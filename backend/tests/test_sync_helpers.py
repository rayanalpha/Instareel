"""Unit tests for sync_helpers caption decisions — sync SQLite, no network.

Run from backend/:  python -m pytest tests/ -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import CaptionTemplate, HashtagSet  # noqa: E402
from app.tasks.sync_helpers import resolve_fire_caption  # noqa: E402


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(CaptionTemplate(name="t", content="templated cap", is_active=True))
    s.add(HashtagSet(name="h", tags="foo,bar", is_active=True))
    s.commit()
    return s


class TestResolveFireCaption:
    def test_source_wins_verbatim(self):
        # No DB touch on this path — session never consulted.
        assert resolve_fire_caption(None, True, "src cap #x", None) == ("src cap #x", "")

    def test_source_ignored_when_disabled(self):
        cap, tags = resolve_fire_caption(_session(), False, "src cap #x", None)
        assert cap == "templated cap" and tags

    def test_fallback_to_template_without_source(self):
        cap, tags = resolve_fire_caption(_session(), True, None, None)
        assert cap == "templated cap" and tags

    def test_blank_source_falls_back(self):
        cap, _ = resolve_fire_caption(_session(), True, "   ", None)
        assert cap == "templated cap"
