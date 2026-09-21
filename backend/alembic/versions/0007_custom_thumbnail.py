"""Custom video thumbnail override (videos.custom_thumbnail_path)."""
revision = "0007_custom_thumbnail"
down_revision = "0006_trial_reels"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("videos", sa.Column("custom_thumbnail_path", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "custom_thumbnail_path")
