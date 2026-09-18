"""Bios, proxies, effects."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, BioConfig, EffectPreset, Proxy, ProxyProtocol
from app.schemas.account import ProxyCreate, ProxyOut, ProxyUpdate
from app.schemas.content import BioIn, BioOut, EffectIn, EffectOut
from app.services.log_service import log_event

bio_router = APIRouter()
proxy_router = APIRouter()
effect_router = APIRouter()


# ---- Bios ----

@bio_router.get("", response_model=list[BioOut])
async def list_bios(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BioConfig))).scalars().all()
    return [BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied) for b in rows]


@bio_router.post("", response_model=BioOut, status_code=201)
async def create_bio(body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, body.account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    b = BioConfig(**body.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied)


@bio_router.put("/{bid}", response_model=BioOut)
async def update_bio(bid: int, body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    await db.commit()
    await db.refresh(b)
    return BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied)


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
    import concurrent.futures

    from app.config import settings
    from app.services.instagram_service import InstagramService
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        b = await db.get(BioConfig, bid)
        if not b:
            raise HTTPException(404, "Bio not found")
        acc = await db.get(Account, b.account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        username, password, text, link = acc.username, decrypt_secret(acc.password_enc), b.text, b.link_url
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        err = pool.submit(
            InstagramService(session_path=session_path_for(username, settings.MEDIA_ROOT)).apply_bio,
            username, password, text, link or "",
        ).result(timeout=180)
    if err:
        raise HTTPException(502, f"Bio apply failed: {err}")
    async with SessionLocal() as db:
        b = await db.get(BioConfig, bid)
        if b:
            b.last_applied = dt.datetime.now(dt.timezone.utc)
            await db.commit()
    await log_event("INFO", "account", f"Bio force-applied to account {acc.id if 'acc' in dir() else ''}")
    return {"ok": True}


@bio_router.get("/{bid}/history")
async def bio_history(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import SystemLog

    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    rows = (
        await db.execute(
            select(SystemLog).where(SystemLog.category == "account").order_by(SystemLog.timestamp.desc()).limit(50)
        )
    ).scalars().all()
    return [{"message": r.message, "timestamp": r.timestamp} for r in rows]


# ---- Proxies ----

def _proxy_out(p: Proxy) -> ProxyOut:
    return ProxyOut(
        id=p.id, url=p.url, protocol=p.protocol.value, username=p.username, country=p.country,
        is_healthy=p.is_healthy, last_checked=p.last_checked, fail_count=p.fail_count,
        latency_ms=p.latency_ms, is_active=p.is_active, created_at=p.created_at,
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
              password_enc=encrypt_secret(body.password) if body.password else None, country=body.country)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _proxy_out(p)


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
