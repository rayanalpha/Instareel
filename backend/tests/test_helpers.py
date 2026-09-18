"""Minimal pytest suite for pure helpers — no DB, no network, no subprocess.

Run from backend/:  python -m pytest tests/ -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite://")

from app.utils.ffmpeg import _parse_probe_json, build_command, build_filter  # noqa: E402
from app.utils.instagram_helpers import device_settings_for, session_path_for  # noqa: E402
from app.core.security import decrypt_secret, encrypt_secret  # noqa: E402


class TestSessionPath:
    def test_dot_becomes_underscore(self):
        assert session_path_for("deer.9693176", "media").endswith("deer_9693176.json")

    def test_safe_name_unchanged(self):
        assert session_path_for("plain_user", "media").endswith("plain_user.json")

    def test_creates_directory(self, tmp_path):
        p = session_path_for("user1", str(tmp_path))
        assert os.path.isdir(os.path.dirname(p))


class TestDeviceSettings:
    def test_stable_fingerprint_per_account(self):
        assert device_settings_for("a") == device_settings_for("a")
        assert device_settings_for("a") != device_settings_for("b")

    def test_tracks_current_app_version(self):
        d = device_settings_for("x")
        # Numeric major comparison (lexicographic ">=" would accept "99.x" too).
        assert int(str(d["app_version"]).split(".")[0]) >= 400  # Instagram rejects outdated versions
        assert d["model"] == "Pixel 8 Pro"


class TestFfmpegBuilder:
    def test_crop_scale_chain_always_present(self):
        fc, needs_wm = build_filter()
        assert "crop=ih*9/16" in fc
        assert "scale=720:1280" in fc
        assert needs_wm is False

    def test_effect_and_custom_filters_appended(self):
        fc, _ = build_filter(effect_filter="eq=saturation=1.2", custom_filters="unsharp")
        assert "eq=saturation=1.2" in fc and "unsharp" in fc

    def test_watermark_adds_second_input(self):
        fc, needs_wm = build_filter(watermark_path="wm.png")
        assert needs_wm is True
        assert "overlay" in fc

    def test_command_has_encode_flags(self):
        cmd = build_command("in.mp4", "out.mp4")
        joined = " ".join(cmd)
        assert "-c:v" in cmd and "libx264" in joined
        assert "+faststart" in joined

    def test_trim_window(self):
        cmd = build_command("in.mp4", "out.mp4", trim_start=2, trim_end=5)
        assert "-ss" in cmd and "2" in cmd and "3" in cmd

    def test_silent_track_added_when_no_audio(self):
        cmd = build_command("in.mp4", "out.mp4", has_audio=False)
        assert "anullsrc" in " ".join(cmd)


class TestProbeParsing:
    def test_parses_streams(self):
        raw = json.dumps({
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080},
                {"codec_type": "audio"},
            ],
            "format": {"duration": "12.5"},
        }).encode()
        info = _parse_probe_json(raw)
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["duration"] == 12.5
        assert info["has_audio"] is True

    def test_no_audio_flag(self):
        raw = json.dumps({
            "streams": [{"codec_type": "video", "width": 720, "height": 1280}],
            "format": {"duration": "5"},
        }).encode()
        info = _parse_probe_json(raw)
        assert info["has_audio"] is False
        assert info["duration"] == 5.0

    def test_empty_probe_defaults(self):
        info = _parse_probe_json(b"{}")
        assert info["duration"] == 0
        assert info["width"] == 0
        assert info["height"] == 0
        assert info["has_audio"] is False


class TestDefaultEffects:
    def test_names_unique_and_valid(self):
        from app.services.default_effects import DEFAULT_EFFECT_PRESETS

        names = [p["name"] for p in DEFAULT_EFFECT_PRESETS]
        assert len(names) >= 40
        assert len(set(names)) == len(names)
        for name in names:
            assert 1 <= len(name) <= 128
            assert all(c.isalnum() or c in "-_" for c in name)

    def test_filters_are_single_chain_safe(self):
        from app.services.default_effects import DEFAULT_EFFECT_PRESETS

        for p in DEFAULT_EFFECT_PRESETS:
            f = p["ffmpeg_filter"]
            assert f.strip(), p["name"]
            # Must compose inside [0:v]...[outv]: no graph separators/labels.
            assert ";" not in f and "[" not in f and "]" not in f, p["name"]

    def test_every_preset_builds_a_command(self):
        from app.services.default_effects import DEFAULT_EFFECT_PRESETS

        for p in DEFAULT_EFFECT_PRESETS:
            fc, _ = build_filter(effect_filter=p["ffmpeg_filter"])
            assert "crop=ih*9/16" in fc and "scale=720:1280" in fc, p["name"]
            cmd = build_command("in.mp4", "out.mp4", effect_filter=p["ffmpeg_filter"])
            assert "libx264" in " ".join(cmd), p["name"]


class TestAccountHealthPolicy:
    def _now(self):
        import datetime as dt

        return dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.timezone.utc)

    def test_warmup_caps_fresh_account(self):
        import datetime as dt

        from app.tasks.sync_helpers import effective_max_posts

        now = self._now()
        fresh = now - dt.timedelta(days=3)
        assert effective_max_posts(fresh, 3, now) == 1
        # Naive datetimes (SQLite) behave the same as aware ones.
        assert effective_max_posts(fresh.replace(tzinfo=None), 3, now) == 1

    def test_warmup_releases_after_7_days(self):
        import datetime as dt

        from app.tasks.sync_helpers import effective_max_posts

        now = self._now()
        assert effective_max_posts(now - dt.timedelta(days=7), 3, now) == 3
        assert effective_max_posts(now - dt.timedelta(days=30), 5, now) == 5

    def test_warmup_never_raises_cap(self):
        import datetime as dt

        from app.tasks.sync_helpers import effective_max_posts

        now = self._now()
        assert effective_max_posts(now, 1, now) == 1
        assert effective_max_posts(None, 3, now) == 3

    def test_throttle_backoff(self):
        from app.tasks.sync_helpers import throttle_cooldown_hours

        assert throttle_cooldown_hours(0) == 6
        assert throttle_cooldown_hours(1) == 12
        assert throttle_cooldown_hours(2) == 24
        assert throttle_cooldown_hours(9) == 24

    def test_spare_prefers_same_country_then_load_then_latency(self):
        from app.tasks.sync_helpers import rank_spare_proxies

        assert rank_spare_proxies([], "DE") is None
        de_busy = {"proxy": "de-busy", "load": 5, "country": "DE", "latency": 50}
        de_idle = {"proxy": "de-idle", "load": 0, "country": "de", "latency": 900}
        us_idle = {"proxy": "us-idle", "load": 0, "country": "US", "latency": 20}
        # Same country wins even with worse latency/load (no geo-hop).
        assert rank_spare_proxies([us_idle, de_busy], "DE") == "de-busy"
        # Within a country: lower load, then lower latency; None latency last.
        de_noping = {"proxy": "de-noping", "load": 0, "country": "DE", "latency": None}
        assert rank_spare_proxies([de_busy, de_idle, de_noping], "DE") == "de-idle"
        assert rank_spare_proxies([us_idle, de_noping], "XX") == "us-idle"

    def test_account_age_days_handles_naive(self):
        import datetime as dt

        from app.tasks.sync_helpers import account_age_days

        now = self._now()
        assert account_age_days(now - dt.timedelta(hours=36), now) == 1.5
        assert account_age_days(None, now) > 10**8

    def test_missing_presets_top_up(self):
        from app.services.default_effects import DEFAULT_EFFECT_PRESETS, missing_presets

        assert missing_presets([]) == DEFAULT_EFFECT_PRESETS
        names = [p["name"] for p in DEFAULT_EFFECT_PRESETS]
        assert missing_presets(names) == []
        partial = missing_presets(names[:5])
        assert [p["name"] for p in partial] == names[5:]


class TestFeedRetry:
    def _feed(self):
        from app.services.instagram_service import _feed_with_retry

        return _feed_with_retry

    def test_healthy_session_no_sleep(self, monkeypatch):
        calls = []
        monkeypatch.setattr("time.sleep", lambda s: calls.append(s))

        class Cl:
            def get_timeline_feed(self):
                return {"ok": True}

        assert self._feed()(Cl()) == (True, "")
        assert calls == []

    def test_auth_failure_fails_fast(self, monkeypatch):
        calls = []
        monkeypatch.setattr("time.sleep", lambda s: calls.append(s))

        class Cl:
            def get_timeline_feed(self):
                raise Exception("login_required: need login")

        ok, kind = self._feed()(Cl())
        assert ok is False and kind == "login_required"
        assert calls == []  # no point retrying auth — go straight to login

    def test_network_blip_retried_once_then_ok(self, monkeypatch):
        calls = []
        monkeypatch.setattr("time.sleep", lambda s: calls.append(s))
        state = {"n": 0}

        class Cl:
            def get_timeline_feed(self):
                state["n"] += 1
                if state["n"] == 1:
                    raise ConnectionError("reset by peer")
                return {"ok": True}

        assert self._feed()(Cl()) == (True, "")
        assert calls == [5]

    def test_persistent_outage_returns_last_kind(self, monkeypatch):
        calls = []
        monkeypatch.setattr("time.sleep", lambda s: calls.append(s))

        class Cl:
            def get_timeline_feed(self):
                raise TimeoutError("timed out")

        ok, kind = self._feed()(Cl())
        assert ok is False and kind == "generic"
        assert calls == [5]


class TestPostClaim:
    """Single-flight claim + video reservation against a real (in-memory) DB."""

    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    _seq = 0

    def _seed_post(self, s, status="scheduled", when=None):
        import datetime as dt

        from app.models import Account, Post, PostStatus, Video

        TestPostClaim._seq += 1
        tag = TestPostClaim._seq
        acc = Account(username=f"claimer{tag}", password_enc="x")
        vid = Video(original_filename="a.mp4", raw_path="/tmp/a.mp4", md5_hash=f"h{tag}")
        s.add_all([acc, vid])
        s.flush()
        post = Post(
            video_id=vid.id,
            account_id=acc.id,
            status=PostStatus[status],
            scheduled_for=when or dt.datetime.now(dt.timezone.utc),
        )
        s.add(post)
        s.commit()
        return acc.id, vid.id, post.id

    def test_claim_then_busy_then_missing(self):
        from app.models import Post, PostStatus
        from app.tasks.sync_helpers import claim_post

        s = self._session()
        _, _, pid = self._seed_post(s)
        assert claim_post(s, pid) == "claimed"
        claimed = s.get(Post, pid)
        assert claimed is not None and claimed.status == PostStatus.posting
        # Beat redelivery / worker crash redelivery must not re-upload.
        assert claim_post(s, pid) == "busy"
        assert claim_post(s, 999999) == "missing"

    def test_claim_refuses_non_scheduled(self):
        from app.tasks.sync_helpers import claim_post

        s = self._session()
        import datetime as dt

        for st in ("posting", "posted", "failed"):
            _, _, pid = self._seed_post(s, status=st)
            assert claim_post(s, pid) == "busy", st

    def test_video_reservation_window(self):
        import datetime as dt

        from app.tasks.sync_helpers import video_already_queued

        s = self._session()
        _, vid, _ = self._seed_post(s)
        assert video_already_queued(s, vid) is True
        assert video_already_queued(s, vid + 999) is False

    def test_video_freed_after_post_or_far_schedule(self):
        import datetime as dt

        from app.models import Post, PostStatus
        from app.tasks.sync_helpers import video_already_queued

        s = self._session()
        _, vid, pid = self._seed_post(s)
        # Posted videos are archived by the executor — no longer queued.
        row = s.get(Post, pid)
        assert row is not None
        row.status = PostStatus.posted
        s.commit()
        assert video_already_queued(s, vid) is False
        # A post scheduled far outside the window doesn't block either.
        far = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
        _, vid2, _ = self._seed_post(s, when=far)
        assert video_already_queued(s, vid2) is False
        assert video_already_queued(s, vid2, window_min=180) is True


class TestCrypto:
    def test_roundtrip(self):
        token = encrypt_secret("s3cret")
        assert token != "s3cret"
        assert decrypt_secret(token) == "s3cret"

    def test_empty_passthrough(self):
        assert encrypt_secret(None) is None
        assert decrypt_secret(None) is None
