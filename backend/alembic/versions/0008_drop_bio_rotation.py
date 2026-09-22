"""Drop bio rotation columns (bio_configs.is_active, rotation_interval_days)."""
revision = "0008_drop_bio_rotation"
down_revision = "0007_custom_thumbnail"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    with op.batch_alter_table("bio_configs") as batch:
        batch.drop_column("is_active")
        batch.drop_column("rotation_interval_days")


def downgrade() -> None:
    with op.batch_alter_table("bio_configs") as batch:
        batch.add_column(sa.Column("is_active", sa.Boolean(), server_default=sa.true()))
        batch.add_column(sa.Column("rotation_interval_days", sa.Integer(), server_default="14"))
