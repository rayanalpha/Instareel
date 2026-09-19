"""Periodic tasks â€” all fully synchronous (Celery-safe, no event loop)."""
import datetime as dt
import logging
import os

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks")


# Max posts refreshed per analytics run — the rest wait for the next 4h
# tick. Bounds IG API calls and spreads them instead of bursting.
MAX_ANALYTICS_PER_RUN = 20
# Skip posts checked more recently than this (hours).
ANALYTICS_MIN_INTERVAL_HOURS = 3


@celery.task(name="tasks.analytics_tasks.fetch_all_analytics")
def fetch_all_analytics():
    import random
    import time

    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, Post, PostStatus
    from app.services.instagram_service import InstagramService
    from app.tasks import sync_helpers as sched
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        # Jitter the start so runs don't hit IG at the exact same minute daily.
        time.sleep(random.uniform(0, 90))
        now = dt.datetime.now(dt.timezone.utc)
        cutoff = now - dt.timedelta(days=7)
        recent = now - dt.timedelta(hours=ANALYTICS_MIN_INTERVAL_HOURS)
        with SyncSessionLocal() as s:
            posts = (
                s.execute(
                    select(Post)
                    .where(Post.status == PostStatus.posted, Post.posted_at >= cutoff)
                    .order_by(Post.last_analytics_check.asc().nulls_first())
                    .limit(MAX_ANALYTICS_PER_RUN * 2)
                )
            ).scalars().all()
            items = [
                (p.id, p.account_id, p.ig_media_id, p.posted_at)
                for p in posts
                if (last := sched.as_aware_utc(p.last_analytics_check)) is None or last <= recent
            ][:MAX_ANALYTICS_PER_RUN]
        updated = 0
        for pid, acc_id, media_id, posted_at in items:
            # Human-like pacing between API calls instead of a tight loop.
            time.sleep(random.uniform(3, 10))
            if not media_id:
                continue
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    if sched.account_age_days(acc.created_at) < sched.BIO_MIN_AGE_DAYS:
                        continue
                    if not sched.account_reachable(s, acc):
                        continue
                    username, password = acc.username, decrypt_secret(acc.password_enc)
                    purl = sched.resolve_proxy_url(s, acc)
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
    import random
    import time

    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, BioConfig
    from app.services.instagram_service import InstagramService
    from app.tasks import sync_helpers as sched
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        # Jitter the daily 6am firing so edits don't land at the same minute.
        time.sleep(random.uniform(0, 120))
        now = dt.datetime.now(dt.timezone.utc)
        with SyncSessionLocal() as s:
            bios = s.execute(select(BioConfig).where(BioConfig.is_active.is_(True))).scalars().all()
            due = []
            for b in bios:
                last = sched.as_aware_utc(b.last_applied)
                if last is None or (now - last).days >= b.rotation_interval_days:
                    due.append(b)
            items = [
                (b.id, b.account_id, b.text, b.link_url, b.full_name, b.profile_pic_path, b.make_private)
                for b in due
            ]
        applied = 0
        for bid, acc_id, text, link, full_name, pic, private in items:
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    if sched.account_age_days(acc.created_at) < sched.BIO_MIN_AGE_DAYS:
                        continue
                    if not sched.account_reachable(s, acc):
                        continue
                    username = acc.username
                    password = decrypt_secret(acc.password_enc)
                    purl = sched.resolve_proxy_url(s, acc)
                # Same egress IP as posts — bio edits from a different IP than
                # uploads is an easy automation tell.
                svc = InstagramService(
                    proxy_url=purl, session_path=session_path_for(username, settings.MEDIA_ROOT)
                )
                err = svc.apply_profile(
                    username, password, biography=text, external_url=link or "",
                    full_name=full_name or "", make_private=private, picture_path=pic,
                )
                if not err:
                    with SyncSessionLocal() as s:
                        b = s.get(BioConfig, bid)
                        if b:
                            b.last_applied = now
                            s.commit()
                    applied += 1
                    log_event_sync("INFO", "account", f"Bio rotated for account {acc_id}", {"bio_id": bid})
            except Exception:
                log.exception("bio rotation failed for %s", bid)
        return {"due": len(items), "applied": applied}
    except Exception:  # noqa: BLE001
        log.exception("check_bio_rotation failed")
        return {"error": "failed"}


@celery.task(name="tasks.proxy_tasks.check_all_proxies")
def check_all_proxies():
    import random
    import time
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Proxy
    from app.services.proxy_service import check_proxy_sync
    from app.tasks.sync_helpers import log_event_sync, record_proxy_check

    try:
        # Small jitter so the check doesn't fire at the exact same second as
        # the posting tick every half hour (less machine-like fingerprint).
        time.sleep(random.uniform(0, 60))
        with SyncSessionLocal() as s:
            # Check every proxy, including auto-disabled ones, so a recovered
            # proxy shows fresh health data for the admin to re-enable.
            ids = [p.id for p in s.execute(select(Proxy)).scalars().all()]
        results = []
        for pid in ids:
            # Snapshot credentials first, then check WITHOUT holding the DB
            # transaction open — a 10-25s network check must never pin a
            # connection (SQLite lock contention / PG idle-in-transaction).
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                snap = (p.url, p.username, p.password_enc)
            probe = SimpleNamespace(id=pid, url=snap[0], username=snap[1], password_enc=snap[2])
            ok, latency = check_proxy_sync(probe)
            # One shared recorder for checker AND live-traffic observations —
            # same streak, same threshold, same parking behavior.
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                record_proxy_check(s, p, ok, latency_ms=latency,
                                   error="" if ok else "periodic check failed")
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
