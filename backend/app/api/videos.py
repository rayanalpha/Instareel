"""Video upload / processing / preview + post history endpoints."""
import asyncio
import hashlib
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.config import settings
from app.models import Post, PostStatus, Video, VideoStatus
from app.schemas.video import PostOut, SchedulePostIn, VideoOut, VideoSettingsUpdate
from app.services import realtime
from app.services.log_service import log_event
from app.services.video_processor import media_dirs

router = APIRouter()

ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
UPLOAD_CHUNK = 4 * 1024 * 1024


def _out(v: Video) -> VideoOut:
    return VideoOut(
        id=v.id, original_filename=v.original_filename, duration=v.duration, file_size=v.file_size,
        status=v.status.value, effect_preset=v.effect_preset, audio_track=v.audio_track,
        custom_filters=v.custom_filters, add_watermark=v.add_watermark,
        trim_start=v.trim_start, trim_end=v.trim_end, failed_reason=v.failed_reason,
        processed_at=v.processed_at, thumbnail_path=v.thumbnail_path, created_at=v.created_at,
    )


async def _audio_map(db: AsyncSession, video_ids: list[int]) -> dict[int, str | None]:
    """Batch audio_track lookup for posts (one query, no N+1)."""
    if not video_ids:
        return {}
    rows = (
        await db.execute(select(Video.id, Video.audio_track).where(Video.id.in_(video_ids)))
    ).all()
    return {vid: audio for vid, audio in rows}


def _post_out(p: Post, audio_track: str | None = None) -> PostOut:
    return PostOut(
        id=p.id, video_id=p.video_id, account_id=p.account_id, ig_media_id=p.ig_media_id,
        ig_permalink=p.ig_permalink, caption=p.caption, hashtags=p.hashtags, status=p.status.value,
        audio_track=audio_track,
        scheduled_for=p.scheduled_for, posted_at=p.posted_at, views_24h=p.views_24h,
        views_7d=p.views_7d, likes_24h=p.likes_24h, engagement_rate=p.engagement_rate,
        fail_reason=p.fail_reason, retry_count=p.retry_count, created_at=p.created_at,
    )


@router.get("", response_model=list[VideoOut])
async def list_videos(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Video)
    if status:
        try:
            q = q.where(Video.status == VideoStatus(status))
        except ValueError:
            raise HTTPException(400, "Invalid status")
    if search:
        q = q.where(Video.original_filename.ilike(f"%{search}%"))
    q = q.order_by(desc(Video.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [_out(v) for v in rows]


@router.post("/upload", response_model=VideoOut, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.utils import ffmpeg as ff

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED_EXT)}")
    dirs = media_dirs()
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(dirs["raw"], tmp_name)
    size = 0
    h = hashlib.md5()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    try:
        # Stream straight to disk (constant memory, regardless of file size).
        async with aiofiles.open(raw_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")
                h.update(chunk)
                await f.write(chunk)
    except HTTPException:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        await file.close()
        raise
    except Exception as exc:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        await file.close()
        raise HTTPException(400, f"Upload failed: {exc}")
    finally:
        try:
            await file.close()
        except Exception:
            pass
    if size == 0:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        raise HTTPException(400, "Empty file")
    digest = h.hexdigest()
    dup = (await db.execute(select(Video).where(Video.md5_hash == digest))).scalar_one_or_none()
    if dup:
        os.remove(raw_path)
        raise HTTPException(409, f"Duplicate of video #{dup.id} ({dup.original_filename})")
    # Validate the container before committing: reject corrupt/non-video uploads early.
    try:
        probe = await asyncio.wait_for(asyncio.to_thread(ff.probe_sync, raw_path), timeout=90)
    except Exception:
        os.remove(raw_path)
        raise HTTPException(422, "File is not a valid video (ffprobe validation failed)")
    video = Video(
        original_filename=file.filename or tmp_name,
        raw_path=raw_path,
        file_size=size,
        md5_hash=digest,
        duration=probe.get("duration"),
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    await log_event("INFO", "video", f"Uploaded {video.original_filename} (#{video.id})")
    if settings.AUTO_PROCESS_ON_UPLOAD:
        from app.tasks.video_tasks import process_video_task

        process_video_task.delay(video.id)
    return _out(video)


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _out(v)


@router.delete("/{video_id}", status_code=204)
async def delete_video(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    for path in (v.raw_path, v.processed_path, v.thumbnail_path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    await db.delete(v)
    await db.commit()
    return None


@router.post("/{video_id}/process")
async def trigger_process(video_id: int, effect_filter: str = "", _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status == VideoStatus.processing:
        raise HTTPException(409, "Already processing")
    from app.tasks.video_tasks import process_video_task

    process_video_task.delay(video_id, effect_filter)
    return {"queued": True}


@router.post("/{video_id}/reprocess")
async def reprocess(video_id: int, effect_filter: str = "", _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status == VideoStatus.processing:
        raise HTTPException(409, "Already processing")
    from app.tasks.video_tasks import process_video_task

    process_video_task.delay(video_id, effect_filter)
    return {"queued": True}


@router.get("/{video_id}/status")
async def processing_status(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    progress = await realtime.get_progress(video_id)
    return {"status": v.status.value, "progress": progress, "failed_reason": v.failed_reason}


@router.put("/{video_id}/settings", response_model=VideoOut)
async def update_settings(video_id: int, body: VideoSettingsUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if body.trim_start is not None and body.trim_end is not None and body.trim_end <= body.trim_start:
        raise HTTPException(400, "trim_end must be greater than trim_start")
    for field in ("effect_preset", "audio_track", "custom_filters", "trim_start", "trim_end", "add_watermark"):
        val = getattr(body, field)
        if val is not None:
            setattr(v, field, val)
    await db.commit()
    await db.refresh(v)
    return _out(v)


def _serve(path: str | None, media_type: str):
    if not path or not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=media_type)


@router.get("/{video_id}/preview")
async def preview(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _serve(v.processed_path or v.raw_path, "video/mp4")


@router.get("/{video_id}/thumbnail")
async def thumbnail(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _serve(v.thumbnail_path, "image/jpeg")


# ---- Posts ----

posts_router = APIRouter()


@posts_router.get("", response_model=list[PostOut])
async def list_posts(
    status: str | None = Query(default=None),
    account_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Post)
    if status:
        try:
            q = q.where(Post.status == PostStatus(status))
        except ValueError:
            raise HTTPException(400, "Invalid status")
    if account_id:
        q = q.where(Post.account_id == account_id)
    q = q.order_by(desc(Post.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    audio = await _audio_map(db, [p.video_id for p in rows])
    return [_post_out(p, audio.get(p.video_id)) for p in rows]


@posts_router.get("/queue", response_model=list[PostOut])
async def post_queue(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt

    rows = (
        await db.execute(
            select(Post)
            .where(Post.status == PostStatus.scheduled)
            .order_by(Post.scheduled_for.asc().nulls_first())
            .limit(100)
        )
    ).scalars().all()
    audio = await _audio_map(db, [p.video_id for p in rows])
    return [_post_out(p, audio.get(p.video_id)) for p in rows]


@posts_router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    audio = await _audio_map(db, [p.video_id])
    return _post_out(p, audio.get(p.video_id))


@posts_router.post("/schedule", response_model=PostOut, status_code=201)
async def schedule_post(body: SchedulePostIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt

    v = await db.get(Video, body.video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status != VideoStatus.processed:
        raise HTTPException(400, f"Video must be processed first (now: {v.status.value})")
    from app.services import scheduler_service as sched_async

    if await sched_async.video_already_queued(db, body.video_id):
        raise HTTPException(400, "Video already has a pending post")
    account_id = body.account_id
    if not account_id:
        from app.services import scheduler_service

        acc = await scheduler_service.eligible_account(db, None)
        if not acc:
            raise HTTPException(400, "No eligible account available")
        account_id = acc.id
    post = Post(
        video_id=body.video_id, account_id=account_id, caption=body.caption,
        hashtags=body.hashtags, status=PostStatus.scheduled,
        scheduled_for=body.scheduled_for or dt.datetime.now(dt.timezone.utc),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_out(post, v.audio_track)


@posts_router.post("/{post_id}/retry")
async def retry_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    if p.status != PostStatus.failed:
        raise HTTPException(400, "Only failed posts can be retried")
    p.status = PostStatus.scheduled
    import datetime as dt

    p.scheduled_for = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    from app.tasks.post_tasks import execute_post

    execute_post.delay(post_id)
    return {"queued": True}


@posts_router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    await db.delete(p)
    await db.commit()
    return None
