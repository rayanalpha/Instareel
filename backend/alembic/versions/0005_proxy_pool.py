"""Auto proxy pool: proxy_sources table + proxies.source origin column."""
revision = "0005_proxy_pool"
down_revision = "0004_proxy_last_error"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _ts_columns():
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "proxy_sources",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("default_protocol", sa.String(16), nullable=False, server_default="http"),
        sa.Column("default_country", sa.String(8), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_total", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proxy_sources_name", "proxy_sources", ["name"], unique=True)
    op.add_column("proxies", sa.Column("source", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("proxies", "source")
    op.drop_index("ix_proxy_sources_name", table_name="proxy_sources")
    op.drop_table("proxy_sources")
