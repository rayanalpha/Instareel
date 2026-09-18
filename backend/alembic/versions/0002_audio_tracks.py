"""Trending audio: audio_tracks table + videos.audio_track column."""
revision = "0002_audio_tracks"
down_revision = "0001_initial"
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
        "audio_tracks",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("music_volume", sa.Float(), nullable=False, server_default="0.4"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("duck_original", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_engagement", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audio_tracks_name", "audio_tracks", ["name"], unique=True)
    op.add_column("videos", sa.Column("audio_track", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "audio_track")
    op.drop_index("ix_audio_tracks_name", table_name="audio_tracks")
    op.drop_table("audio_tracks")
