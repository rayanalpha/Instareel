"""Proxy rotation signals: last_error on proxies (fail evidence for the router)."""
revision = "0004_proxy_last_error"
down_revision = "0003_bio_profile"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("proxies", sa.Column("last_error", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("proxies", "last_error")
