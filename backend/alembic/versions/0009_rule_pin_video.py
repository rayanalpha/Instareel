"""Hybrid scheduling: schedule_rules.pinned_video_id (nullable, app-validated).

No DB-level FK: SQLite can't ALTER in constraints, and it wouldn't enforce
them anyway — pin targets are validated in the API (same as other FKs).
"""
revision = "0009_rule_pin_video"
down_revision = "0008_drop_bio_rotation"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("schedule_rules", sa.Column("pinned_video_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedule_rules", "pinned_video_id")
