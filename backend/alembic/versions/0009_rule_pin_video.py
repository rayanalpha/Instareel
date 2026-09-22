"""Hybrid scheduling: schedule_rules.pinned_video_id (nullable FK to videos)."""
revision = "0009_rule_pin_video"
down_revision = "0008_drop_bio_rotation"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("schedule_rules", sa.Column("pinned_video_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_schedule_rules_pinned_video", "schedule_rules", "videos",
        ["pinned_video_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_schedule_rules_pinned_video", "schedule_rules", type_="foreignkey")
    op.drop_column("schedule_rules", "pinned_video_id")
