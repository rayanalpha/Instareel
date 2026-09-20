"""Schedule rules, captions, hashtags, bios, effects, logs, settings."""
import datetime as dt

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base
from app.models.base import TimestampMixin


class ScheduleRule(Base, TimestampMixin):
    __tablename__ = "schedule_rules"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, default=-1)  # -1 = every day
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_effect: Mapped[str | None] = mapped_column(String(128), nullable=True)
    caption_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("caption_templates.id"), nullable=True
    )


class CaptionTemplate(Base, TimestampMixin):
    __tablename__ = "caption_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class HashtagSet(Base, TimestampMixin):
    __tablename__ = "hashtag_sets"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class BioConfig(Base, TimestampMixin):
    __tablename__ = "bio_configs"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_applied: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotation_interval_days: Mapped[int] = mapped_column(Integer, default=14)
    # Extended profile customization (all optional — empty/None = don't touch):
    full_name: Mapped[str] = mapped_column(String(128), default="")
    profile_pic_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Tri-state privacy: None = leave as-is, True = force private, False = force public.
    make_private: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="bio_configs")


class EffectPreset(Base, TimestampMixin):
    __tablename__ = "effect_presets"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    ffmpeg_filter: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class AudioTrack(Base, TimestampMixin):
    """Trending/named audio mixed into processed videos (FFmpeg, pre-upload).

    The track's sound is baked into the file's audio stream — this is what
    viewers hear (and what drives retention). Note: this does NOT attach an
    official IG licensed-track attribution; that surface only exists in the
    official app. Selection is data-driven: least-used + best-engagement
    weighting in tasks.sync_helpers.pick_audio.
    """

    __tablename__ = "audio_tracks"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Playback level of the music (0.0-2.0). Original audio stays at full
    # volume unless duck_original mutes it in favor of the track.
    music_volume: Mapped[float] = mapped_column(Float, default=0.4)
    duck_original: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class ProxySource(Base, TimestampMixin):
    """A remote proxy list feeding the auto pool (see refresh_proxy_pool).

    Fetch is read-only text over HTTPS; every line goes through the same
    strict parser as manual imports. Rows created from a source carry
    Proxy.source == this name, so the purge only ever touches auto rows —
    hand-added/imported proxies ("manual") are immortal.
    """

    __tablename__ = "proxy_sources"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_protocol: Mapped[str] = mapped_column(String(16), default="http")
    default_country: Mapped[str] = mapped_column(String(8), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetch_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_added: Mapped[int] = mapped_column(Integer, default=0)
    last_total: Mapped[int] = mapped_column(Integer, default=0)


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    level: Mapped[LogLevel] = mapped_column(SQLEnum(LogLevel), default=LogLevel.INFO)
    category: Mapped[str] = mapped_column(String(64), default="system", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), index=True
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )
