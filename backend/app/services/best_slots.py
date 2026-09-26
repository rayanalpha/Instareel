"""Golden-hour suggestions: per-account best posting slots from history.

Builds on the analytics already collected (posted_at + views_7d per
post). Aggregation runs in Python over plain rows — deliberately NOT
EXTRACT(dow/hour) in SQL, so the same code serves SQLite and Postgres.

Hours are stored UTC; the UI-facing labels are wall-clock in SCHEDULE_TZ
(the same zone schedule-rule hours are interpreted in), so the suggested
hour can be copied straight into the rule form.

Design rules (anti-interference):
- Read-only: no schema change, no tick change. Suggestions surface in
  Analytics + a one-click "fill the new-rule form" button; the admin
  still owns the rule.
- Pure aggregate core (aggregate_slots) over (hour, views) pairs —
  fully unit-tested without a DB.
- Accounts with too little history get the global fallback marked
  personalized=false instead of a misleading "best" slot.
"""
import datetime as dt

from app.config import settings

MIN_POSTS_PERSONALIZED = 3
DEFAULT_LIMIT = 5


def tz_label() -> str:
    """Short display name for the schedule zone, e.g. 'Tehran'."""
    return settings.SCHEDULE_TZ.split("/")[-1].replace("_", " ")


def local_label(utc_hour: int, utc_minute: int = 0) -> str:
    """'21:30' style wall-clock in the schedule timezone for a UTC hour."""
    from zoneinfo import ZoneInfo

    t = dt.datetime(2000, 1, 1, utc_hour, utc_minute, tzinfo=dt.timezone.utc)
    return t.astimezone(ZoneInfo(settings.SCHEDULE_TZ)).strftime("%H:%M")


def local_hour(utc_hour: int) -> int:
    """Rule-form hour matching a UTC hour in the schedule timezone."""
    from zoneinfo import ZoneInfo

    t = dt.datetime(2000, 1, 1, utc_hour, tzinfo=dt.timezone.utc)
    return t.astimezone(ZoneInfo(settings.SCHEDULE_TZ)).hour


def aggregate_slots(pairs: list[tuple[int, int]], *, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Rank UTC hours by average views. pairs = [(utc_hour, views), ...]."""
    from collections import defaultdict

    by_hour: dict[int, list[int]] = defaultdict(list)
    for hour, views in pairs:
        by_hour[int(hour)].append(int(views or 0))
    ranked = sorted(
        (
            {
                "hour_utc": h,
                # Wall-clock in the schedule zone — copy-pasteable into the
                # rule form, which is interpreted in that same zone.
                "hour_local": local_hour(h),
                "local": local_label(h),
                "tz": settings.SCHEDULE_TZ,
                "tz_label": tz_label(),
                "posts": len(v),
                "avg_views": int(sum(v) / len(v)),
            }
            for h, v in by_hour.items()
        ),
        key=lambda s: (-s["avg_views"], -s["posts"], s["hour_utc"]),
    )
    return ranked[:limit]


async def best_slots_for_account(db, account_id: int, *, limit: int = DEFAULT_LIMIT) -> dict:
    """Top posting slots for one account, with global fallback."""
    from sqlalchemy import select

    from app.models import Account, Post, PostStatus

    acc = await db.get(Account, account_id)
    if acc is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Account not found")

    rows = (
        await db.execute(
            select(Post.posted_at, Post.views_7d).where(
                Post.account_id == account_id,
                Post.status == PostStatus.posted,
                Post.posted_at.is_not(None),
            )
        )
    ).all()

    def utc_hour(ts) -> int:
        if ts is not None and getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        return ts.hour if ts is not None else 0

    pairs = [(utc_hour(ts), v or 0) for ts, v in rows]
    personalized = len(pairs) >= MIN_POSTS_PERSONALIZED
    if not personalized:
        grows = (
            await db.execute(
                select(Post.posted_at, Post.views_7d).where(
                    Post.status == PostStatus.posted,
                    Post.posted_at.is_not(None),
                ).limit(5000)
            )
        ).all()
        pairs = [(utc_hour(ts), v or 0) for ts, v in grows]
    return {
        "account_id": account_id,
        "username": acc.username,
        "personalized": personalized,
        "min_posts_for_personalized": MIN_POSTS_PERSONALIZED,
        "slots": aggregate_slots(pairs, limit=limit),
    }
