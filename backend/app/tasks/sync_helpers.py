"""Sync helpers for Celery tasks: blocking realtime pub/sub, sync logging, sync scheduler."""
import json
import logging
import random

import redis

from app.config import settings

_channel = "igfunnel:events"
log = logging.getLogger("igfunnel")


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish_sync(event: str, payload: dict) -> None:
    """Blocking publish (Celery-safe). Failures are swallowed — best effort."""
    try:
        client = _redis_client()
        try:
            client.publish(_channel, json.dumps({"event": event, **payload}))
        finally:
            client.close()
    except Exception:
        pass


def set_progress_sync(video_id: int, percentage: float, stage: str) -> None:
    try:
        client = _redis_client()
        try:
            client.set(
                f"igfunnel:progress:{video_id}",
                json.dumps({"percentage": percentage, "stage": stage}),
                ex=3600,
            )
        finally:
            client.close()
        publish_sync(
            "video_processing_progress",
            {"video_id": video_id, "percentage": percentage, "stage": stage},
        )
    except Exception:
        pass


def log_event_sync(level: str, category: str, message: str, details: dict | None = None) -> None:
    """Sync audit-log write for Celery tasks (commit included)."""
    from app.database import SyncSessionLocal
    from app.models import LogLevel, SystemLog

    try:
        lvl = LogLevel[level.upper()]
    except KeyError:
        lvl = LogLevel.INFO
    getattr(log, lvl.name.lower(), log.info)("[%s] %s", category, message)
    try:
        with SyncSessionLocal() as session:
            session.add(SystemLog(level=lvl, category=category, message=message, details=details))
            session.commit()
    except Exception:
        log.exception("Failed to persist system log")


# ---- Sync scheduler helpers (mirrors the async service used by the web API) ----

import datetime as dt

from sqlalchemy import func, select

# ---- Account/proxy health policy (pure helpers — unit tested) ----

#: Fresh accounts stay in warm-up this long (see effective_max_posts).
WARMUP_DAYS = 7
#: Posting cap applied during warm-up regardless of the account setting.
WARMUP_MAX_POSTS = 1
#: Consecutive proxy failures before the proxy is auto-disabled.
MAX_PROXY_FAILS = 5
#: Cooldown given to accounts whose proxy was just auto-disabled.
PROXY_FAIL_COOLDOWN_HOURS = 6
#: Bio rotation skips accounts younger than this (fresh accounts changing bio = flag).
BIO_MIN_AGE_DAYS = 14
#: Analytics skips accounts younger than this (saves logins on day-0 accounts).
ANALYTICS_MIN_AGE_DAYS = 3


def account_age_days(created_at: "dt.datetime | None", now: "dt.datetime | None" = None) -> float:
    """Age in days; tolerates naive datetimes (SQLite) by assuming UTC."""
    now = now or _now()
    if created_at is None:
        return 10**9
    ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return (now - ts).total_seconds() / 86400


def effective_max_posts(created_at: "dt.datetime | None", max_daily_posts: int, now: "dt.datetime | None" = None) -> int:
    """Warm-up cap: accounts younger than WARMUP_DAYS post at most 1/day.

    Handles naive datetimes (SQLite stores func.now() without tz) by
    assuming UTC, so the same code works on SQLite and Postgres.
    """
    now = now or _now()
    if created_at is None:
        return max_daily_posts
    ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    if (now - ts).days < WARMUP_DAYS:
        return min(WARMUP_MAX_POSTS, max_daily_posts)
    return max_daily_posts


def throttle_cooldown_hours(retry_count: int) -> int:
    """Exponential backoff for throttled accounts: 6h -> 12h -> 24h (capped)."""
    return 6 * (2 ** max(0, min(retry_count, 2)))


def rank_spare_proxies(candidates: list[dict], prefer_country: str = ""):
    """Pick the best spare proxy (pure — unit tested).

    Each candidate: {"proxy": obj, "load": int, "country": str, "latency": int|None}.
    Prefers same-country (no sudden geo-hop), then fewest accounts, then lowest latency.
    Returns the proxy object or None.
    """
    if not candidates:
        return None
    want = (prefer_country or "").upper()

    def key(c: dict):
        same = 0 if (want and (c.get("country") or "").upper() == want) else 1
        lat = c.get("latency")
        return (same, c.get("load", 0), lat if lat is not None else 10**9)

    return sorted(candidates, key=key)[0]["proxy"]


def pick_spare_proxy(session, exclude_id: "int | None" = None, prefer_country: "str | None" = None):
    """Healthiest spare proxy from the DB (active + healthy, not exclude_id)."""
    from sqlalchemy import func as _func
    from sqlalchemy import select as _select

    from app.models import Account, Proxy

    q = (
        _select(Proxy, _func.count(Account.id))
        .outerjoin(Account, Account.proxy_id == Proxy.id)
        .where(Proxy.is_active.is_(True), Proxy.is_healthy.is_(True))
        .group_by(Proxy.id)
    )
    if exclude_id:
        q = q.where(Proxy.id != exclude_id)
    rows = session.execute(q).all()
    cands = [
        {"proxy": p, "load": cnt or 0, "country": p.country or "", "latency": p.latency_ms}
        for p, cnt in rows
    ]
    return rank_spare_proxies(cands, prefer_country or "")


def resolve_proxy_url(session, account) -> "str | None":
    """Connection URL for this post: own proxy if healthy, else best spare.

    Returns None for direct connection (no proxy assigned) AND when no
    healthy route exists — use account_reachable() to tell them apart.
    """
    from app.models import Proxy
    from app.services.proxy_service import proxy_url_for

    own = session.get(Proxy, account.proxy_id) if account.proxy_id else None
    if own is None and not account.proxy_id:
        return None
    if own is not None and own.is_active and own.is_healthy:
        return proxy_url_for(own)
    spare = pick_spare_proxy(
        session,
        exclude_id=own.id if own else None,
        prefer_country=own.country if own else None,
    )
    return proxy_url_for(spare) if spare is not None else None


def account_reachable(session, account) -> bool:
    """False only when the account needs a proxy but none healthy exists."""
    if not account.proxy_id:
        return True
    from app.models import Proxy

    own = session.get(Proxy, account.proxy_id)
    if own is not None and own.is_active and own.is_healthy:
        return True
    spare = pick_spare_proxy(
        session,
        exclude_id=own.id if own else None,
        prefer_country=own.country if own else None,
    )
    return spare is not None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def due_rules(session, at: "dt.datetime | None" = None):
    from app.models import ScheduleRule

    at = at or _now()
    q = select(ScheduleRule).where(
        ScheduleRule.is_active.is_(True),
        ((ScheduleRule.day_of_week == -1) | (ScheduleRule.day_of_week == at.weekday())),
        ScheduleRule.hour == at.hour,
        ScheduleRule.minute == at.minute,
    )
    return list(session.execute(q).scalars().all())


def eligible_account(session, account_id: "int | None" = None):
    from app.models import Account, AccountStatus

    now = _now()
    if account_id:
        acc = session.get(Account, account_id)
        if acc and acc.status == AccountStatus.active:
            if not acc.cooldown_until or acc.cooldown_until <= now:
                if acc.posts_today < effective_max_posts(acc.created_at, acc.max_daily_posts, now):
                    return acc
        return None
    q = (
        select(Account)
        .where(
            Account.status == AccountStatus.active,
            Account.posts_today < Account.max_daily_posts,
            ((Account.cooldown_until.is_(None)) | (Account.cooldown_until <= now)),
            ((Account.last_post.is_(None)) | (Account.last_post <= now - dt.timedelta(hours=2))),
        )
        .order_by(Account.last_post.asc().nulls_first())
    )
    # Warm-up cap is per-account age — filter in Python over the ordered set
    # so a fresh account yields to older ones instead of blocking the slot.
    for acc in session.execute(q).scalars().all():
        if acc.posts_today < effective_max_posts(acc.created_at, acc.max_daily_posts, now):
            return acc
    return None


def next_video(session, effect: "str | None" = None):
    """Oldest processed video, preferring the rule's effect; fallback to any."""
    from app.models import Video, VideoStatus

    base = select(Video).where(Video.status == VideoStatus.processed)
    if effect:
        preferred = base.where(Video.effect_preset == effect).order_by(Video.created_at.asc()).limit(1)
        video = session.execute(preferred).scalars().first()
        if video:
            return video
    return session.execute(base.order_by(Video.created_at.asc()).limit(1)).scalars().first()


def claim_post(session, post_id: int) -> str:
    """Atomically claim a scheduled post for execution (single-flight).

    One UPDATE ... WHERE status=scheduled so concurrent workers, beat
    redelivery and celery retries can never upload the same post twice.
    Returns 'claimed' | 'missing' | 'busy'. Commits on claim.
    """
    from sqlalchemy import update

    from app.models import Post, PostStatus

    res = session.execute(
        update(Post)
        .where(Post.id == post_id, Post.status == PostStatus.scheduled)
        .values(status=PostStatus.posting)
    )
    session.commit()
    if res.rowcount:
        return "claimed"
    post = session.get(Post, post_id)
    return "missing" if post is None else "busy"


def video_already_queued(session, video_id: int, window_min: int = 10) -> bool:
    """True when the video already has a pending scheduled post in the window.

    Prevents two rules in one tick (or API + beat) from queueing the same
    video twice — the video is only freed after it posts or the post fails.
    """
    from app.models import Post, PostStatus

    now = _now()
    q = select(func.count(Post.id)).where(
        Post.video_id == video_id,
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
    )
    return (session.execute(q).scalar() or 0) > 0


def already_scheduled(session, rule, window_min: int = 10) -> bool:
    from app.models import Post, PostStatus

    now = _now()
    q = select(func.count(Post.id)).where(
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
        (Post.account_id == rule.account_id) if rule.account_id else True,
    )
    return (session.execute(q).scalar() or 0) > 0


def pick_caption(session, template_id: "int | None") -> "tuple[str, int | None]":
    from app.models import CaptionTemplate

    if template_id:
        t = session.get(CaptionTemplate, template_id)
        if t and t.is_active:
            return t.content, t.id
    rows = session.execute(select(CaptionTemplate).where(CaptionTemplate.is_active.is_(True))).scalars().all()
    if not rows:
        return "", None
    weights = [1.0 / (1.0 + (r.use_count or 0)) for r in rows]
    chosen = random.choices(rows, weights=weights, k=1)[0]
    return chosen.content, chosen.id


def pick_hashtags(session, last_tags: str = "") -> str:
    from app.models import HashtagSet

    rows = session.execute(select(HashtagSet).where(HashtagSet.is_active.is_(True))).scalars().all()
    rows = [r for r in rows if r.tags.strip() and r.tags.strip() != last_tags.strip()]
    if not rows:
        return ""
    chosen = random.choice(rows)
    tags = [t.strip() for t in chosen.tags.replace("\n", ",").split(",") if t.strip()]
    chosen.use_count += 1
    selected = random.sample(tags, k=min(len(tags), random.randint(3, 5)))
    return " ".join(t if t.startswith("#") else f"#{t}" for t in selected)
