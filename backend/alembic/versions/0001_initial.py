"""Initial schema: all tables."""
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _ts_columns():
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "proxies",
        *_ts_columns(),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("protocol", sa.Enum("http", "socks5", "socks4", name="proxyprotocol"), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password_enc", sa.String(1024), nullable=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "accounts",
        *_ts_columns(),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_enc", sa.String(1024), nullable=False),
        sa.Column("proxy_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "cooldown", "banned", "challenge_required", "disabled", name="accountstatus"),
            nullable=False,
        ),
        sa.Column("session_file_path", sa.String(512), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_post", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posts_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_daily_posts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["proxy_id"], ["proxies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)
    op.create_table(
        "videos",
        *_ts_columns(),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("raw_path", sa.String(1024), nullable=False),
        sa.Column("processed_path", sa.String(1024), nullable=True),
        sa.Column("thumbnail_path", sa.String(1024), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("md5_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("uploaded", "processing", "processed", "posting", "posted", "failed", "archived", name="videostatus"),
            nullable=False,
        ),
        sa.Column("upload_notes", sa.Text(), nullable=True),
        sa.Column("effect_preset", sa.String(128), nullable=True),
        sa.Column("custom_filters", sa.Text(), nullable=True),
        sa.Column("trim_start", sa.Float(), nullable=True),
        sa.Column("trim_end", sa.Float(), nullable=True),
        sa.Column("add_watermark", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_md5", "videos", ["md5_hash"], unique=True)
    op.create_table(
        "posts",
        *_ts_columns(),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("ig_media_id", sa.String(128), nullable=True),
        sa.Column("ig_permalink", sa.String(512), nullable=True),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("hashtags", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.Enum("scheduled", "posting", "posted", "failed", "deleted", "shadowbanned_check", name="poststatus"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views_1h", sa.Integer(), nullable=True),
        sa.Column("views_6h", sa.Integer(), nullable=True),
        sa.Column("views_24h", sa.Integer(), nullable=True),
        sa.Column("views_48h", sa.Integer(), nullable=True),
        sa.Column("views_7d", sa.Integer(), nullable=True),
        sa.Column("likes_1h", sa.Integer(), nullable=True),
        sa.Column("likes_24h", sa.Integer(), nullable=True),
        sa.Column("likes_7d", sa.Integer(), nullable=True),
        sa.Column("comments_24h", sa.Integer(), nullable=True),
        sa.Column("comments_7d", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("last_analytics_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "caption_templates",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_engagement", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hashtag_sets",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schedule_rules",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("preferred_effect", sa.String(128), nullable=True),
        sa.Column("caption_template_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["caption_template_id"], ["caption_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bio_configs",
        *_ts_columns(),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_applied", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_interval_days", sa.Integer(), nullable=False, server_default="14"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "effect_presets",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("ffmpeg_filter", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_engagement", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_effect_presets_name", "effect_presets", ["name"], unique=True)
    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", sa.Enum("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", name="loglevel"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_logs_category", "system_logs", ["category"])
    op.create_index("ix_logs_timestamp", "system_logs", ["timestamp"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    for table in [
        "settings", "system_logs", "effect_presets", "bio_configs",
        "schedule_rules", "hashtag_sets", "caption_templates", "posts", "videos", "accounts", "proxies",
    ]:
        op.drop_table(table)
