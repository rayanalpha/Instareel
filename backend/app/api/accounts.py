"""IG accounts CRUD + session management."""
import datetime as dt
import json
import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, AccountStatus, Post, PostStatus
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.log_service import log_event

router = APIRouter()

MAX_SESSION_BYTES = 5 * 1024 * 1024


def _has_session_file(username: str, session_file_path: str | None) -> bool:
    from app.config import settings
    from app.utils.instagram_helpers import session_path_for

    path = session_file_path or session_path_for(username, settings.MEDIA_ROOT)
    return bool(path) and os.path.exists(path)


def _out(a: Account) -> AccountOut:
    return AccountOut(
        id=a.id, username=a.username, proxy_id=a.proxy_id, status=a.status.value,
        last_login=a.last_login, last_post=a.last_post, posts_today=a.posts_today,
        max_daily_posts=a.max_daily_posts, cooldown_until=a.cooldown_until,
        total_posts=a.total_posts, total_views=a.total_views, total_likes=a.total_likes,
        notes=a.notes, created_at=a.created_at, updated_at=a.updated_at,
        has_session=_has_session_file(a.username, a.session_file_path),
    )


@router.get("", response_model=list[AccountOut])
async def list_accounts(_: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    rows = (await db.execute(select(Account).order_by(Account.username))).scalars().all()
    return [_out(a) for a in rows]


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(body: AccountCreate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    from app.config import settings

    exists = (await db.execute(select(Account).where(Account.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Account already exists")
    acc = Account(
        username=body.username,
        password_enc=encrypt_secret(body.password),
        proxy_id=body.proxy_id,
        max_daily_posts=body.max_daily_posts or settings.IG_DEFAULT_MAX_DAILY_POSTS,
        notes=body.notes,
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    await log_event("INFO", "account", f"Account @{body.username} added")
    return _out(acc)


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return _out(acc)


@router.put("/{account_id}", response_model=AccountOut)
async def update_account(account_id: int, body: AccountUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    # Sentinel: {"proxy_id": "none"} unlinks the proxy. Plain null = leave unchanged.
    if body.proxy_id is not None:
        if body.proxy_id == "none":
            acc.proxy_id = None
        else:
            acc.proxy_id = int(body.proxy_id)
    if body.max_daily_posts is not None:
        acc.max_daily_posts = body.max_daily_posts
    if body.notes is not None:
        acc.notes = body.notes
    if body.status is not None:
        try:
            acc.status = AccountStatus(body.status)
        except ValueError:
            raise HTTPException(400, "Invalid status")
    await db.commit()
    await db.refresh(acc)
    return _out(acc)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    await db.delete(acc)
    await db.commit()
    await log_event("INFO", "account", f"Account @{acc.username} removed")
    return None


def _blocking_login(username: str, password: str, proxy_url: str | None, session_path: str):
    from app.services.instagram_service import InstagramService

    return InstagramService(proxy_url=proxy_url, session_path=session_path).login(username, password)


@router.post("/{account_id}/login")
async def force_login(account_id: int, _: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.config import settings
    from app.models import Proxy
    from app.services.proxy_service import proxy_url_for
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        proxy = await db.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        username, password = acc.username, decrypt_secret(acc.password_enc)
        purl = proxy_url_for(proxy) if proxy else None
        spath = session_path_for(username, settings.MEDIA_ROOT)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        ok, detail = pool.submit(_blocking_login, username, password, purl, spath).result(timeout=180)
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if acc:
            if ok:
                acc.status = AccountStatus.active
                acc.last_login = dt.datetime.now(dt.timezone.utc)
                acc.session_file_path = spath
            elif detail.startswith("challenge"):
                acc.status = AccountStatus.challenge_required
            await db.commit()
    await log_event("INFO" if ok else "WARNING", "account", f"Manual login @{username}: {detail}")
    return {"ok": ok, "detail": detail}


@router.post("/{account_id}/test-session")
async def test_session(account_id: int, _: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.config import settings
    from app.models import Proxy
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        proxy = await db.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        username = acc.username
        purl = proxy_url_for(proxy) if proxy else None
        spath = acc.session_file_path or session_path_for(username, settings.MEDIA_ROOT)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        valid = pool.submit(InstagramService(proxy_url=purl, session_path=spath).check_session, username).result(timeout=120)
    return {"valid": valid}


@router.post("/{account_id}/session")
async def upload_session(
    account_id: int,
    file: UploadFile = File(...),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db),
):
    """Upload a session JSON (created by manual_login.py / session_from_browser.py).

    Validates the payload is a JSON object containing the fields instagrapi
    needs (at minimum a cookies/authorization section), then stores it at the
    account's canonical session path.
    """
    from app.config import settings
    from app.utils.instagram_helpers import session_path_for

    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    raw = await file.read()
    try:
        await file.close()
    except Exception:
        pass
    if not raw:
        raise HTTPException(400, "Empty file")
    if len(raw) > MAX_SESSION_BYTES:
        raise HTTPException(413, "Session file too large (max 5MB)")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "File is not valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Session JSON must be an object")
    keys = set(payload.keys())
    if not ({"cookies", "authorization", "authorization_data", "uuids"} & keys):
        raise HTTPException(
            400,
            "Not an instagrapi session file (missing cookies/authorization data). "
            "Create it with backend/manual_login.py or session_from_browser.py.",
        )
    spath = session_path_for(acc.username, settings.MEDIA_ROOT)
    tmp = spath + ".tmp"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, spath)
    acc.session_file_path = spath
    await db.commit()
    await db.refresh(acc)
    await log_event("INFO", "account", f"Session uploaded for @{acc.username}")
    return {"ok": True, "detail": f"Session saved ({len(raw)} bytes). Press 'Test session' to verify."}


@router.delete("/{account_id}/session", status_code=204)
async def delete_session(account_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    spath = acc.session_file_path
    try:
        if spath and os.path.exists(spath):
            os.remove(spath)
    except OSError:
        pass
    acc.session_file_path = None
    await db.commit()
    await log_event("INFO", "account", f"Session removed for @{acc.username}")
    return None


@router.post("/{account_id}/cooldown")
async def set_cooldown(
    account_id: int, hours: int = Query(default=24, ge=0, le=720),
    _: str = Depends(get_current_admin),
):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        acc.status = AccountStatus.cooldown
        acc.cooldown_until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
        await db.commit()
    return {"ok": True}


@router.post("/{account_id}/activate")
async def activate(account_id: int, _: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        acc.status = AccountStatus.active
        acc.cooldown_until = None
        await db.commit()
    return {"ok": True}


@router.get("/{account_id}/analytics")
async def account_analytics(account_id: int, _: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        rows = (
            await db.execute(
                select(
                    func.count(Post.id),
                    func.coalesce(func.sum(Post.views_7d), 0),
                    func.coalesce(func.sum(Post.likes_7d), 0),
                    func.avg(Post.engagement_rate),
                ).where(Post.account_id == account_id, Post.status == PostStatus.posted)
            )
        ).one()
        recent = (
            await db.execute(
                select(Post).where(Post.account_id == account_id).order_by(Post.created_at.desc()).limit(10)
            )
        ).scalars().all()
        return {
            "posts": rows[0],
            "views": int(rows[1] or 0),
            "likes": int(rows[2] or 0),
            "avg_engagement": round(float(rows[3] or 0), 2),
            "recent": [{"id": p.id, "status": p.status.value, "views_7d": p.views_7d, "posted_at": p.posted_at} for p in recent],
        }
