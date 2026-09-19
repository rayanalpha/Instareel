"""Minimal pytest suite for pure helpers — no DB, no network, no subprocess.

Run from backend/:  python -m pytest tests/ -q
"""
import json
import os
import sys

from sqlalchemy import select

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


class TestSiblingGuard:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def _video_and_posts(self, s, sibling_status="posting", sibling_age_h=0):
        import datetime as dt
        from sqlalchemy import update

        from app.models import Account, Post, PostStatus, Video

        TestPostClaim._seq += 1
        tag = TestPostClaim._seq
        s.add_all([
            Account(username=f"sib{tag}", password_enc="x"),
            Video(original_filename="b.mp4", raw_path="/tmp/b.mp4", md5_hash=f"sib{tag}"),
        ])
        s.flush()
        acc = s.execute(select(Account).where(Account.username == f"sib{tag}")).scalar_one()
        vid = s.execute(select(Video).where(Video.md5_hash == f"sib{tag}")).scalar_one()
        now = dt.datetime.now(dt.timezone.utc)
        mine = Post(video_id=vid.id, account_id=acc.id, status=PostStatus.posting, scheduled_for=now)
        sib = Post(video_id=vid.id, account_id=acc.id, status=PostStatus[sibling_status], scheduled_for=now)
        s.add_all([mine, sib])
        s.commit()
        if sibling_age_h:
            old = now - dt.timedelta(hours=sibling_age_h)
            s.execute(update(Post).where(Post.id == sib.id).values(updated_at=old))
            s.commit()
            s.expire_all()
        return mine.id, vid.id

    def test_fresh_posting_sibling_blocks(self):
        from app.tasks.sync_helpers import find_blocking_sibling

        s = self._session()
        mine, vid = self._video_and_posts(s, "posting")
        sib = find_blocking_sibling(s, mine, vid)
        assert sib is not None and sib.status.value == "posting"

    def test_posted_sibling_blocks(self):
        from app.tasks.sync_helpers import find_blocking_sibling

        s = self._session()
        mine, vid = self._video_and_posts(s, "posted")
        assert find_blocking_sibling(s, mine, vid) is not None

    def test_stale_posting_sibling_ignored(self):
        from app.tasks.sync_helpers import find_blocking_sibling

        s = self._session()
        mine, vid = self._video_and_posts(s, "posting", sibling_age_h=3)
        assert find_blocking_sibling(s, mine, vid) is None

    def test_nonblocking_statuses_and_self(self):
        from app.tasks.sync_helpers import find_blocking_sibling

        s = self._session()
        for st in ("scheduled", "failed"):
            mine, vid = self._video_and_posts(s, st)
            assert find_blocking_sibling(s, mine, vid) is None, st
        # Self is never its own blocker.
        mine2, vid2 = self._video_and_posts(s, "failed")
        assert find_blocking_sibling(s, mine2, vid2) is None

    def test_async_mirror_matches_sync(self):
        import asyncio
        import datetime as dt

        async def go():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.database import Base
            from app.models import Account, Post, PostStatus, Video
            from app.services import scheduler_service

            engine = create_async_engine("sqlite+aiosqlite://")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as s:
                s.add_all([
                    Account(username="am1", password_enc="x"),
                    Video(original_filename="c.mp4", raw_path="/tmp/c.mp4", md5_hash="am1"),
                ])
                await s.flush()
                acc_id = (await s.execute(select(Account).where(Account.username == "am1"))).scalar_one().id
                vid_id = (await s.execute(select(Video).where(Video.md5_hash == "am1"))).scalar_one().id
                s.add(Post(
                    video_id=vid_id, account_id=acc_id, status=PostStatus.scheduled,
                    scheduled_for=dt.datetime.now(dt.timezone.utc),
                ))
                await s.commit()
                assert await scheduler_service.video_already_queued(s, vid_id) is True
                assert await scheduler_service.video_already_queued(s, vid_id + 999) is False
            await engine.dispose()

        asyncio.run(go())


class TestSessionCookieHelpers:
    def test_sanitize_strips_quotes_whitespace_and_decoding(self):
        from app.utils.instagram_helpers import sanitize_sessionid

        assert sanitize_sessionid('  "12345%3Aabcdef%20XYZ"  ') == "12345:abcdefXYZ"
        assert sanitize_sessionid("12345:abc def") == "12345:abcdef"
        assert sanitize_sessionid("") == ""

    def test_validity_mirrors_instagrapi_gate(self):
        from app.utils.instagram_helpers import sessionid_looks_valid, sessionid_owner_id

        good = "1234567890:" + "AbC123xYz" * 4
        assert sessionid_owner_id(good) == "1234567890"
        assert sessionid_looks_valid(good) is True
        assert sessionid_looks_valid("short") is False
        assert sessionid_looks_valid("no-leading-digits-here-xxxxxxxxxx") is False
        assert sessionid_looks_valid("") is False

    def test_parse_netscape_cookies_file(self):
        from app.utils.instagram_helpers import extract_sessionid, parse_cookies_file

        raw = (
            "# Netscape HTTP Cookie File\n"
            ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\t12345%3AabcDEF12345678901234567890\n"
            ".instagram.com\tTRUE\t/\tTRUE\t0\tcsrftoken\tXYZ\n"
            "\n"
            "garbage-line-without-tabs\n"
        )
        cookies = parse_cookies_file(raw)
        assert cookies["sessionid"].startswith("12345")
        assert cookies["csrftoken"] == "XYZ"
        assert extract_sessionid(cookies) == "12345:abcDEF12345678901234567890"

    def test_parse_json_cookie_exports(self):
        from app.utils.instagram_helpers import extract_sessionid, parse_cookies_file

        flat = '{"sessionid": "999%3A' + "z" * 30 + '", "other": "1"}'
        assert extract_sessionid(parse_cookies_file(flat)) == "999:" + "z" * 30
        listed = '{"cookies": [{"name": "sessionid", "value": "777:' + "q" * 30 + '"}]}'
        assert extract_sessionid(parse_cookies_file(listed)) == "777:" + "q" * 30
        assert parse_cookies_file("") == {}
        assert parse_cookies_file("{not json") == {}

    def test_extract_rejects_truncated_cookie(self):
        from app.utils.instagram_helpers import extract_sessionid

        assert extract_sessionid({"sessionid": "12345:abc"}) is None
        assert extract_sessionid({}) is None


class TestTrendingAudio:
    def _mp3(self, tmp_path, name="trend.mp3"):
        p = tmp_path / name
        p.write_bytes(b"ID3" + b"\x00" * 1024)
        return str(p)

    def test_no_trending_keeps_legacy_command(self):
        cmd = build_command("in.mp4", "out.mp4")
        joined = " ".join(cmd)
        assert "amix" not in joined and "-map" in cmd and "0:a?" in cmd

    def test_mix_mode_loops_and_mixes(self, tmp_path):
        music = self._mp3(tmp_path)
        cmd = build_command("in.mp4", "out.mp4", trending_audio=music, music_volume=0.5, loop_audio_to=12.5)
        joined = " ".join(cmd)
        assert "-stream_loop" in cmd and "12.5" in cmd
        assert "amix=inputs=2:duration=first" in joined
        assert "[aout]" in joined and "volume=0.5" in joined

    def test_duck_mode_replaces_audio(self, tmp_path):
        music = self._mp3(tmp_path)
        cmd = build_command("in.mp4", "out.mp4", trending_audio=music, duck_original=True)
        joined = " ".join(cmd)
        assert "amix" not in joined and "volume=0.4,loudnorm" in joined

    def test_silent_video_gets_track_as_audio(self, tmp_path):
        music = self._mp3(tmp_path)
        cmd = build_command("in.mp4", "out.mp4", has_audio=False, trending_audio=music, loop_audio_to=8)
        joined = " ".join(cmd)
        assert "anullsrc" not in joined and "amix" not in joined

    def test_missing_file_silently_ignored(self):
        cmd = build_command("in.mp4", "out.mp4", trending_audio="/nope/missing.mp3")
        joined = " ".join(cmd)
        assert "amix" not in joined and "0:a?" in cmd

    def _audio_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def _seed_tracks(self, s, tmp_path):
        from app.models import AudioTrack

        live = AudioTrack(name="hit", file_path=self._mp3(tmp_path, "hit.mp3"), use_count=5)
        fresh = AudioTrack(name="new", file_path=self._mp3(tmp_path, "new.mp3"), use_count=0)
        off = AudioTrack(name="off", file_path=self._mp3(tmp_path, "off.mp3"), is_active=False)
        ghost = AudioTrack(name="ghost", file_path="/nope/gone.mp3")
        s.add_all([live, fresh, off, ghost])
        s.commit()

    def test_pick_prefers_usable_and_least_used(self, tmp_path):
        from app.tasks.sync_helpers import pick_audio

        s = self._audio_session()
        self._seed_tracks(s, tmp_path)
        seen = {pick_audio(s).name for _ in range(20)}
        # Only usable tracks ever surface; ghost/off never picked.
        assert seen <= {"hit", "new"}
        # Least-used dominates the weighting.
        assert sum(1 for _ in range(40) if pick_audio(s).name == "new") > 20

    def test_pick_empty_when_nothing_usable(self, tmp_path):
        from app.models import AudioTrack
        from app.tasks.sync_helpers import pick_audio

        s = self._audio_session()
        s.add(AudioTrack(name="gone", file_path="/nope/gone.mp3"))
        s.commit()
        assert pick_audio(s) is None

    def test_resolve_guards(self, tmp_path):
        from app.tasks.sync_helpers import resolve_audio

        s = self._audio_session()
        self._seed_tracks(s, tmp_path)
        hit = resolve_audio(s, "hit")
        assert hit is not None and hit.file_path.endswith("hit.mp3")
        assert resolve_audio(s, "off") is None
        assert resolve_audio(s, "ghost") is None
        assert resolve_audio(s, "nope") is None
        assert resolve_audio(s, "") is None
        assert resolve_audio(s, None) is None


class TestEffectiveDuration:
    def test_trim_window(self):
        from app.services.video_processor import effective_output_duration

        assert effective_output_duration(20.0, 2.0, 8.0) == 6.0
        assert effective_output_duration(20.0, None, 8.0) == 8.0

    def test_start_only_and_plain(self):
        from app.services.video_processor import effective_output_duration

        assert effective_output_duration(20.0, 5.0, None) == 15.0
        assert effective_output_duration(20.0, None, None) == 20.0

    def test_nonsense_trims_clamped(self):
        from app.services.video_processor import effective_output_duration

        assert effective_output_duration(20.0, 30.0, None) == 0.0
        assert effective_output_duration(20.0, 8.0, 5.0) == 12.0  # end<=start ignored


class _FakeIGClient:
    """Stand-in for instagrapi.Client (no network). Records calls."""

    made: list = []

    def __init__(self):
        self.calls: list = []
        self.settings: dict = {}
        self.fail_feed = 0
        self.feed_calls = 0
        _FakeIGClient.made.append(self)

    def set_device(self, d):
        self.calls.append(("set_device", d))

    def set_proxy(self, u):
        self.calls.append(("proxy", u))

    def load_settings(self, p):
        self.calls.append(("load", p))

    def get_timeline_feed(self):
        self.feed_calls += 1
        self.calls.append(("feed",))
        if self.feed_calls <= self.fail_feed:
            raise TimeoutError("boom")
        return {"ok": 1}

    def login(self, u, p):
        self.calls.append(("login", u))
        return True

    def dump_settings(self, p):
        self.calls.append(("dump", p))

    def account_edit(self, **kw):
        self.calls.append(("edit", kw))
        return True

    def account_change_picture(self, p):
        self.calls.append(("pic", str(p)))
        return True

    def account_set_private(self):
        self.calls.append(("private",))
        return True

    def account_set_public(self):
        self.calls.append(("public",))
        return True


class TestApplyProfile:
    def _svc(self, monkeypatch):
        import instagrapi

        from app.services.instagram_service import InstagramService

        _FakeIGClient.made.clear()
        monkeypatch.setattr(instagrapi, "Client", _FakeIGClient)
        monkeypatch.setattr("time.sleep", lambda s: None)
        return InstagramService()

    def test_full_apply_sends_only_set_fields(self, monkeypatch, tmp_path):
        pic = tmp_path / "pic.jpg"
        pic.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        svc = self._svc(monkeypatch)
        err = svc.apply_profile(
            "u", "p", biography="hey", external_url="https://t.me/x",
            full_name=" Brand ", make_private=True, picture_path=str(pic),
        )
        assert err == ""
        cl = _FakeIGClient.made[-1]
        kinds = [c[0] for c in cl.calls]
        assert "login" not in kinds  # healthy session reused
        edit = next(c[1] for c in cl.calls if c[0] == "edit")
        assert edit == {"biography": "hey", "external_url": "https://t.me/x", "full_name": "Brand"}
        assert ("pic", str(pic)) in cl.calls
        assert ("private",) in cl.calls and ("public",) not in kinds

    def test_empty_apply_is_noop_success(self, monkeypatch):
        svc = self._svc(monkeypatch)
        assert svc.apply_profile("u", "p") == ""
        cl = _FakeIGClient.made[-1]
        kinds = [c[0] for c in cl.calls]
        assert "feed" in kinds
        assert not ({"edit", "pic", "private", "public", "login"} & set(kinds))

    def test_missing_picture_fails_before_any_call(self, monkeypatch):
        svc = self._svc(monkeypatch)
        err = svc.apply_profile("u", "p", biography="x", picture_path="/nope/gone.jpg")
        assert err.startswith("picture:")
        assert _FakeIGClient.made == []

    def test_public_path_and_error_passthrough(self, monkeypatch):
        import instagrapi

        svc = self._svc(monkeypatch)
        assert svc.apply_profile("u", "p", make_private=False) == ""
        cl = _FakeIGClient.made[-1]
        assert ("public",) in [c if isinstance(c, tuple) and len(c) == 1 else c for c in cl.calls]

        class Boom(_FakeIGClient):
            def account_edit(self, **kw):
                raise Exception("challenge_required: verify")

        monkeypatch.setattr(instagrapi, "Client", Boom)
        err = svc.apply_profile("u", "p", biography="x")
        assert err.startswith("challenge")

    def test_dead_session_falls_back_to_login(self, monkeypatch):
        import instagrapi

        class Dead(_FakeIGClient):
            def get_timeline_feed(self):
                self.calls.append(("feed",))
                raise Exception("login_required: expired")

        monkeypatch.setattr(instagrapi, "Client", Dead)
        monkeypatch.setattr("time.sleep", lambda s: None)

        from app.services.instagram_service import InstagramService

        svc = InstagramService()
        assert svc.apply_profile("u", "p", biography="x") == ""
        kinds = [c[0] for c in Dead.made[-1].calls]
        assert "login" in kinds and "edit" in kinds


class TestRateLimitWiring:
    def test_login_brute_force_trips_429(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            codes = [
                client.post(
                    "/api/v1/auth/login", json={"username": "nope", "password": "nope"}
                ).status_code
                for _ in range(7)
            ]
        assert 401 in codes  # wrong creds rejected...
        assert codes[-1] == 429  # ...and the 6th+ rapid hit is rate-limited

    def test_slowapi_middleware_installed(self):
        from slowapi.middleware import SlowAPIMiddleware

        from app.main import app

        assert any(
            getattr(m, "cls", None) is SlowAPIMiddleware for m in app.user_middleware
        )


class TestAnalyticsQueries:
    def test_account_comparison_runs(self):
        import asyncio
        import datetime as dt

        async def go():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.database import Base
            from app.models import Account, Post, PostStatus, Video
            from app.services import analytics_service

            engine = create_async_engine("sqlite+aiosqlite://")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as s:
                s.add(Account(username="cmp1", password_enc="x"))
                s.add(Video(original_filename="v.mp4", raw_path="/tmp/v.mp4", md5_hash="cmp1"))
                await s.flush()
                acc_id = (await s.execute(select(Account).where(Account.username == "cmp1"))).scalar_one().id
                vid_id = (await s.execute(select(Video).where(Video.md5_hash == "cmp1"))).scalar_one().id
                s.add(Post(
                    video_id=vid_id, account_id=acc_id, status=PostStatus.posted,
                    posted_at=dt.datetime.now(dt.timezone.utc),
                    views_7d=100, likes_7d=10, engagement_rate=10.0,
                ))
                await s.commit()
                rows = await analytics_service.account_comparison(s)
                assert rows and rows[0]["username"] == "cmp1"
                assert rows[0]["posts"] == 1 and rows[0]["views"] == 100
            await engine.dispose()

        asyncio.run(go())


class TestProxyImport:
    def _ok(self, line, default="http"):
        from app.services.proxy_service import parse_proxy_line

        spec, err = parse_proxy_line(line, default)
        assert err is None, (line, err)
        assert spec is not None
        return spec

    def _bad(self, line, default="http"):
        from app.services.proxy_service import parse_proxy_line

        spec, err = parse_proxy_line(line, default)
        assert spec is None and err not in (None, "blank/comment")
        return err

    def test_shapes(self):
        assert self._ok("1.2.3.4:8080") == (
            {"scheme": "http", "host": "1.2.3.4", "port": 8080,
             "username": "", "password": "", "country": ""})
        assert self._ok("socks5://1.2.3.4:1080")["scheme"] == "socks5"
        assert self._ok("https://1.2.3.4:443")["scheme"] == "https"
        assert self._ok("1.2.3.4:8080:u:p")["username"] == "u"
        assert self._ok("u:p@1.2.3.4:8080") == {
            "scheme": "http", "host": "1.2.3.4", "port": 8080,
            "username": "u", "password": "p", "country": ""}
        assert self._ok("socks5://u:p@h:1")["password"] == "p"
        assert self._ok("9.9.9.9:1080", "socks5")["scheme"] == "socks5"

    def test_country_suffix_comment_blank(self):
        from app.services.proxy_service import parse_proxy_line

        assert self._ok("1.2.3.4:8080 |de")["country"] == "DE"
        assert self._ok("1.2.3.4:8080 #us")["country"] == "US"
        assert parse_proxy_line("# just a comment") == (None, "blank/comment")
        assert parse_proxy_line("   ") == (None, "blank/comment")

    def test_rejections(self):
        assert self._bad("ftp://h:1").startswith("bad scheme")
        assert self._bad("nope") == "want host:port or host:port:user:pass"
        assert self._bad("h:99999") == "port out of range"
        assert self._bad("h:notaport") == "bad port"
        assert self._bad("h:1:u") == "want host:port or host:port:user:pass"
        assert self._bad("http://:8080") == "empty host"

    def test_fingerprint_normalizes(self):
        from app.services.proxy_service import proxy_fingerprint as f

        assert f("https", "H", 1) == f("http", "h", 1)
        assert f("http", "a", 1) != f("http", "a", 2)
        assert f("http", "a", 1) != f("socks5", "a", 1)


class TestProxyEngine:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def _proxy(self, s, url="http://1.1.1.1:8080", **kw):
        from app.models import Proxy, ProxyProtocol

        p = Proxy(url=url, protocol=ProxyProtocol.http, fail_count=0, **kw)
        s.add(p)
        s.commit()
        return p.id

    def test_looks_like_proxy_error(self):
        from app.tasks.sync_helpers import looks_like_proxy_error as looks

        assert looks("generic: ProxyError: tunnel failed") is True
        assert looks("generic: ConnectTimeout on POST") is True
        assert looks("throttled: slow down") is False
        assert looks("challenge_required: ...") is False
        assert looks("") is False

    def test_rank_prefers_clean_record(self):
        from app.tasks.sync_helpers import rank_spare_proxies as rank

        a = {"proxy": "flaky", "load": 0, "country": "DE", "latency": 10, "fail_count": 3}
        b = {"proxy": "clean", "load": 5, "country": "US", "latency": 900, "fail_count": 0}
        # Country still dominates (no geo-hop), but among peers the clean wins.
        assert rank([a, b], "DE") == "flaky"
        assert rank([a, b], "") == "clean"

    def test_shared_streak_disables_and_parks(self):
        from app.models import Account, Proxy
        from app.tasks.sync_helpers import MAX_PROXY_FAILS, record_proxy_check

        s = self._session()
        pid = self._proxy(s)
        acc = Account(username="parkme", password_enc="x", proxy_id=pid)
        s.add(acc)
        s.commit()
        disabled = False
        for _ in range(MAX_PROXY_FAILS):
            disabled = record_proxy_check(s, s.get(Proxy, pid), False, error="boom")
        assert disabled is True
        p = s.get(Proxy, pid)
        assert p is not None
        assert p.is_active is False and p.is_healthy is False
        assert p.last_error == "boom"
        a = s.get(Account, acc.id)
        assert a is not None and a.cooldown_until is not None
        # Success heals the streak for a re-enabled proxy.
        p.is_active = True
        s.commit()
        healed = s.get(Proxy, pid)
        assert healed is not None
        assert record_proxy_check(s, healed, True, latency_ms=42) is False
        p = s.get(Proxy, pid)
        assert p is not None
        assert (p.fail_count, p.is_healthy, p.latency_ms, p.last_error) == (0, True, 42, None)

    def test_resolve_proxy_object(self):
        from app.models import Proxy
        from app.tasks.sync_helpers import account_reachable, resolve_proxy, resolve_proxy_url

        s = self._session()
        pid = self._proxy(s)
        from app.models import Account

        acc = Account(username="r1", password_enc="x", proxy_id=pid)
        s.add(acc)
        s.commit()
        acc = s.get(Account, acc.id)
        assert isinstance(resolve_proxy(s, acc), Proxy)
        assert resolve_proxy_url(s, acc) == "http://1.1.1.1:8080"
        assert account_reachable(s, acc) is True


class TestProxyImportEndpoint:
    def test_bulk_import_dedupes_and_reports(self):
        import uuid

        from fastapi.testclient import TestClient

        from app.api.deps import get_current_admin
        from app.main import app

        tag = uuid.uuid4().hex[:10]
        text = (
            "# comment line\n"
            "\n"
            f"{tag}a.test:8080\n"
            f"socks5://{tag}b.test:1080 |DE\n"
            f"{tag}c.test:1:u:p\n"
            f"{tag}a.test:8080\n"
            "not a proxy!!!\n"
        )
        app.dependency_overrides[get_current_admin] = lambda: "admin"
        try:
            with TestClient(app) as client:
                r1 = client.post(
                    "/api/v1/proxies/import",
                    files={"file": ("list.txt", text, "text/plain")},
                    data={"default_protocol": "http"},
                )
                assert r1.status_code == 200, r1.text
                body = r1.json()
                assert body["added"] == 3, body
                assert body["duplicates_skipped"] == 1, body
                assert any(e["reason"] != "duplicate" for e in body["errors"])
                rows = client.get("/api/v1/proxies").json()
                mine = [p for p in rows if ".test:" in (p["url"] or "")]
                assert len(mine) == 3
                by_url = {p["url"]: p for p in mine}
                assert by_url[f"http://{tag}a.test:8080"]["username"] is None
                assert by_url[f"socks5://{tag}b.test:1080"]["country"] == "DE"
                assert by_url[f"http://{tag}c.test:1"]["username"] == "u"
                # Re-import is fully idempotent.
                r2 = client.post(
                    "/api/v1/proxies/import",
                    files={"file": ("list.txt", text, "text/plain")},
                    data={"default_protocol": "http"},
                )
                assert r2.json()["added"] == 0
        finally:
            app.dependency_overrides.clear()


class TestAutoPool:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def test_country_gate(self):
        from app.tasks.sync_helpers import pool_allows_country as gate

        assert gate("DE", "", "DE", True) is True
        assert gate("", "DE", "DE", True) is True  # source default counts
        assert gate("US", "", "DE", True) is False
        assert gate("", "", "DE", True) is False
        assert gate("US", "", "DE", False) is True  # not required: all pass
        assert gate("US", "", "", True) is True  # no pool country: all pass

    def test_get_setting(self):
        from app.models import Setting
        from app.tasks.sync_helpers import get_setting

        s = self._session()
        assert get_setting(s, "pool_country", "") == ""
        s.add(Setting(key="pool_country", value="DE"))
        s.commit()
        assert get_setting(s, "pool_country", "") == "DE"

    def test_purge_only_old_inactive_auto(self):
        import datetime as dt

        from app.models import Proxy, ProxyProtocol
        from app.tasks.sync_helpers import purge_stale_auto_proxies

        s = self._session()
        old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
        fresh = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)

        def mk(url, source, active, checked):
            p = Proxy(url=url, protocol=ProxyProtocol.http, source=source,
                      is_active=active, is_healthy=False, fail_count=9,
                      last_checked=checked)
            s.add(p)
            return p

        mk("http://old-auto:1", "list-a", False, old)     # reaped
        mk("http://manual:1", "manual", False, old)       # immortal
        mk("http://legacy:1", None, False, old)           # pre-feature rows immortal
        mk("http://fresh:1", "list-a", False, fresh)      # too young
        mk("http://active:1", "list-a", True, old)        # active rows kept
        mk("http://never:1", "list-a", False, None)       # unchecked kept
        s.commit()

        assert purge_stale_auto_proxies(s) == 1
        left = sorted(p.url for p in s.execute(select(Proxy)).scalars().all())
        assert left == [
            "http://active:1", "http://fresh:1", "http://legacy:1",
            "http://manual:1", "http://never:1",
        ]


class TestCrypto:
    def test_roundtrip(self):
        token = encrypt_secret("s3cret")
        assert token != "s3cret"
        assert decrypt_secret(token) == "s3cret"

    def test_empty_passthrough(self):
        assert encrypt_secret(None) is None
        assert decrypt_secret(None) is None
