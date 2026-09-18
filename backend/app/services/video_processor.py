"""FFmpeg processing pipeline orchestrator.

Async variant (web API) + fully synchronous variant (Celery workers).
Celery must ONLY use process_video_sync — it never touches an event loop.
"""
import hashlib
import logging
import os
import subprocess
import uuid

from app.config import settings
from app.utils import ffmpeg as ff

log = logging.getLogger("igfunnel.video")


def media_dirs() -> dict[str, str]:
    root = settings.MEDIA_ROOT
    dirs = {
        "raw": os.path.join(root, "raw"),
        "processed": os.path.join(root, "processed"),
        "thumbnails": os.path.join(root, "thumbnails"),
        "watermarks": os.path.join(root, "watermarks"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_watermark() -> str | None:
    p = os.path.join(media_dirs()["watermarks"], "watermark.png")
    return p if os.path.exists(p) else None


async def extract_thumbnail(src: str, duration: float, dst: str) -> None:
    import asyncio

    at = max(0.1, duration * 0.25)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", "-q:v", "3", dst,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()


def extract_thumbnail_sync(src: str, duration: float, dst: str) -> None:
    """Blocking thumbnail extraction (Celery-safe)."""
    at = max(0.1, duration * 0.25)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", "-q:v", "3", dst],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )


def process_video_sync(video_id: int, effect_filter: str = "", color_grade: str = "") -> str:
    """Run the full pipeline synchronously. Returns processed_path. Raises on failure."""
    import datetime as dt

    from app.database import SyncSessionLocal
    from app.models import Video, VideoStatus
    from app.tasks.sync_helpers import log_event_sync, set_progress_sync

    with SyncSessionLocal() as s:
        from sqlalchemy import select

        from app.models import EffectPreset

        video = s.get(Video, video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")
        raw_path = video.raw_path
        trim_start, trim_end = video.trim_start, video.trim_end
        effect_preset = video.effect_preset
        if not effect_filter and effect_preset:
            # effect_preset stores the preset NAME — resolve to its filter.
            preset = s.execute(
                select(EffectPreset).where(
                    EffectPreset.name == effect_preset,
                    EffectPreset.is_active.is_(True),
                )
            ).scalars().first()
            if preset:
                effect_preset = preset.ffmpeg_filter or ""
            else:
                # Unknown name (e.g. deleted preset) — never feed it to FFmpeg.
                effect_preset = ""
        custom_filters = video.custom_filters
        add_watermark = video.add_watermark
        video.status = VideoStatus.processing
        s.commit()

    dirs = media_dirs()
    set_progress_sync(video_id, 2, "probing")
    info = ff.probe_sync(raw_path)
    if info["duration"] < 3:
        raise ValueError(f"Video too short ({info['duration']:.1f}s < 3s)")
    set_progress_sync(video_id, 8, "validated")

    out_name = f"{uuid.uuid4().hex}.mp4"
    dst = os.path.join(dirs["processed"], out_name)
    watermark = default_watermark() if add_watermark else None
    cmd = ff.build_command(
        raw_path, dst,
        trim_start=trim_start, trim_end=trim_end,
        effect_filter=effect_filter or (effect_preset or ""),
        custom_filters=custom_filters or "",
        color_grade=color_grade,
        watermark_path=watermark,
        has_audio=info["has_audio"],
    )

    def on_progress(pct: float, stage: str):
        set_progress_sync(video_id, 8 + pct * 0.85, stage)

    ff.run_sync_with_progress(cmd, info["duration"], on_progress)

    thumb_name = f"{uuid.uuid4().hex}.jpg"
    thumb_path = os.path.join(dirs["thumbnails"], thumb_name)
    try:
        extract_thumbnail_sync(dst, info["duration"], thumb_path)
    except Exception:
        log.warning("Thumbnail extraction failed for video %s", video_id)
        thumb_path = None

    digest = md5_of_file(dst)
    with SyncSessionLocal() as s:
        video = s.get(Video, video_id)
        if video:
            video.processed_path = dst
            video.thumbnail_path = thumb_path
            video.duration = info["duration"]
            video.file_size = os.path.getsize(dst)
            video.processed_at = dt.datetime.now(dt.timezone.utc)
            video.status = VideoStatus.processed
            s.commit()
    log_event_sync("INFO", "video", f"Video {video_id} processed", {"md5": digest})
    set_progress_sync(video_id, 100, "done")
    return dst


async def process_video(
    video_id: int,
    get_video,   # async callable returning a DB-attached Video
    save_video,  # async callable persisting changes
    effect_filter: str = "",
    color_grade: str = "",
) -> str:
    """Async pipeline (web API use). Celery workers must use process_video_sync."""
    from app.services import realtime

    video = await get_video(video_id)
    dirs = media_dirs()
    await realtime.set_progress(video_id, 2, "probing")
    info = await ff.probe(video.raw_path)
    if info["duration"] < 3:
        raise ValueError(f"Video too short ({info['duration']:.1f}s < 3s)")
    await realtime.set_progress(video_id, 8, "validated")

    out_name = f"{uuid.uuid4().hex}.mp4"
    dst = os.path.join(dirs["processed"], out_name)
    watermark = default_watermark() if video.add_watermark else None
    cmd = ff.build_command(
        video.raw_path, dst,
        trim_start=video.trim_start, trim_end=video.trim_end,
        effect_filter=effect_filter or (video.effect_preset or ""),
        custom_filters=video.custom_filters or "",
        color_grade=color_grade,
        watermark_path=watermark,
        has_audio=info["has_audio"],
    )

    async def on_progress(pct: float, stage: str):
        await realtime.set_progress(video_id, 8 + pct * 0.85, stage)

    await ff.run_with_progress(cmd, info["duration"], on_progress)

    thumb_name = f"{uuid.uuid4().hex}.jpg"
    thumb_path = os.path.join(dirs["thumbnails"], thumb_name)
    try:
        await extract_thumbnail(dst, info["duration"], thumb_path)
    except Exception:
        log.warning("Thumbnail extraction failed for video %s", video_id)
        thumb_path = None

    digest = md5_of_file(dst)
    await save_video(video_id, {
        "processed_path": dst,
        "thumbnail_path": thumb_path,
        "duration": info["duration"],
        "file_size": os.path.getsize(dst),
        "md5_hash_processed": digest,
        "processed_at": True,
    })
    await realtime.set_progress(video_id, 100, "done")
    return dst
