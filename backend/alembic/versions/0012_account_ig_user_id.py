"""Track the stable Instagram numeric user id per account.

Usernames change; ds_user_id never does. Storing it lets uploads and
renames verify a session file really belongs to the account row, and lets
an uploaded session auto-adopt a renamed username instead of forcing the
user to delete and re-create the account (which wipes its history).
"""
revision = "0012_account_ig_user_id"
down_revision = "0011_drop_watermark"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("accounts", sa.Column("ig_user_id", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "ig_user_id")
