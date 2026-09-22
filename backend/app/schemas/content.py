import datetime as dt
import re

from pydantic import BaseModel, Field, field_validator


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
    # Every section is optional and independent — empty = don't touch on IG.
    text: str = ""
    link_url: str = ""
    full_name: str = Field(default="", max_length=128)

    @field_validator("link_url")
    @classmethod
    def _safe_link(cls, v: str) -> str:
        s = (v or "").strip()
        if s and not s.lower().startswith(("http://", "https://")):
            # Bare domains (t.me/...) render relative and broken — normalize.
            # Dangerous schemes never pass through to the rendered <a href>.
            if re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)+(/.*)?$", s, re.IGNORECASE):
                return "https://" + s
            raise ValueError("link_url must be an http(s) URL")
        return s
    make_private: bool | None = None


class BioApplyIn(BaseModel):
    """Sections to apply: any of bio, link, full_name, picture, privacy.
    Omitted/empty = apply every non-empty section (legacy full apply)."""
    fields: list[str] | None = None


class BioOut(BioIn):
    id: int
    profile_pic_path: str | None = None
    has_picture: bool = False
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


class ProxySourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=8, max_length=1024)
    default_protocol: str = "http"
    default_country: str = Field(default="", max_length=2)
    is_active: bool = True


class ProxySourceOut(ProxySourceIn):
    id: int
    last_fetch_at: dt.datetime | None
    last_added: int
    last_total: int


class SettingUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=5000)


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
