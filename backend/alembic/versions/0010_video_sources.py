"""Video sources: video_sources + source_items tables, videos.source_caption."""
revision = "0010_video_sources"
down_revision = "0009_rule_pin_video"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "video_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(128), nullable=False, index=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("idle", "running", "stopping", "completed", "failed",
                                    name="sourcestatus"), nullable=False, server_default="idle"),
        sa.Column("max_items", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("reels_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("with_covers", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_process", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("delay_min_s", sa.Float(), nullable=False, server_default="8"),
        sa.Column("delay_max_s", sa.Float(), nullable=False, server_default="20"),
        sa.Column("end_cursor", sa.String(512), nullable=True),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1024), nullable=True),
        sa.Column("current_stage", sa.String(256), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "source_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), nullable=False, index=True),
        sa.Column("media_pk", sa.String(64), nullable=False, index=True),
        sa.Column("shortcode", sa.String(64), nullable=True),
        sa.Column("media_type", sa.String(16), nullable=True),
        sa.Column("status", sa.Enum("pending", "downloading", "downloaded", "skipped", "failed",
                                    name="sourceitemstatus"), nullable=False, server_default="pending"),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "media_pk", name="uq_source_item"),
    )
    op.add_column("videos", sa.Column("source_caption", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "source_caption")
    op.drop_table("source_items")
    op.drop_table("video_sources")
