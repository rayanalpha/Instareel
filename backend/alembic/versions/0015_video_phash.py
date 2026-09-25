"""Near-duplicate detection: perceptual hash per video.

- videos.phash: 64-bit dHash of a middle frame, hex-encoded (16 chars).
  NULL for rows ingested before this migration (they simply never match).
  Additive + nullable: old code reading the table keeps working.
"""
revision = "0015_video_phash"
down_revision = "0014_drop_dead_columns"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("videos", sa.Column("phash", sa.String(16), nullable=True))
    op.create_index("ix_videos_phash", "videos", ["phash"])


def downgrade() -> None:
    op.drop_index("ix_videos_phash", table_name="videos")
    op.drop_column("videos", "phash")
