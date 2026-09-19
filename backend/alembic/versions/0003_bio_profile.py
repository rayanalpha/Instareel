"""Bio profile customization: full_name, profile_pic_path, make_private on bio_configs."""
revision = "0003_bio_profile"
down_revision = "0002_audio_tracks"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("bio_configs", sa.Column("full_name", sa.String(128), nullable=False, server_default=""))
    op.add_column("bio_configs", sa.Column("profile_pic_path", sa.String(1024), nullable=True))
    op.add_column("bio_configs", sa.Column("make_private", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("bio_configs", "make_private")
    op.drop_column("bio_configs", "profile_pic_path")
    op.drop_column("bio_configs", "full_name")
