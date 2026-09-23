"""Video source ingestion: pull reels from an IG page into the videos pipeline."""
import datetime as dt
import hashlib
import logging
import os
import random
import shutil
import time
import uuid

log = logging.getLogger("igfunnel.sources")

PAGE_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 5
MAX_ITEMS_HARD_CAP = 200
ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

from app.tasks.celery_app import celery


def should_take_media(media_type: int, product_type: str, reels_only: bool) -> "tuple[bool, str]":
    """Pure gate: which IG media become Video rows. Unit-tested.

    Only single-file videos are ingestible (photos can't be processed,
    albums are multi-file). reels_only narrows further to clips.
    """
    product = (product_type or "").lower()
    if media_type == 1:
        return False, "photo — video pipeline only"
    if media_type == 8:
        return False, "album — multi-file, unsupported"
    if media_type != 2:
        return False, f"unsupported media_type={media_type}"
    if reels_only and product != "clips":
        return False, "not a reel (feed video)"
    return True, ""


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _publish(source_id: int):
    try:
        from app.tasks.sync_helpers import publish_sync

        publish_sync("video_source_update", {"source_id": source_id})
    except Exception:
        pass


def _bump(s, source, **kw):
    for k, v in kw.items():
        setattr(source, k, v)
    s.commit()


def _stopped(s, source_id: int) -> bool:
    from app.models import SourceStatus, VideoSource

    row = s.get(VideoSource, source_id)
    return row is None or row.status == SourceStatus.stopping


def _sleep_chunked(s, source_id: int, seconds: float) -> bool:
    """Sleep in 2s slices so Stop lands fast. Returns True if stop requested."""
    end = time.time() + max(seconds, 0)
    while time.time() < end:
        if _stopped(s, source_id):
            return True
        time.sleep(min(2.0, end - time.time()))
    return _stopped(s, source_id)


def _md5_of(path: str) -> "tuple[int, str]":
    h = hashlib.md5()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            size += len(chunk)
            h.update(chunk)
    return size, h.hexdigest()


def _convert_cover(src: str, dst: str) -> bool:
    import subprocess

    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-q:v", "3", dst],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
        return r.returncode == 0 and os.path.exists(dst)
    except Exception:
        return False


def _finish(s, source, status, error: "str | None" = None):
    from app.models import SourceStatus
    from app.tasks.sync_helpers import log_event_sync

    _bump(s, source, status=status, finished_at=_now(),
          last_error=(error[:1000] if error else None), current_stage=None)
    msg = f"Source @{source.username}: {status.value}" + (f" — {error}" if error else "")
    log_event_sync("INFO" if status == SourceStatus.completed else "ERROR", "source", msg,
                   {"source_id": source.id})
    _publish(source.id)


@celery.task(name="tasks.source_tasks.ingest_source", bind=True)
def ingest_source(self, source_id: int):
    """Beat/API entry: ingest one page until max reached, cursor exhausted,
    stopped, or aborted. Resumable via end_cursor + SourceItem dedupe."""
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import (
        Account, AccountStatus, SourceItem, SourceItemStatus, SourceStatus, Video, VideoStatus,
        VideoSource,
    )
    from app.services.instagram_service import InstagramService, _classify
    from app.services.video_processor import media_dirs
    from app.tasks import sync_helpers as sched
    from app.tasks.sync_helpers import log_event_sync
    from app.utils import ffmpeg as ff
    from app.utils.instagram_helpers import session_path_for

    def fail(s, source, error: str):
        _finish(s, source, SourceStatus.failed, error)
        return {"source_id": source_id, "status": "failed", "error": error}

    try:
        with SyncSessionLocal() as s:
            source = s.get(VideoSource, source_id)
            if source is None:
                return {"error": "source not found"}
            if source.status != SourceStatus.running:
                return {"status": source.status.value, "note": "not claimed"}
            _bump(s, source, started_at=_now(), finished_at=None, last_error=None,
                  current_stage="resolving download account")

            # --- download account: explicit, else first active one with a session.
            acc = None
            if source.account_id:
                acc = s.get(Account, source.account_id)
                if acc is None or acc.status != AccountStatus.active:
                    return fail(s, source, "Download account missing or not active")
            else:
                cands = s.execute(
                    select(Account).where(Account.status == AccountStatus.active)
                    .order_by(Account.id)
                ).scalars().all()
                for c in cands:
                    if os.path.exists(session_path_for(c.username, settings.MEDIA_ROOT)):
                        acc = c
                        break
                if acc is None:
                    return fail(s, source, "No download account: upload a session JSON to an account first")
            if not sched.account_reachable(s, acc):
                return fail(s, source, "No healthy proxy route for the download account")
            username, password = acc.username, decrypt_secret(acc.password_enc)
            purl = sched.resolve_proxy_url(s, acc)
            spath = acc.session_file_path or session_path_for(username, settings.MEDIA_ROOT)
            if not os.path.exists(spath):
                return fail(s, source, f"Download account @{username} has no session file")

            svc = InstagramService(proxy_url=purl, session_path=spath)
            # Bulk CDN pulls of multi-MB reels need a generous per-read
            # timeout (instagrapi defaults to 1s — stalls kill downloads).
            cl = svc._make_client(username, request_timeout=60)
            # Session-first check via the shared helper (same as profile ops).
            from app.services.instagram_service import _feed_with_retry

            feed_ok, feed_kind = _feed_with_retry(cl)
            if not feed_ok:
                try:
                    cl.login(username, password)
                    try:
                        cl.dump_settings(spath)
                    except Exception:
                        pass
                except Exception as exc:
                    return fail(s, source, f"login failed: {_classify(exc)}: {exc}")

            # --- resolve the target page.
            _bump(s, source, current_stage=f"resolving @{source.username}")
            try:
                target_id = cl.user_id_from_username(source.username)
            except Exception as exc:
                return fail(s, source, f"page @{source.username} not found: {_classify(exc)}")
            try:
                info = cl.user_info(target_id)
            except Exception as exc:
                return fail(s, source, f"could not read page: {_classify(exc)}: {exc}")
            if getattr(info, "is_private", False):
                return fail(s, source, f"@{source.username} is private — follow it from the official app first")

            dirs = media_dirs()
            max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
            cursor = source.end_cursor
            run_downloaded = 0
            consec_fail = 0
            page = 0
            exhausted = False
            seen_cursors: set = set()

            while True:
                if _stopped(s, source_id):
                    _bump(s, source, status=SourceStatus.idle, finished_at=_now(),
                          current_stage=None)
                    log_event_sync("INFO", "source", f"Source @{source.username} stopped",
                                   {"source_id": source_id})
                    _publish(source_id)
                    return {"source_id": source_id, "status": "stopped"}
                if run_downloaded >= min(source.max_items, MAX_ITEMS_HARD_CAP):
                    _finish(s, source, SourceStatus.completed)
                    return {"source_id": source_id, "status": "completed"}

                page += 1
                _bump(s, source, current_stage=f"listing page {page}")
                try:
                    medias, cursor = cl.user_medias_paginated(
                        target_id, PAGE_SIZE, end_cursor=cursor or "")
                except Exception as exc:
                    kind = _classify(exc)
                    if kind in ("challenge", "login_required"):
                        return fail(s, source, f"listing blocked ({kind}): {exc}")
                    consec_fail += 1
                    if consec_fail >= MAX_CONSECUTIVE_FAILURES:
                        return fail(s, source, f"listing failed {consec_fail}x: {exc}")
                    _sleep_chunked(s, source_id, 30)
                    continue
                consec_fail = 0
                if not medias:
                    exhausted = True
                    break
                _bump(s, source, end_cursor=cursor,
                      fetched=(source.fetched or 0) + len(medias))
                if not cursor or cursor in seen_cursors:
                    # Falsy cursor = last page; repeated cursor = API loop —
                    # process this page, then stop instead of paging forever.
                    exhausted = True
                seen_cursors.add(cursor)

                for m in medias:
                    if _stopped(s, source_id) or run_downloaded >= min(source.max_items, MAX_ITEMS_HARD_CAP):
                        break
                    pk = str(getattr(m, "pk", "") or "")
                    if not pk:
                        continue
                    exists = s.execute(
                        select(SourceItem.id).where(
                            SourceItem.source_id == source_id, SourceItem.media_pk == pk)
                    ).first()
                    if exists:
                        continue
                    shortcode = getattr(m, "code", None)
                    mtype = getattr(m, "media_type", 0) or 0
                    ptype = getattr(m, "product_type", "") or ""
                    item = SourceItem(source_id=source_id, media_pk=pk,
                                      shortcode=shortcode, media_type=str(mtype))
                    s.add(item)
                    s.commit()

                    take, reason = should_take_media(mtype, ptype, source.reels_only)
                    if not take:
                        item.status = SourceItemStatus.skipped
                        item.error = reason
                        s.commit()
                        _bump(s, source, skipped=(source.skipped or 0) + 1)
                        _publish(source_id)
                        continue

                    item.status = SourceItemStatus.downloading
                    s.commit()
                    _bump(s, source, current_stage=f"downloading @{source.username} #{shortcode or pk}")
                    try:
                        from pathlib import Path

                        pk_int = int(pk)
                        dl_dir = Path(dirs["raw"]) / f"src_{source_id}_{pk}"
                        dl_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            if ptype.lower() == "clips":
                                got = cl.clip_download(pk_int, dl_dir)
                            else:
                                got = cl.video_download(pk_int, dl_dir)
                        except AttributeError:
                            # Older instagrapi without clip_download: fall back.
                            got = cl.video_download(pk_int, dl_dir)
                        got_path = str(got)
                        ext = os.path.splitext(got_path)[1].lower() or ".mp4"
                        if ext not in ALLOWED_EXT:
                            raise ValueError(f"unsupported container {ext}")
                        size = os.path.getsize(got_path)
                        if size == 0:
                            raise ValueError("empty download")
                        if size > max_bytes:
                            raise ValueError(f"file exceeds {settings.MAX_UPLOAD_MB}MB limit")
                        dest = os.path.join(dirs["raw"], f"{uuid.uuid4().hex}{ext}")
                        shutil.move(got_path, dest)
                        try:
                            shutil.rmtree(dl_dir, ignore_errors=True)
                        except Exception:
                            pass
                        size, digest = _md5_of(dest)
                        dup = s.execute(
                            select(Video.id, Video.original_filename).where(Video.md5_hash == digest)
                        ).first()
                        if dup:
                            os.remove(dest)
                            raise ValueError(f"duplicate of video #{dup[0]}")
                        try:
                            probe = ff.probe_sync(dest)
                        except Exception:
                            os.remove(dest)
                            raise ValueError("ffprobe validation failed")
                        # Cover = the post's own IG cover art.
                        cover_path = None
                        if source.with_covers:
                            try:
                                from pathlib import Path as _Path

                                cdir = _Path(dirs["thumbnails"]) / f"srccov_{source_id}_{pk}"
                                cdir.mkdir(parents=True, exist_ok=True)
                                cgot = str(cl.photo_download(pk_int, cdir))
                                cext = os.path.splitext(cgot)[1].lower()
                                cdst = os.path.join(dirs["thumbnails"], f"custom_{uuid.uuid4().hex}.jpg")
                                if cext in (".jpg", ".jpeg"):
                                    shutil.move(cgot, cdst)
                                else:
                                    ok_cov = _convert_cover(cgot, cdst)
                                    if not ok_cov:
                                        raise ValueError("cover convert failed")
                                try:
                                    shutil.rmtree(cdir, ignore_errors=True)
                                except Exception:
                                    pass
                                cover_path = cdst
                            except Exception as exc:
                                log.warning("source %s cover failed for %s: %s", source_id, pk, exc)
                        caption = (getattr(m, "caption_text", "") or "")[:4000] or None
                        fname = f"{source.username}_{shortcode or pk}.mp4"[:500]
                        video = Video(
                            original_filename=fname, raw_path=dest,
                            file_size=size, md5_hash=digest,
                            duration=(probe or {}).get("duration"),
                            custom_thumbnail_path=cover_path,
                            source_caption=caption,
                        )
                        s.add(video)
                        s.flush()
                        item.status = SourceItemStatus.downloaded
                        item.video_id = video.id
                        item.error = None
                        s.commit()
                        _bump(s, source, downloaded=(source.downloaded or 0) + 1)
                        run_downloaded += 1
                        consec_fail = 0
                        log_event_sync("INFO", "video",
                                       f"Sourced {fname} (#{video.id}) from @{source.username}",
                                       {"source_id": source_id, "video_id": video.id})
                        if source.auto_process:
                            from app.tasks.video_tasks import process_video_task

                            process_video_task.delay(video.id)
                    except Exception as exc:
                        kind = _classify(exc)
                        item.status = SourceItemStatus.failed
                        item.error = f"{kind}: {exc}"[:1000]
                        s.commit()
                        _bump(s, source, failed_count=(source.failed_count or 0) + 1)
                        if kind in ("challenge", "login_required"):
                            return fail(s, source, f"download blocked ({kind}): {exc}")
                        consec_fail += 1
                        if consec_fail >= MAX_CONSECUTIVE_FAILURES:
                            return fail(s, source,
                                        f"{consec_fail} consecutive failures, stopping to protect the account: {exc}")
                    _publish(source_id)
                    if _sleep_chunked(s, source_id, random.uniform(source.delay_min_s, source.delay_max_s)):
                        break

                if exhausted:
                    break

            _finish(s, source, SourceStatus.completed)
            return {"source_id": source_id, "status": "completed",
                    "exhausted": exhausted, "downloaded_this_run": run_downloaded}
    except Exception as exc:  # noqa: BLE001
        log.exception("ingest_source %s failed", source_id)
        try:
            with SyncSessionLocal() as s2:
                source2 = s2.get(VideoSource, source_id)
                if source2 is not None:
                    _finish(s2, source2, SourceStatus.failed, str(exc))
        except Exception:
            pass
        return {"source_id": source_id, "status": "failed", "error": str(exc)}
