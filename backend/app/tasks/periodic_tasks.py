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
        from app.tasks.sync_helpers import (
            PROXY_CHECK_BATCH,
            PROXY_VERIFY_LIMIT,
            SWEEP_TCP_TIMEOUT,
            due_for_check,
        )

        with SyncSessionLocal() as s:
            # Oldest-checked first (never-checked lead), capped per cycle —
            # a 300-row pool drains over several 30-min ticks instead of
            # pinning the solo worker for a quarter hour and stalling posts.
            # Disabled rows are included so recoveries surface for re-enable.
            ids = due_for_check(s, PROXY_CHECK_BATCH)
        swept, verified = 0, 0
        for pid in ids:
            # Snapshot credentials first, then check WITHOUT holding the DB
            # transaction open — network checks must never pin a connection
            # (SQLite lock contention / PG idle-in-transaction).
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                snap = (p.url, p.username, p.password_enc)
            probe = SimpleNamespace(id=pid, url=snap[0], username=snap[1], password_enc=snap[2])
            # Tier 1 — fast TCP sweep (seconds, not tens of seconds).
            ok, latency = check_proxy_sync(probe, tcp_timeout=SWEEP_TCP_TIMEOUT, sweep_only=True)
            swept += 1
            if not ok:
                with SyncSessionLocal() as s:
                    p = s.get(Proxy, pid)
                    if p is not None:
                        record_proxy_check(s, p, False, error="tcp sweep failed")
                continue
            # Tier 2 — full end-to-end, but only for the first survivors each
            # cycle; the rest wait for the next tick (their sweep already
            # proved TCP liveness, so streaks stay honest).
            if verified >= PROXY_VERIFY_LIMIT:
                continue
            ok, latency = check_proxy_sync(probe)
            verified += 1
            # One shared recorder for checker AND live-traffic observations —
            # same streak, same threshold, same parking behavior.
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                record_proxy_check(s, p, ok, latency_ms=latency,
                                   error="" if ok else "periodic check failed")
        log_event_sync("INFO", "system", f"Proxy health check: {swept} swept, {verified} verified")
        return {"swept": swept, "verified": verified}
    except Exception:  # noqa: BLE001
        log.exception("check_all_proxies failed")
        return {"error": "failed"}


@celery.task(name="tasks.proxy_tasks.refresh_proxy_pool")
def refresh_proxy_pool():
    """Auto-pool refresh: fetch enabled sources, insert healthy-candidate rows.

    Insert is cheap and untrusted input goes through the strict line parser;
    actual health is decided later by the 30-min checker. Single-location
    policy (pool_country + pool_require_country Settings) gates inserts.
    Stale auto rows are reaped; manual rows are never touched.
    """
    import random
    import time

    from sqlalchemy import select

    from app.core.security import encrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Proxy, ProxyProtocol, ProxySource
    from app.services.proxy_service import (
        MAX_IMPORT_LINES,
        parse_proxy_line,
        proxy_fingerprint,
    )
    from app.tasks import sync_helpers as sched
    from app.tasks.sync_helpers import (
        POOL_MAX_NEW_PER_SOURCE,
        POOL_REQUIRE_COUNTRY_KEY,
        POOL_COUNTRY_KEY,
        log_event_sync,
        purge_stale_auto_proxies,
    )

    try:
        time.sleep(random.uniform(0, 120))
        with SyncSessionLocal() as s:
            sources = s.execute(
                select(ProxySource).where(ProxySource.is_active.is_(True))
            ).scalars().all()
            snap = [(x.id, x.name, x.url, x.default_protocol, x.default_country) for x in sources]
            pool_country = sched.get_setting(s, POOL_COUNTRY_KEY, "")
            require = sched.get_setting(s, POOL_REQUIRE_COUNTRY_KEY, "false").lower() == "true"
            have = set()
            for p in s.execute(select(Proxy)).scalars().all():
                known, _e = parse_proxy_line(p.url, "http")
                if known:
                    have.add(proxy_fingerprint(known["scheme"], known["host"], known["port"]))
        if not snap:
            return {"sources": 0}
        import httpx

        total_added = 0
        per_source = []
        for sid, name, url, proto, country in snap:
            added = total = 0
            err = ""
            try:
                if not url.lower().startswith(("http://", "https://")):
                    raise ValueError("source URL must be http(s)")
                with httpx.Client(timeout=30, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    if len(resp.content) > 1024 * 1024:
                        raise ValueError("list exceeds 1MB")
                    lines = resp.text.splitlines()[:MAX_IMPORT_LINES]
                total = len(lines)
                with SyncSessionLocal() as s:
                    made = 0
                    for line in lines:
                        spec, _e = parse_proxy_line(line, proto or "http")
                        if spec is None:
                            continue
                        if not sched.pool_allows_country(
                            spec["country"], country or "", pool_country, require
                        ):
                            continue
                        key = proxy_fingerprint(spec["scheme"], spec["host"], spec["port"])
                        if key in have:
                            continue
                        try:
                            penum = ProxyProtocol(spec["scheme"] if spec["scheme"] != "https" else "http")
                        except ValueError:
                            continue
                        s.add(Proxy(
                            url=f"{spec['scheme']}://{spec['host']}:{spec['port']}",
                            protocol=penum,
                            username=spec["username"] or None,
                            password_enc=encrypt_secret(spec["password"]) if spec["password"] else None,
                            country=spec["country"] or (country or None),
                            source=name,
                        ))
                        have.add(key)
                        made += 1
                        if made >= POOL_MAX_NEW_PER_SOURCE:
                            break
                    src = s.get(ProxySource, sid)
                    if src is not None:
                        src.last_fetch_at = dt.datetime.now(dt.timezone.utc)
                        src.last_added = made
                        src.last_total = total
                    s.commit()
                    added = made
            except Exception as exc:  # noqa: BLE001 — one bad source must not kill the cycle
                err = str(exc)[:300]
                log.exception("proxy source %s fetch failed", name)
            per_source.append({"source": name, "added": added, "lines": total, "error": err})
            total_added += added
        with SyncSessionLocal() as s:
            purged = purge_stale_auto_proxies(s)
        log_event_sync("INFO", "proxy", f"Pool refresh: {total_added} added, {purged} stale purged")
        return {"added": total_added, "purged": purged, "sources": per_source}
    except Exception:  # noqa: BLE001
        log.exception("refresh_proxy_pool failed")
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
