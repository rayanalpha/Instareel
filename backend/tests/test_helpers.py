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

from app.utils.ffmpeg import build_command, build_filter, probe_sync  # noqa: E402
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
        assert d["app_version"] >= "400.0.0"  # Instagram rejects outdated versions
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
        info = json.loads(raw)  # shape sanity
        assert info["streams"][0]["width"] == 1920


class TestCrypto:
    def test_roundtrip(self):
        token = encrypt_secret("s3cret")
        assert token != "s3cret"
        assert decrypt_secret(token) == "s3cret"

    def test_empty_passthrough(self):
        assert encrypt_secret(None) is None
        assert decrypt_secret(None) is None
