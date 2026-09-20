"""JWT auth, bcrypt passwords, Fernet encryption for stored secrets."""
import datetime as dt

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt_secret(plaintext: str | None) -> str | None:
    if not plaintext:
        return plaintext
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return token
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        # Legacy plaintext value stored before encryption was enabled.
        return token


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def _encode(payload: dict, expires: dt.timedelta) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_access_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "access"}, dt.timedelta(minutes=settings.JWT_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "refresh"}, dt.timedelta(days=settings.JWT_REFRESH_DAYS))


def decode_token(token: str, expected_type: str = "access") -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Wrong token type")
    sub = payload.get("sub")
    if not sub:
        # A structurally valid JWT without subject must 401, never 500.
        raise ValueError("Invalid token")
    return str(sub)
