"""Shared dependencies: DB session, JWT auth guard, rate limiting."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.database import get_db

limiter = Limiter(key_func=get_remote_address)
bearer = HTTPBearer(auto_error=False)


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def admin_username() -> str:
    return settings.ADMIN_USERNAME

__all__ = ["get_db", "get_current_admin", "limiter", "admin_username"]
