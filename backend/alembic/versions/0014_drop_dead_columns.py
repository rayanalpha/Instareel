"""Drop write-only / never-read columns and orphaned setting seeds.

- posts.views_1h/likes_1h/views_6h/views_48h/comments_24h: written by the
  analytics job but never read anywhere (24h/7d + engagement carry the UI).
- videos.upload_notes: zero references in the codebase.
- caption_templates/effect_presets/audio_tracks.avg_engagement: never
  computed, always NULL (aggregates are computed on the fly instead).
- settings rows orphaned by earlier seed removals (analytics_refresh_hours,
  default_effect, watermark_enabled): the toggles never did anything.
"""
revision = "0014_drop_dead_columns"
down_revision = "0013_rule_prefer_source_caption"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

DEAD_POST_COLS = ["views_1h", "likes_1h", "views_6h", "views_48h", "comments_24h"]
ORPHAN_SETTINGS = ["analytics_refresh_hours", "default_effect", "watermark_enabled"]


def upgrade() -> None:
    for col in DEAD_POST_COLS:
        op.drop_column("posts", col)
    op.drop_column("videos", "upload_notes")
    for table in ("caption_templates", "effect_presets", "audio_tracks"):
        op.drop_column(table, "avg_engagement")
    for key in ORPHAN_SETTINGS:
        op.execute(sa.text("DELETE FROM settings WHERE key = :k").bindparams(k=key))


def downgrade() -> None:
    for col in DEAD_POST_COLS:
        op.add_column("posts", sa.Column(col, sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("upload_notes", sa.Text(), nullable=True))
    for table in ("caption_templates", "effect_presets", "audio_tracks"):
        op.add_column(table, sa.Column("avg_engagement", sa.Float(), nullable=True))
