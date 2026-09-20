"""Real FFmpeg end-to-end: generate fixtures, encode, probe outputs.

Slow-ish by design (each encode is seconds) — this is the suite that proves
every shipped effect preset, the trending-audio mixer, watermarks, trims and
thumbnails against the real encoder, not string matching.
"""
import json
import os
import subprocess

import pytest

from app.services.default_effects import DEFAULT_EFFECT_PRESETS
from app.utils import ffmpeg as ff


def _run(cmd, timeout=90):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=timeout)


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    src = str(d / "src.mp4")
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src])
    silent = str(d / "silent.mp4")
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", silent])
    music = str(d / "music.wav")
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", "sine=frequency=880:duration=6",
          "-c:a", "pcm_s16le", music])
    wm = str(d / "wm.png")
    from PIL import Image

    Image.new("RGB", (120, 60), (10, 200, 90)).save(wm)
    return {"dir": str(d), "src": src, "silent": silent, "music": music, "wm": wm}


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def _streams(info):
    return {s.get("codec_type"): s for s in info.get("streams", [])}


class TestProbe:
    def test_src_fixture(self, media):
        info = ff.probe_sync(media["src"])
        assert info["width"] == 320 and info["height"] == 240
        assert info["has_audio"] is True
        assert 3.5 < info["duration"] < 4.5


class TestPlainAndWatermark:
    def test_plain_encode(self, media, tmp_path):
        dst = str(tmp_path / "plain.mp4")
        ff.run_sync_with_progress(
            ff.build_command(media["src"], dst), 4.0, lambda *a: None)
        info = _probe(dst)
        ss = _streams(info)
        assert (ss["video"]["width"], ss["video"]["height"]) == (720, 1280)
        assert "audio" in ss

    def test_watermark_encode(self, media, tmp_path):
        dst = str(tmp_path / "wm.mp4")
        ff.run_sync_with_progress(
            ff.build_command(media["src"], dst, watermark_path=media["wm"]), 4.0, lambda *a: None)
        assert _streams(_probe(dst))["video"]["width"] == 720

    def test_progress_monotonic(self, media, tmp_path):
        seen = []
        ff.run_sync_with_progress(
            ff.build_command(media["src"], str(tmp_path / "p.mp4")), 4.0,
            lambda pct, stage: seen.append(pct))
        assert seen and all(0.0 <= v <= 100.0 for v in seen)
        assert max(seen) > 50.0


class TestAllPresetsEncode:
    """Every shipped preset must survive the real encoder at 720x1280."""

    @pytest.mark.parametrize("preset", [p["name"] for p in DEFAULT_EFFECT_PRESETS])
    def test_preset(self, media, tmp_path, preset):
        filt = next(p["ffmpeg_filter"] for p in DEFAULT_EFFECT_PRESETS if p["name"] == preset)
        dst = str(tmp_path / f"{preset}.mp4")
        cmd = ff.build_command(media["src"], dst, effect_filter=filt)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=120)
        v = _streams(_probe(dst))["video"]
        # Frame-adding presets intentionally change dimensions.
        expected = {"letterbox_cinema": (720, 1440), "white_frame": (744, 1304)}.get(
            preset, (720, 1280))
        assert (v["width"], v["height"]) == expected, preset


class TestTrendingAudioEncode:
    def test_mix_longer_music(self, media, tmp_path):
        dst = str(tmp_path / "mix.mp4")  # 6s music over 4s video
        ff.run_sync_with_progress(
            ff.build_command(media["src"], dst, trending_audio=media["music"],
                             music_volume=0.5, loop_audio_to=4.0), 4.0, lambda *a: None)
        info = _probe(dst)
        assert "audio" in _streams(info)
        assert abs(float(info["format"]["duration"]) - 4.0) < 0.6

    def test_duck_replaces(self, media, tmp_path):
        dst = str(tmp_path / "duck.mp4")
        ff.run_sync_with_progress(
            ff.build_command(media["src"], dst, trending_audio=media["music"],
                             duck_original=True, loop_audio_to=4.0), 4.0, lambda *a: None)
        assert "audio" in _streams(_probe(dst))

    def test_silent_video_gets_audio_stream(self, media, tmp_path):
        # Regression: the silent branch once dropped the audio map entirely.
        # NOTE: has_audio comes from probing in production — pass it explicitly.
        dst = str(tmp_path / "sil.mp4")
        info = ff.probe_sync(media["silent"])
        assert info["has_audio"] is False
        ff.run_sync_with_progress(
            ff.build_command(media["silent"], dst, has_audio=info["has_audio"]),
            4.0, lambda *a: None)
        assert "audio" in _streams(_probe(dst))

    def test_trim_duck_matches_trimmed_length(self, media, tmp_path):
        # Regression: music -t used raw length, freezing the tail on trims.
        dst = str(tmp_path / "trim.mp4")
        cmd = ff.build_command(media["src"], dst, trim_start=1.0, trim_end=3.0,
                               trending_audio=media["music"], duck_original=True,
                               loop_audio_to=2.0)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=120)
        dur = float(_probe(dst)["format"]["duration"])
        assert abs(dur - 2.0) < 0.6, dur

    def test_thumbnail(self, media, tmp_path):
        from app.services.video_processor import extract_thumbnail_sync

        dst = str(tmp_path / "th.jpg")
        extract_thumbnail_sync(media["src"], 4.0, dst)
        assert os.path.exists(dst) and os.path.getsize(dst) > 0


class TestParseHelpers:
    def test_time_token(self):
        from app.utils.ffmpeg import _parse_time_token

        assert _parse_time_token("frame= 10 time=00:00:02.50 bitrate=1", 10.0) == 25.0
        assert _parse_time_token("no time here", 10.0) is None
        assert _parse_time_token("time=00:00:01.00", 0) is None

    def test_probe_rejects_garbage(self, tmp_path):
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"not a video at all")
        with pytest.raises(RuntimeError):
            ff.probe_sync(str(bad))
