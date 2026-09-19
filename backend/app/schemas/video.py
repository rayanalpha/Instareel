import datetime as dt

from pydantic import BaseModel, Field


class VideoOut(BaseModel):
    id: int
    original_filename: str
    duration: float | None
    file_size: int | None
    status: str
    effect_preset: str | None
    audio_track: str | None
    custom_filters: str | None
    add_watermark: bool
    trim_start: float | None
    trim_end: float | None
    failed_reason: str | None
    processed_at: dt.datetime | None
    thumbnail_path: str | None
    created_at: dt.datetime


class VideoSettingsUpdate(BaseModel):
    effect_preset: str | None = None
    audio_track: str | None = None
    custom_filters: str | None = None
    trim_start: float | None = Field(default=None, ge=0)
    trim_end: float | None = Field(default=None, ge=0)
    add_watermark: bool | None = None


class PostOut(BaseModel):
    id: int
    video_id: int
    account_id: int
    ig_media_id: str | None
    ig_permalink: str | None
    caption: str
    hashtags: str
    audio_track: str | None = None
    status: str
    scheduled_for: dt.datetime | None
    posted_at: dt.datetime | None
    views_24h: int | None
    views_7d: int | None
    likes_24h: int | None
    engagement_rate: float | None
    fail_reason: str | None
    retry_count: int
    created_at: dt.datetime


class SchedulePostIn(BaseModel):
    video_id: int
    account_id: int | None = None
    scheduled_for: dt.datetime | None = None
    caption: str = ""
    hashtags: str = ""
