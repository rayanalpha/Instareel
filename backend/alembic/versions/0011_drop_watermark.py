"""Drop the watermark feature (videos.add_watermark)."""
revision = "0011_drop_watermark"
down_revision = "0010_video_sources"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.drop_column("videos", "add_watermark")


def downgrade() -> None:
    op.add_column("videos", sa.Column("add_watermark", sa.Boolean(), server_default=sa.true()))
