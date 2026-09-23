"""Prefer harvested source captions on scheduled posts.

When a rule fires a video that carries a source_caption (ingested from a
source page), the caption posts verbatim instead of a random template.
Existing rules keep the behavior via server_default=True.
"""
revision = "0013_rule_prefer_source_caption"
down_revision = "0012_account_ig_user_id"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "schedule_rules",
        sa.Column("prefer_source_caption", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("schedule_rules", "prefer_source_caption")
