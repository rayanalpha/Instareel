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
        if acc and acc.status == AccountStatus.active and acc.posts_today < acc.max_daily_posts:
            if not acc.cooldown_until or acc.cooldown_until <= now:
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
    return session.execute(q).scalars().first()


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
