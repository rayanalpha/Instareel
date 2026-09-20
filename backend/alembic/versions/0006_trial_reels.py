"""Trial Reels: videos.is_trial/trial_strategy + posts.is_trial."""
revision = "0006_trial_reels"
down_revision = "0005_proxy_pool"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("videos", sa.Column("is_trial", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("videos", sa.Column("trial_strategy", sa.String(16), nullable=False, server_default="manual"))
    op.add_column("posts", sa.Column("is_trial", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("posts", "is_trial")
    op.drop_column("videos", "trial_strategy")
    op.drop_column("videos", "is_trial")
