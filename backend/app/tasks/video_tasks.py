"""Video processing celery task — never crashes the worker.

Fully synchronous: no asyncio.run, no event loop. Uses SyncSessionLocal
and the sync FFmpeg pipeline.
"""
import logging
import random

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks.video")


@celery.task(name="tasks.video_tasks.process_video", bind=True, max_retries=2)
def process_video_task(self, video_id: int, effect_filter: str = "", color_grade: str = ""):
    import datetime as dt

    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import EffectPreset, Video, VideoStatus
    from app.services.video_processor import process_video_sync
    from app.tasks.sync_helpers import log_event_sync, publish_sync

    def mark(status: VideoStatus, reason: str | None = None):
        with SyncSessionLocal() as s:
            v = s.get(Video, video_id)
            if v:
                v.status = status
                if reason is not None:
                    v.failed_reason = reason[:2000]
                s.commit()

    try:
        mark(VideoStatus.processing)
        if not effect_filter:
            with SyncSessionLocal() as s:
                video = s.get(Video, video_id)
                chosen_name = (video.effect_preset or "").strip() if video else ""
                if chosen_name:
                    # The video stores the preset NAME — resolve it to the
                    # real FFmpeg filter (never feed the raw name to FFmpeg).
                    preset = s.execute(
                        select(EffectPreset).where(
                            EffectPreset.name == chosen_name,
                            EffectPreset.is_active.is_(True),
                        )
                    ).scalars().first()
                    if preset:
                        effect_filter = preset.ffmpeg_filter or ""
                if not effect_filter:
                    presets = s.execute(
                        select(EffectPreset).where(EffectPreset.is_active.is_(True))
                    ).scalars().all()
                    if presets:
                        effect_filter = random.choice(presets).ffmpeg_filter or ""
        process_video_sync(video_id, effect_filter, color_grade)
        publish_sync("video_processing_complete", {"video_id": video_id, "status": "processed"})
        log_event_sync("INFO", "video", f"Video {video_id} processed successfully")
        return {"video_id": video_id, "status": "processed"}
    except Exception as exc:  # noqa: BLE001 — must never crash worker
        log.exception("process_video_task failed for %s", video_id)
        mark(VideoStatus.failed, str(exc))
        publish_sync("video_processing_complete", {"video_id": video_id, "status": "failed"})
        log_event_sync("ERROR", "video", f"Video {video_id} failed: {exc}")
        return {"video_id": video_id, "status": "failed", "error": str(exc)}
