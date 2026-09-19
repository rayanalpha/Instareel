"""Bios, proxies, effects, audio tracks."""
import datetime as dt
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, AudioTrack, BioConfig, EffectPreset, Proxy, ProxyProtocol, ProxySource
from app.schemas.account import ProxyCreate, ProxyOut, ProxyUpdate
from app.schemas.content import (
    AudioIn, AudioOut, BioIn, BioOut, EffectIn, EffectOut, ProxySourceIn, ProxySourceOut,
)
from app.services.log_service import log_event

bio_router = APIRouter()
proxy_router = APIRouter()
effect_router = APIRouter()
audio_router = APIRouter()

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
MAX_AUDIO_BYTES = 50 * 1024 * 1024


def _audio_out(t: AudioTrack) -> AudioOut:
    return AudioOut(
        id=t.id, name=t.name, description=t.description, music_volume=t.music_volume,
        duck_original=t.duck_original, is_active=t.is_active, file_path=t.file_path,
        duration=t.duration, use_count=t.use_count, avg_engagement=t.avg_engagement,
    )


# ---- Bios (bio text + link + full name + picture + privacy) ----

def _bio_out(b: BioConfig) -> BioOut:
    import os as _os

    return BioOut(
        id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url,
        full_name=b.full_name or "", make_private=b.make_private,
        is_active=b.is_active, rotation_interval_days=b.rotation_interval_days,
        profile_pic_path=b.profile_pic_path,
        has_picture=bool(b.profile_pic_path and _os.path.exists(b.profile_pic_path)),
        last_applied=b.last_applied,
    )


@bio_router.get("", response_model=list[BioOut])
async def list_bios(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BioConfig))).scalars().all()
    return [_bio_out(b) for b in rows]


@bio_router.post("", response_model=BioOut, status_code=201)
async def create_bio(body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, body.account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    b = BioConfig(**body.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return _bio_out(b)


@bio_router.put("/{bid}", response_model=BioOut)
async def update_bio(bid: int, body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    await db.commit()
    await db.refresh(b)
    return _bio_out(b)


@bio_router.delete("/{bid}", status_code=204)
async def delete_bio(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    await db.delete(b)
    await db.commit()
    return None


@bio_router.post("/{bid}/apply")
async def apply_bio(bid: int, _: str = Depends(get_current_admin)):
    """Apply the full profile now: bio + link + full name + picture + privacy."""
    import concurrent.futures

    from app.config import settings
    from app.services.instagram_service import InstagramService
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        from app.tasks import sync_helpers as sched

        b = await db.get(BioConfig, bid)
        if not b:
            raise HTTPException(404, "Bio not found")
        acc = await db.get(Account, b.account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        if not sched.account_reachable(db, acc):
            raise HTTPException(409, "No healthy proxy route for this account right now")
        username, password = acc.username, decrypt_secret(acc.password_enc)
        purl = sched.resolve_proxy_url(db, acc)
        bio_text: str = b.text
        link: str = b.link_url or ""
        full_name: str = b.full_name or ""
        make_private: bool | None = b.make_private
        picture: str | None = b.profile_pic_path
        acc_id = acc.id
    svc = InstagramService(proxy_url=purl, session_path=session_path_for(username, settings.MEDIA_ROOT))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        err = pool.submit(
            svc.apply_profile, username, password,
            biography=bio_text, external_url=link, full_name=full_name,
            make_private=make_private, picture_path=picture,
        ).result(timeout=180)
    if err:
        raise HTTPException(502, f"Profile apply failed: {err}")
    async with SessionLocal() as db:
        b = await db.get(BioConfig, bid)
        if b:
            b.last_applied = dt.datetime.now(dt.timezone.utc)
            await db.commit()
    await log_event("INFO", "account", f"Profile force-applied to account {acc_id}", {"bio_id": bid})
    return {"ok": True}


PIC_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PIC_BYTES = 10 * 1024 * 1024


@bio_router.post("/{bid}/picture", response_model=BioOut)
async def upload_bio_picture(
    bid: int,
    file: UploadFile = File(...),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload the profile picture for a bio config (validated image, ≤10MB).

    Stored under media/profile_pics/ and applied on next rotation/Apply.
    """
    from app.config import settings
    from app.services.video_processor import media_dirs

    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in PIC_EXT:
        raise HTTPException(400, f"Unsupported image type {ext}. Allowed: {sorted(PIC_EXT)}")
    raw = await file.read()
    try:
        await file.close()
    except Exception:
        pass
    if not raw:
        raise HTTPException(400, "Empty file")
    if len(raw) > MAX_PIC_BYTES:
        raise HTTPException(413, "Image exceeds 10MB")
    try:
        from PIL import Image as PILImage

        with PILImage.open(__import__("io").BytesIO(raw)) as img:
            img.load()
            if img.width < 50 or img.height < 50:
                raise HTTPException(422, "Image too small (min 50×50)")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "File is not a valid image")
    dirs = media_dirs()
    tmp_name = f"bio_{bid}_{uuid.uuid4().hex}{ext}"
    dest = os.path.join(dirs["profile_pics"], tmp_name)
    old = b.profile_pic_path
    with open(dest, "wb") as f:
        f.write(raw)
    b.profile_pic_path = dest
    await db.commit()
    await db.refresh(b)
    try:
        if old and old != dest and os.path.exists(old):
            os.remove(old)
    except OSError:
        pass
    await log_event("INFO", "account", f"Profile picture uploaded for bio #{bid}")
    return _bio_out(b)


@bio_router.delete("/{bid}/picture", response_model=BioOut)
async def delete_bio_picture(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    old = b.profile_pic_path
    b.profile_pic_path = None
    await db.commit()
    await db.refresh(b)
    try:
        if old and os.path.exists(old):
            os.remove(old)
    except OSError:
        pass
    return _bio_out(b)


@bio_router.get("/{bid}/current")
async def bio_current(bid: int, _: str = Depends(get_current_admin)):
    """Read-only IG-side profile snapshot to compare against the config."""
    import concurrent.futures

    from app.config import settings
    from app.services.instagram_service import InstagramService
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        from app.tasks import sync_helpers as sched

        b = await db.get(BioConfig, bid)
        if not b:
            raise HTTPException(404, "Bio not found")
        acc = await db.get(Account, b.account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        username = acc.username
        purl = sched.resolve_proxy_url(db, acc)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        try:
            data = pool.submit(
                InstagramService(proxy_url=purl, session_path=session_path_for(username, settings.MEDIA_ROOT)).read_profile,
                username,
            ).result(timeout=120)
        except Exception as exc:
            raise HTTPException(502, f"Profile read failed: {exc}")
    return data


@bio_router.get("/{bid}/history")
async def bio_history(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import SystemLog

    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    # Only this config's own events (tagged with bio_id at write time) —
    # previously this leaked the global account log into every bio card.
    rows = (
        await db.execute(
            select(SystemLog).where(SystemLog.category == "account").order_by(SystemLog.timestamp.desc()).limit(200)
        )
    ).scalars().all()
    mine = [r for r in rows if (r.details or {}).get("bio_id") == bid][:50]
    return [{"message": r.message, "timestamp": r.timestamp} for r in mine]


# ---- Proxies ----

def _proxy_out(p: Proxy) -> ProxyOut:
    return ProxyOut(
        id=p.id, url=p.url, protocol=p.protocol.value, username=p.username, country=p.country,
        is_healthy=p.is_healthy, last_checked=p.last_checked, fail_count=p.fail_count,
        latency_ms=p.latency_ms, last_error=p.last_error, source=p.source or "manual",
        is_active=p.is_active, created_at=p.created_at,
    )


@proxy_router.get("", response_model=list[ProxyOut])
async def list_proxies(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Proxy).order_by(Proxy.id))).scalars().all()
    return [_proxy_out(p) for p in rows]


@proxy_router.post("", response_model=ProxyOut, status_code=201)
async def create_proxy(body: ProxyCreate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    try:
        proto = ProxyProtocol(body.protocol)
    except ValueError:
        raise HTTPException(400, "Invalid protocol")
    p = Proxy(url=body.url, protocol=proto, username=body.username,
              password_enc=encrypt_secret(body.password) if body.password else None, country=body.country,
              source="manual")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _proxy_out(p)


@proxy_router.post("/import")
async def import_proxies(
    file: UploadFile = File(...),
    default_protocol: str = "http",
    default_country: str = "",
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-import proxies from a text file (one per line, any shape).

    Accepted per line: host:port, scheme://host:port, user:pass@host:port,
    scheme://user:pass@host:port, host:port:user:pass — each optionally
    suffixed with " |CC" / " #CC" country tag. Lines starting with # and
    blank lines are skipped. No-auth (IP-whitelisted) lines work as-is.
    Existing host:port entries are skipped, never duplicated.
    """
    from app.services.proxy_service import MAX_IMPORT_LINES, parse_proxy_line, proxy_fingerprint

    if default_protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(400, "Invalid default_protocol")
    default_country = (default_country or "").strip().upper()[:2]
    raw = await file.read()
    try:
        await file.close()
    except Exception:
        pass
    if not raw:
        raise HTTPException(400, "Empty file")
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, "List exceeds 1MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 text")
    lines = text.splitlines()
    if len(lines) > MAX_IMPORT_LINES:
        raise HTTPException(413, f"Too many lines (max {MAX_IMPORT_LINES})")

    have = set()
    for p in (await db.execute(select(Proxy))).scalars().all():
        known, _err = parse_proxy_line(p.url, "http")
        if known:
            have.add(proxy_fingerprint(known["scheme"], known["host"], known["port"]))

    added, skipped, errors = 0, [], []
    for i, line in enumerate(lines, 1):
        spec, err = parse_proxy_line(line, default_protocol)
        if spec is None:
            if err not in ("blank/comment",):
                errors.append({"line": i, "text": line.strip()[:80], "reason": err})
            continue
        key = proxy_fingerprint(spec["scheme"], spec["host"], spec["port"])
        if key in have:
            skipped.append({"line": i, "text": line.strip()[:80], "reason": "duplicate"})
            continue
        try:
            proto = ProxyProtocol(spec["scheme"] if spec["scheme"] != "https" else "http")
        except ValueError:
            errors.append({"line": i, "text": line.strip()[:80], "reason": "bad scheme"})
            continue
        country = spec["country"] or (default_country or None)
        db.add(Proxy(
            url=f"{spec['scheme']}://{spec['host']}:{spec['port']}",
            protocol=proto,
            username=spec["username"] or None,
            password_enc=encrypt_secret(spec["password"]) if spec["password"] else None,
            country=country,
            source="manual",
        ))
        have.add(key)
        added += 1
    await db.commit()
    await log_event("INFO", "proxy", f"Bulk import: {added} added, {len(skipped)} duplicates, {len(errors)} bad lines")
    return {
        "added": added,
        "duplicates_skipped": len(skipped),
        "errors": (skipped + errors)[:100],
    }


@proxy_router.put("/{pid}", response_model=ProxyOut)
async def update_proxy(pid: int, body: ProxyUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    if body.url is not None:
        p.url = body.url
    if body.protocol is not None:
        try:
            p.protocol = ProxyProtocol(body.protocol)
        except ValueError:
            raise HTTPException(400, "Invalid protocol")
    if body.username is not None:
        p.username = body.username
    if body.password is not None:
        p.password_enc = encrypt_secret(body.password)
    if body.country is not None:
        p.country = body.country
    if body.is_active is not None:
        p.is_active = body.is_active
    await db.commit()
    await db.refresh(p)
    return _proxy_out(p)


@proxy_router.delete("/{pid}", status_code=204)
async def delete_proxy(pid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    await db.delete(p)
    await db.commit()
    return None


@proxy_router.post("/{pid}/test")
async def test_proxy(pid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt2

    from app.services.proxy_service import check_proxy

    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    ok, latency = await check_proxy(p)
    p.is_healthy = ok
    p.latency_ms = latency
    p.last_checked = dt2.datetime.now(dt2.timezone.utc)
    p.fail_count = 0 if ok else p.fail_count + 1
    await db.commit()
    return {"healthy": ok, "latency_ms": latency}


@proxy_router.post("/check-all")
async def check_all(_: str = Depends(get_current_admin)):
    from app.tasks.periodic_tasks import check_all_proxies

    check_all_proxies.delay()
    return {"queued": True}


def _source_out(x: ProxySource) -> ProxySourceOut:
    return ProxySourceOut(
        id=x.id, name=x.name, url=x.url, default_protocol=x.default_protocol,
        default_country=x.default_country or "", is_active=x.is_active,
        last_fetch_at=x.last_fetch_at, last_added=x.last_added, last_total=x.last_total,
    )


@proxy_router.get("/sources", response_model=list[ProxySourceOut])
async def list_sources(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ProxySource).order_by(ProxySource.name))).scalars().all()
    return [_source_out(x) for x in rows]


@proxy_router.post("/sources", response_model=ProxySourceOut, status_code=201)
async def create_source(body: ProxySourceIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    if body.default_protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(400, "Invalid default_protocol")
    if body.url and not body.url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Source URL must be http(s)")
    exists = (await db.execute(select(ProxySource).where(ProxySource.name == body.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Source already exists")
    x = ProxySource(
        name=body.name, url=body.url, default_protocol=body.default_protocol,
        default_country=(body.default_country or "").upper(),
    )
    db.add(x)
    await db.commit()
    await db.refresh(x)
    return _source_out(x)


@proxy_router.put("/sources/{sid}", response_model=ProxySourceOut)
async def update_source(sid: int, body: ProxySourceIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    x = await db.get(ProxySource, sid)
    if not x:
        raise HTTPException(404, "Source not found")
    if body.default_protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(400, "Invalid default_protocol")
    clash = (await db.execute(
        select(ProxySource).where(ProxySource.name == body.name, ProxySource.id != sid)
    )).scalar_one_or_none()
    if clash:
        raise HTTPException(409, "Another source already uses that name")
    # Renaming a source orphans its rows' origin label — auto rows stay
    # protected by the purge rule (source != manual), so this is display-only.
    x.name, x.url = body.name, body.url
    x.default_protocol, x.default_country = body.default_protocol, (body.default_country or "").upper()
    x.is_active = body.is_active
    await db.commit()
    await db.refresh(x)
    return _source_out(x)


@proxy_router.delete("/sources/{sid}", status_code=204)
async def delete_source(sid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    x = await db.get(ProxySource, sid)
    if not x:
        raise HTTPException(404, "Source not found")
    await db.delete(x)
    await db.commit()
    return None


@proxy_router.post("/pool/refresh")
async def refresh_pool_now(_: str = Depends(get_current_admin)):
    from app.tasks.periodic_tasks import refresh_proxy_pool

    refresh_proxy_pool.delay()
    return {"queued": True}


@proxy_router.post("/pool/purge")
async def purge_pool_now(_: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.database import SyncSessionLocal
    from app.tasks.sync_helpers import purge_stale_auto_proxies

    def _run() -> int:
        with SyncSessionLocal() as s:
            return purge_stale_auto_proxies(s)

    # The purge helper is sync (same session style as the celery tasks).
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        n = pool.submit(_run).result(timeout=120)
    await log_event("INFO", "proxy", f"Manual pool purge: {n} stale auto rows removed")
    return {"purged": n}


# ---- Effects ----

@effect_router.get("", response_model=list[EffectOut])
async def list_effects(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(EffectPreset).order_by(EffectPreset.name))).scalars().all()
    # Top up any missing built-ins (covers both fresh DBs and servers seeded
    # with an older, smaller set) so the admin can just pick — no manual
    # FFmpeg entry needed. Never touches rows the admin added/edited.
    from app.services.default_effects import missing_presets

    missing = missing_presets([e.name for e in rows])
    if missing:
        for preset in missing:
            db.add(EffectPreset(**preset))
        await db.commit()
        rows = (await db.execute(select(EffectPreset).order_by(EffectPreset.name))).scalars().all()
    return [EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement) for e in rows]


@effect_router.post("", response_model=EffectOut, status_code=201)
async def create_effect(body: EffectIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(EffectPreset).where(EffectPreset.name == body.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Effect preset already exists")
    e = EffectPreset(**body.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement)


@effect_router.put("/{eid}", response_model=EffectOut)
async def update_effect(eid: int, body: EffectIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    e = await db.get(EffectPreset, eid)
    if not e:
        raise HTTPException(404, "Effect not found")
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    await db.commit()
    await db.refresh(e)
    return EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement)


@effect_router.delete("/{eid}", status_code=204)
async def delete_effect(eid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    e = await db.get(EffectPreset, eid)
    if not e:
        raise HTTPException(404, "Effect not found")
    await db.delete(e)
    await db.commit()
    return None


# ---- Audio tracks (trending sounds mixed in at processing time) ----

@audio_router.get("", response_model=list[AudioOut])
async def list_audio(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AudioTrack).order_by(AudioTrack.name))).scalars().all()
    return [_audio_out(t) for t in rows]


@audio_router.post("/upload", response_model=AudioOut, status_code=201)
async def upload_audio(
    file: UploadFile = File(...),
    name: str = "",
    description: str = "",
    music_volume: float = 0.4,
    duck_original: bool = False,
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a trending sound (MP3/WAV/M4A/…). Validated with ffprobe, then
    eligible for automatic weighted selection at processing time."""
    import asyncio

    from app.config import settings
    from app.services.video_processor import media_dirs
    from app.utils import ffmpeg as ff

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, f"Unsupported audio type {ext}. Allowed: {sorted(AUDIO_EXT)}")
    if not (0.0 <= music_volume <= 2.0):
        raise HTTPException(400, "music_volume must be between 0.0 and 2.0")
    track_name = (name or os.path.splitext(file.filename or "track")[0]).strip()[:128]
    if not track_name:
        raise HTTPException(400, "Track name is required")
    exists = (await db.execute(select(AudioTrack).where(AudioTrack.name == track_name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Audio track already exists")
    dirs = media_dirs()
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(dirs["audio"], tmp_name)
    size = 0
    try:
        # Single streaming handle (same pattern as video upload) — one
        # open/write/close cycle instead of one per chunk.
        async with aiofiles.open(raw_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise HTTPException(413, "Audio exceeds 50MB")
                await f.write(chunk)
    except HTTPException:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        raise
    finally:
        try:
            await file.close()
        except Exception:
            pass
    if size == 0:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        raise HTTPException(400, "Empty file")
    try:
        probe = await asyncio.wait_for(asyncio.to_thread(ff.probe_sync, raw_path), timeout=60)
    except Exception:
        os.remove(raw_path)
        raise HTTPException(422, "File is not valid audio (ffprobe validation failed)")
    duration = probe.get("duration") or 0
    if duration < 1:
        os.remove(raw_path)
        raise HTTPException(422, "Audio is too short (< 1s)")
    t = AudioTrack(
        name=track_name, description=description[:2000], file_path=raw_path,
        duration=duration, music_volume=music_volume, duck_original=duck_original,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    await log_event("INFO", "audio", f"Audio track '{track_name}' uploaded ({duration:.1f}s)")
    return _audio_out(t)


@audio_router.put("/{tid}", response_model=AudioOut)
async def update_audio(tid: int, body: AudioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    t = await db.get(AudioTrack, tid)
    if not t:
        raise HTTPException(404, "Audio track not found")
    clash = (await db.execute(
        select(AudioTrack).where(AudioTrack.name == body.name, AudioTrack.id != tid)
    )).scalar_one_or_none()
    if clash:
        raise HTTPException(409, "Another track already uses that name")
    t.name = body.name
    t.description = body.description
    t.music_volume = body.music_volume
    t.duck_original = body.duck_original
    t.is_active = body.is_active
    await db.commit()
    await db.refresh(t)
    return _audio_out(t)


@audio_router.delete("/{tid}", status_code=204)
async def delete_audio(tid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    t = await db.get(AudioTrack, tid)
    if not t:
        raise HTTPException(404, "Audio track not found")
    path = t.file_path
    await db.delete(t)
    await db.commit()
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    await log_event("INFO", "audio", f"Audio track '{t.name}' deleted")
    return None
