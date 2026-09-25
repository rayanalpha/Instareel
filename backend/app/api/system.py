"""Analytics, logs, global settings, WebSocket feed."""
import csv
import datetime as dt
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_current_admin, get_db
from app.config import settings
from app.core.security import decode_token
from app.models import LogLevel, Post, PostStatus, Setting, SystemLog, Video
from app.schemas.content import LogOut, SettingOut, SettingUpdate
from app.services import analytics_service, log_service

analytics_router = APIRouter()
logs_router = APIRouter()
settings_router = APIRouter()
system_router = APIRouter()


@system_router.get("/stats")
async def system_stats(_: str = Depends(get_current_admin)):
    """Live host + container resources for the Server panel.

    Runs in a thread (psutil blocks ~0.5s for a real CPU sample, the
    Docker socket can stall) so the event loop never waits on it.
    """
    import asyncio

    from app.services import host_stats

    return await asyncio.to_thread(host_stats.full_snapshot)


@analytics_router.get("/overview")
async def overview(days: int = Query(default=30, ge=1, le=365), _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    data = await analytics_service.overview(db, since)
    data["series"] = await analytics_service.views_over_time(db, days)
    return data


@analytics_router.get("/posts")
async def posts_breakdown(limit: int = Query(default=100, ge=1, le=2000), _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Post).where(Post.status == PostStatus.posted).order_by(desc(Post.posted_at)).limit(limit))).scalars().all()
    return [
        {"id": p.id, "account_id": p.account_id, "views_7d": p.views_7d, "likes_7d": p.likes_7d,
         "comments_7d": p.comments_7d, "engagement_rate": p.engagement_rate, "posted_at": p.posted_at}
        for p in rows
    ]


@analytics_router.get("/accounts")
async def accounts_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await analytics_service.account_comparison(db)


@analytics_router.get("/effects")
async def effects_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import EffectPreset, Video

    # One grouped query — not one aggregate per preset (N+1).
    agg = {
        (r[0] or ""): r[1:]
        for r in (
            await db.execute(
                select(
                    Video.effect_preset,
                    func.count(Post.id),
                    func.avg(Post.engagement_rate),
                    func.coalesce(func.sum(Post.views_7d), 0),
                )
                .join(Video, Video.id == Post.video_id)
                .where(Post.status == PostStatus.posted, Video.effect_preset.is_not(None))
                .group_by(Video.effect_preset)
            )
        ).all()
    }
    presets = (await db.execute(select(EffectPreset))).scalars().all()
    return [
        {"name": p.name, "posts": agg.get(p.name, (0, None, 0))[0],
         "avg_engagement": round(float(agg.get(p.name, (0, None, 0))[1] or 0), 2),
         "views": int(agg.get(p.name, (0, None, 0))[2] or 0)}
        for p in presets
    ]


@analytics_router.get("/audio")
async def audio_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Per-track performance: which trending sound actually drives explore.

    Attribution rides on Video.audio_track (set at processing time), mirroring
    the effects breakdown — no extra columns needed.
    """
    from app.models import AudioTrack, Video

    agg = {
        (r[0] or ""): r[1:]
        for r in (
            await db.execute(
                select(
                    Video.audio_track,
                    func.count(Post.id),
                    func.avg(Post.engagement_rate),
                    func.coalesce(func.sum(Post.views_7d), 0),
                )
                .join(Video, Video.id == Post.video_id)
                .where(Post.status == PostStatus.posted, Video.audio_track.is_not(None))
                .group_by(Video.audio_track)
            )
        ).all()
    }
    tracks = (await db.execute(select(AudioTrack))).scalars().all()
    out = []
    for track in tracks:
        row = agg.get(track.name, (0, None, 0))
        out.append({
            "id": track.id, "name": track.name, "posts": row[0],
            "avg_engagement": round(float(row[1] or 0), 2), "views": int(row[2] or 0),
            "use_count": track.use_count, "is_active": track.is_active,
        })
    return out


@analytics_router.get("/captions")
async def captions_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import CaptionTemplate

    templates = (await db.execute(select(CaptionTemplate))).scalars().all()
    # Same approximation as /captions/{id}/performance: posts whose caption
    # matches the template exactly. No stored column (it was never computed).
    agg = {
        (r[0] or ""): r[1:]
        for r in (
            await db.execute(
                select(
                    Post.caption,
                    func.count(Post.id),
                    func.avg(Post.engagement_rate),
                    func.coalesce(func.sum(Post.views_7d), 0),
                )
                .where(Post.status == PostStatus.posted)
                .group_by(Post.caption)
            )
        ).all()
    }
    out = []
    for t in templates:
        row = agg.get(t.content or "", (0, None, 0))
        out.append({
            "id": t.id, "name": t.name, "use_count": t.use_count,
            "avg_engagement": round(float(row[1] or 0), 2),
        })
    return out


@analytics_router.get("/time-slots")
async def time_slots(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await analytics_service.time_slot_performance(db)


@analytics_router.get("/export")
async def export_csv(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Post, Video).join(Video, Video.id == Post.video_id).where(Post.status == PostStatus.posted).order_by(desc(Post.posted_at)).limit(2000))).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "account_id", "posted_at", "views_7d", "likes_7d", "comments_7d", "engagement_rate", "audio_track", "url"])
    for p, v in rows:
        w.writerow([p.id, p.account_id, p.posted_at, p.views_7d, p.likes_7d, p.comments_7d, p.engagement_rate, v.audio_track, p.ig_permalink])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=analytics.csv"})


# ---- Logs ----

@logs_router.get("", response_model=list[LogOut])
async def list_logs(
    level: str | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(SystemLog)
    if level:
        try:
            q = q.where(SystemLog.level == LogLevel[level.upper()])
        except KeyError:
            raise HTTPException(400, f"Invalid level (known: {[e.value for e in LogLevel]})")
    if category:
        q = q.where(SystemLog.category == category)
    if search:
        q = q.where(SystemLog.message.ilike(f"%{search}%"))
    q = q.order_by(desc(SystemLog.timestamp)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [LogOut(id=r.id, level=r.level.value, category=r.category, message=r.message, details=r.details, timestamp=r.timestamp) for r in rows]


@logs_router.get("/stats")
async def logs_stats(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SystemLog.level, func.count(SystemLog.id)).group_by(SystemLog.level))).all()
    return {r[0].value: r[1] for r in rows}


@logs_router.delete("", status_code=204)
async def clear_logs(
    older_than_days: int = Query(default=30, ge=0, le=3650),
    _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than_days)
    await db.execute(delete(SystemLog).where(SystemLog.timestamp < cutoff))
    await db.commit()
    return None


# ---- Settings ----

DEFAULT_SETTINGS = {
    "auto_process_on_upload": ("true", "processing"),
    "post_jitter_minutes": ("5", "scheduler"),
    "pool_country": ("", "proxy"),
    "pool_require_country": ("false", "proxy"),
    "pool_purge_after_days": ("7", "proxy"),
    "pool_stillborn_hours": ("48", "proxy"),
}

MASKED = "••••••••"


@settings_router.get("", response_model=list[SettingOut])
async def list_settings(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    for key, (val, cat) in DEFAULT_SETTINGS.items():
        if not await db.get(Setting, key):
            db.add(Setting(key=key, value=val, category=cat))
    await db.commit()
    rows = (await db.execute(select(Setting).order_by(Setting.category, Setting.key))).scalars().all()
    return [SettingOut(key=s.key, value=(MASKED if s.is_sensitive and s.value else s.value), category=s.category, is_sensitive=s.is_sensitive) for s in rows]


@settings_router.put("/{key}", response_model=SettingOut, status_code=200)
async def update_setting(
    key: str, body: SettingUpdate,
    _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db),
):
    """Update an existing setting (JSON body: {"value": ...}).

    Arbitrary key creation is rejected: unknown keys 404 with the known key
    list instead of silently polluting the table. (The old query-param
    contract is gone — the dashboard sends a JSON body.)
    """
    if len(key) > 128 or not key.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise HTTPException(400, "Invalid setting key")
    s = await db.get(Setting, key)
    if not s:
        if key not in DEFAULT_SETTINGS:
            known = sorted(DEFAULT_SETTINGS)
            raise HTTPException(404, f"Unknown setting. Known keys: {known}")
        s = Setting(key=key, value=body.value, category=DEFAULT_SETTINGS[key][1])
        db.add(s)
    else:
        s.value = body.value
        s.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(s)
    return SettingOut(key=s.key, value=(MASKED if s.is_sensitive else s.value), category=s.category, is_sensitive=s.is_sensitive)


@settings_router.post("/test-instagram")
async def test_instagram(
    _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db),
):
    from app.models import Account

    count = (await db.execute(select(func.count(Account.id)))).scalar() or 0
    return {"ok": True, "accounts": count, "note": "Use /accounts/{id}/test-session for a live session check"}


# ---- WebSocket ----

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def ws_feed(websocket: WebSocket):
    await websocket.accept()
    # Auth arrives as the first message frame ({ "token": ... }), never as a
    # URL query param (URLs are written to access logs). Legacy ?token= URLs
    # are still honored during the transition, then removed.
    token = websocket.query_params.get("token", "")
    if not token:
        try:
            import asyncio as _asyncio

            raw = await _asyncio.wait_for(websocket.receive_text(), timeout=10)
            token = (json.loads(raw) or {}).get("token", "")
        except Exception:
            token = ""
    try:
        decode_token(token, expected_type="access")
    except ValueError:
        await websocket.close(code=4401)
        return
    client = None
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("igfunnel:events")
        await websocket.send_text(json.dumps({"event": "connected"}))
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20.0)
            if msg and msg.get("data"):
                await websocket.send_text(msg["data"])
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        try:
            if client is not None:
                await client.aclose()
        except Exception:
            pass
