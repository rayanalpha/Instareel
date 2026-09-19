"""Pydantic schemas shared across resources."""
import datetime as dt

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1)
    proxy_id: int | None = None
    max_daily_posts: int = Field(default=3, ge=1, le=20)
    notes: str | None = None


class AccountUpdate(BaseModel):
    max_daily_posts: int | None = Field(default=None, ge=1, le=20)
    notes: str | None = None
    status: str | None = None
    proxy_id: int | str | None = None


class AccountOut(BaseModel):
    id: int
    username: str
    proxy_id: int | None
    status: str
    last_login: dt.datetime | None
    last_post: dt.datetime | None
    posts_today: int
    max_daily_posts: int
    cooldown_until: dt.datetime | None
    total_posts: int
    total_views: int
    total_likes: int
    notes: str | None
    has_session: bool = False
    created_at: dt.datetime
    updated_at: dt.datetime


class ProxyCreate(BaseModel):
    url: str
    protocol: str = "http"
    username: str | None = None
    password: str | None = None
    country: str | None = None


class ProxyUpdate(BaseModel):
    url: str | None = None
    protocol: str | None = None
    username: str | None = None
    password: str | None = None
    country: str | None = None
    is_active: bool | None = None


class ProxyOut(BaseModel):
    id: int
    url: str
    protocol: str
    username: str | None
    country: str | None
    is_healthy: bool
    last_checked: dt.datetime | None
    fail_count: int
    latency_ms: int | None
    last_error: str | None = None
    is_active: bool
    created_at: dt.datetime
