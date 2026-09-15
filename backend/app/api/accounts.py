"""IG accounts CRUD + session management."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, AccountStatus, Post, PostStatus
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.log_service import log_event

router = APIRouter()


def _out(a: Account) -> AccountOut:
    return AccountOut(
        id=a.id, username=a.username, proxy_id=a.proxy_id, status=a.status.value,
        last_login=a.last_login, last_post=a.last_post, posts_today=a.posts_today,
        max_daily_posts=a.max_daily_posts, cooldown_until=a.cooldown_until,
        total_posts=a.total_posts, total_views=a.total_views, total_likes=a.total_likes,
        notes=a.notes, created_at=a.created_at, updated_at=a.updated_at,
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
    if body.max_daily_posts is not None:
        acc.max_daily_posts = body.max_daily_posts
    if body.notes is not None:
        acc.notes = body.notes
    if body.proxy_id is not None:
        acc.proxy_id = body.proxy_id
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


@router.post("/{account_id}/cooldown")
async def set_cooldown(account_id: int, hours: int = 24, _: str = Depends(get_current_admin)):
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
