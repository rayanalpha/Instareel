import datetime as dt

from pydantic import BaseModel, Field


class ScheduleRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    day_of_week: int = Field(default=-1, ge=-1, le=6)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    account_id: int | None = None
    is_active: bool = True
    preferred_effect: str | None = None
    caption_template_id: int | None = None


class ScheduleRuleOut(ScheduleRuleIn):
    id: int
    created_at: dt.datetime


class CaptionIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    category: str | None = None
    is_active: bool = True


class CaptionOut(CaptionIn):
    id: int
    use_count: int
    avg_engagement: float | None


class HashtagSetIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tags: str = Field(min_length=1)
    is_active: bool = True


class HashtagSetOut(HashtagSetIn):
    id: int
    use_count: int


class BioIn(BaseModel):
    account_id: int
    text: str = Field(min_length=1)
    link_url: str = ""
    is_active: bool = True
    rotation_interval_days: int = Field(default=14, ge=1, le=365)


class BioOut(BioIn):
    id: int
    last_applied: dt.datetime | None


class EffectIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    ffmpeg_filter: str = ""
    is_active: bool = True


class EffectOut(EffectIn):
    id: int
    use_count: int
    avg_engagement: float | None


class AudioIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    music_volume: float = Field(default=0.4, ge=0.0, le=2.0)
    duck_original: bool = False
    is_active: bool = True


class AudioOut(AudioIn):
    id: int
    file_path: str
    duration: float | None
    use_count: int
    avg_engagement: float | None


class SettingOut(BaseModel):
    key: str
    value: str
    category: str
    is_sensitive: bool


class LogOut(BaseModel):
    id: int
    level: str
    category: str
    message: str
    details: dict | None
    timestamp: dt.datetime
