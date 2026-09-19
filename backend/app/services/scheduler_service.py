"""Scheduler helpers: due-rule detection + eligible-account/video selection."""
import datetime as dt
import random

from sqlalchemy import func, select

from app.models import Account, AccountStatus, Post, PostStatus, ScheduleRule, Video, VideoStatus


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def due_rules(session, at: dt.datetime | None = None) -> list[ScheduleRule]:
    """Rules whose (day/hour/minute) match the current minute and are active."""
    at = at or _now()
    q = select(ScheduleRule).where(
        ScheduleRule.is_active.is_(True),
        ((ScheduleRule.day_of_week == -1) | (ScheduleRule.day_of_week == at.weekday())),
        ScheduleRule.hour == at.hour,
        ScheduleRule.minute == at.minute,
    )
    return list((await session.execute(q)).scalars().all())


def effective_max_posts(
    created_at: dt.datetime | None, max_daily_posts: int, now: dt.datetime | None = None
) -> int:
    """Warm-up cap shared with the sync scheduler (see tasks.sync_helpers).

    Accounts younger than 7 days post at most 1/day. Tolerates naive
    datetimes (SQLite) by assuming UTC.
    """
    from app.tasks.sync_helpers import WARMUP_DAYS, WARMUP_MAX_POSTS

    now = now or _now()
    if created_at is None:
        return max_daily_posts
    ts = created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    if (now - ts).days < WARMUP_DAYS:
        return min(WARMUP_MAX_POSTS, max_daily_posts)
    return max_daily_posts


async def eligible_account(session, account_id: int | None = None) -> Account | None:
    from app.tasks.sync_helpers import as_aware_utc

    now = _now()
    if account_id:
        acc = await session.get(Account, account_id)
        if acc and acc.status == AccountStatus.active:
            cd = as_aware_utc(acc.cooldown_until)
            if not cd or cd <= now:
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
    for acc in (await session.execute(q)).scalars().all():
        if acc.posts_today < effective_max_posts(acc.created_at, acc.max_daily_posts, now):
            return acc
    return None


async def next_video(session, effect: str | None = None) -> Video | None:
    """Oldest processed video, preferring one that matches the rule's effect.

    If the rule prefers an effect but no processed video carries it, fall
    back to any processed video so a schedule slot is never silently wasted.
    """
    base = select(Video).where(Video.status == VideoStatus.processed)
    if effect:
        preferred = (
            base.where(Video.effect_preset == effect)
            .order_by(Video.created_at.asc())
            .limit(1)
        )
        video = (await session.execute(preferred)).scalars().first()
        if video:
            return video
    video = (await session.execute(base.order_by(Video.created_at.asc()).limit(1))).scalars().first()
    return video


async def video_already_queued(session, video_id: int, window_min: int = 10) -> bool:
    """Async mirror of tasks.sync_helpers.video_already_queued (API use)."""
    now = _now()
    q = select(func.count(Post.id)).where(
        Post.video_id == video_id,
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
    )
    return ((await session.execute(q)).scalar() or 0) > 0


async def already_scheduled(session, rule: ScheduleRule, window_min: int = 10) -> bool:
    """Avoid double-scheduling when beat fires twice in the same window."""
    now = _now()
    q = select(func.count(Post.id)).where(
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
        (Post.account_id == rule.account_id) if rule.account_id else True,
    )
    return ((await session.execute(q)).scalar() or 0) > 0


async def pick_caption(session, template_id: int | None) -> tuple[str, int | None]:
    from app.models import CaptionTemplate

    if template_id:
        t = await session.get(CaptionTemplate, template_id)
        if t and t.is_active:
            return t.content, t.id
    rows = (await session.execute(select(CaptionTemplate).where(CaptionTemplate.is_active.is_(True)))).scalars().all()
    if not rows:
        return "", None
    weights = [1.0 / (1.0 + (r.use_count or 0)) for r in rows]
    chosen = random.choices(rows, weights=weights, k=1)[0]
    return chosen.content, chosen.id


async def pick_hashtags(session, last_tags: str = "") -> str:
    from app.models import HashtagSet

    rows = (
        await session.execute(select(HashtagSet).where(HashtagSet.is_active.is_(True)))
    ).scalars().all()
    rows = [r for r in rows if r.tags.strip() and r.tags.strip() != last_tags.strip()]
    if not rows:
        return ""
    chosen = random.choice(rows)
    tags = [t.strip() for t in chosen.tags.replace("\n", ",").split(",") if t.strip()]
    chosen.use_count += 1
    selected = random.sample(tags, k=min(len(tags), random.randint(3, 5)))
    return " ".join(t if t.startswith("#") else f"#{t}" for t in selected)
