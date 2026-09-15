"""Periodic tasks â€” all fully synchronous (Celery-safe, no event loop)."""
import datetime as dt
import logging
import os

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks")


@celery.task(name="tasks.analytics_tasks.fetch_all_analytics")
def fetch_all_analytics():
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, Post, PostStatus, Proxy
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        with SyncSessionLocal() as s:
            posts = (
                s.execute(
                    select(Post).where(Post.status == PostStatus.posted, Post.posted_at >= cutoff)
                )
            ).scalars().all()
            items = [(p.id, p.account_id, p.ig_media_id, p.posted_at) for p in posts]
        updated = 0
        for pid, acc_id, media_id, posted_at in items:
            if not media_id:
                continue
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    proxy = s.get(Proxy, acc.proxy_id) if acc.proxy_id else None
                    username = acc.username
                    password = decrypt_secret(acc.password_enc)
                    purl = proxy_url_for(proxy) if proxy else None
                svc = InstagramService(
                    proxy_url=purl, session_path=session_path_for(username, settings.MEDIA_ROOT)
                )
                info = svc.media_info(username, media_id)
                likes = info.get("like_count", 0)
                comments = info.get("comment_count", 0)
                views = info.get("view_count", 0)
                age_h = max(
                    1,
                    (dt.datetime.now(dt.timezone.utc) - (posted_at or dt.datetime.now(dt.timezone.utc))).total_seconds() / 3600,
                )
                eng = round((likes + comments) / max(1, views) * 100, 2) if views else 0.0
                with SyncSessionLocal() as s:
                    p = s.get(Post, pid)
                    if p:
                        if age_h <= 1.5:
                            p.views_1h, p.likes_1h = views, likes
                        if age_h <= 8:
                            p.views_6h = views
                        if age_h <= 30:
                            p.views_24h, p.likes_24h, p.comments_24h = views, likes, comments
                        if age_h <= 54:
                            p.views_48h = views
                        p.views_7d, p.likes_7d, p.comments_7d = views, likes, comments
                        p.engagement_rate = eng
                        p.last_analytics_check = dt.datetime.now(dt.timezone.utc)
                        s.commit()
                        updated += 1
            except Exception:
                log.exception("analytics fetch failed for post %s", pid)
        log_event_sync("INFO", "system", f"Analytics refresh: {updated} posts updated")
        return {"updated": updated}
    except Exception:  # noqa: BLE001
        log.exception("fetch_all_analytics failed")
        return {"error": "failed"}


@celery.task(name="tasks.bio_tasks.check_bio_rotation")
def check_bio_rotation():
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, BioConfig
    from app.services.instagram_service import InstagramService
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        now = dt.datetime.now(dt.timezone.utc)
        with SyncSessionLocal() as s:
            bios = s.execute(select(BioConfig).where(BioConfig.is_active.is_(True))).scalars().all()
            due = [b for b in bios if not b.last_applied or (now - b.last_applied).days >= b.rotation_interval_days]
            items = [(b.id, b.account_id, b.text, b.link_url) for b in due]
        applied = 0
        for bid, acc_id, text, link in items:
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    username, password = acc.username, decrypt_secret(acc.password_enc)
                svc = InstagramService(session_path=session_path_for(username, settings.MEDIA_ROOT))
                err = svc.apply_bio(username, password, text, link or "")
                if not err:
                    with SyncSessionLocal() as s:
                        b = s.get(BioConfig, bid)
                        if b:
                            b.last_applied = now
                            s.commit()
                    applied += 1
                    log_event_sync("INFO", "account", f"Bio rotated for account {acc_id}")
            except Exception:
                log.exception("bio rotation failed for %s", bid)
        return {"due": len(items), "applied": applied}
    except Exception:  # noqa: BLE001
        log.exception("check_bio_rotation failed")
        return {"error": "failed"}


@celery.task(name="tasks.proxy_tasks.check_all_proxies")
def check_all_proxies():
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Proxy
    from app.services.proxy_service import check_proxy_sync
    from app.tasks.sync_helpers import log_event_sync

    try:
        with SyncSessionLocal() as s:
            proxies = s.execute(select(Proxy).where(Proxy.is_active.is_(True))).scalars().all()
            ids = [p.id for p in proxies]
        results = []
        for pid in ids:
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                ok, latency = check_proxy_sync(p)
                p.is_healthy = ok
                p.latency_ms = latency
                p.last_checked = dt.datetime.now(dt.timezone.utc)
                p.fail_count = 0 if ok else p.fail_count + 1
                s.commit()
                results.append({"id": pid, "healthy": ok})
        log_event_sync("INFO", "system", f"Proxy health check: {len(results)} checked")
        return results
    except Exception:  # noqa: BLE001
        log.exception("check_all_proxies failed")
        return {"error": "failed"}


@celery.task(name="tasks.cleanup_tasks.clean_old_media")
def clean_old_media(days: int = 30):
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Video, VideoStatus
    from app.tasks.sync_helpers import log_event_sync

    try:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        with SyncSessionLocal() as s:
            olds = (
                s.execute(
                    select(Video).where(Video.status == VideoStatus.posted, Video.processed_at < cutoff)
                )
            ).scalars().all()
            removed = 0
            for v in olds:
                for path in (v.raw_path, v.processed_path):
                    try:
                        if path and os.path.exists(path):
                            os.remove(path)
                            removed += 1
                    except OSError:
                        pass
                v.status = VideoStatus.archived
            s.commit()
        log_event_sync("INFO", "system", f"Media cleanup: {removed} files removed")
        return {"removed": removed}
    except Exception:  # noqa: BLE001
        log.exception("clean_old_media failed")
        return {"error": "failed"}


@celery.task(name="tasks.account_tasks.reset_daily_counts")
def reset_daily_counts():
    from sqlalchemy import update

    from app.database import SyncSessionLocal
    from app.models import Account
    from app.tasks.sync_helpers import log_event_sync

    try:
        with SyncSessionLocal() as s:
            s.execute(update(Account).values(posts_today=0))
            s.commit()
        log_event_sync("INFO", "system", "Daily post counts reset")
        return {"ok": True}
    except Exception:  # noqa: BLE001
        log.exception("reset_daily_counts failed")
        return {"error": "failed"}
