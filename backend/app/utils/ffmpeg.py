"""FFmpeg command builder + runner with progress parsing.

Both async (web API) and sync (Celery workers) runners are provided.
Celery must ONLY use the sync variants — never create an event loop in a task.
"""
import json
import logging
import os
import shlex
import subprocess

log = logging.getLogger("igfunnel.ffmpeg")

TARGET_W, TARGET_H = 720, 1280


def _parse_probe_json(raw: bytes) -> dict:
    info = json.loads(raw.decode() or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "has_audio": audio is not None,
    }


def probe_sync(path: str) -> dict:
    """Blocking ffprobe (Celery-safe)."""
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed — file is not a valid video")
    return _parse_probe_json(proc.stdout)


async def probe(path: str) -> dict:
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed — file is not a valid video")
    return _parse_probe_json(out)


def build_filter(
    effect_filter: str = "",
    custom_filters: str = "",
    color_grade: str = "",
    watermark_path: str | None = None,
    has_audio: bool = True,
) -> tuple[str, bool]:
    """Return (filter_complex, needs_watermark_input)."""
    parts: list[str] = []
    # Center-crop to 9:16 then scale to 720x1280.
    parts.append(
        "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H}"
    )
    if effect_filter.strip():
        parts.append(effect_filter.strip())
    if color_grade.strip():
        parts.append(color_grade.strip())
    if custom_filters.strip():
        parts.append(custom_filters.strip())
    parts.append("format=yuv420p")
    video_chain = ",".join(p for p in parts if p)
    if watermark_path:
        # [0:v]<chain>[v]; [1:v]scale=120:-1[wm]; [v][wm]overlay=W-w-20:20
        fc = (
            f"[0:v]{video_chain}[v];"
            f"[1:v]scale=120:-1[wm];"
            f"[v][wm]overlay=W-w-20:20[outv]"
        )
        return fc, True
    return f"[0:v]{video_chain}[outv]", False


def build_command(
    src: str,
    dst: str,
    trim_start: float | None = None,
    trim_end: float | None = None,
    effect_filter: str = "",
    custom_filters: str = "",
    color_grade: str = "",
    watermark_path: str | None = None,
    has_audio: bool = True,
    trending_audio: str | None = None,
    music_volume: float = 0.4,
    duck_original: bool = False,
    loop_audio_to: float | None = None,
) -> list[str]:
    """Build the ffmpeg command. Trending-audio modes (music file must exist):

    - mix (default): original audio at full volume + trending track at
      ``music_volume``, looped to the video length.
    - duck/replace (``duck_original=True``, or video without audio): the
      trending track becomes the only audio (at ``music_volume``).
    - no trending file: previous behavior is unchanged.
    """
    filter_complex, needs_wm = build_filter(
        effect_filter, custom_filters, color_grade,
        watermark_path if watermark_path and os.path.exists(watermark_path) else None,
        has_audio,
    )
    music = trending_audio if trending_audio and os.path.exists(trending_audio) else None
    vol = max(0.0, float(music_volume or 0.0))
    use_mix = bool(music and has_audio and not duck_original)

    cmd = ["ffmpeg", "-y"]
    if trim_start:
        cmd += ["-ss", str(trim_start)]
    if trim_end and trim_start is not None and trim_end > trim_start:
        cmd += ["-t", str(trim_end - trim_start)]
    elif trim_end:
        cmd += ["-t", str(trim_end)]
    cmd += ["-i", src]
    next_idx = 1
    if needs_wm:
        cmd += ["-i", watermark_path]
        next_idx += 1
    music_idx: int | None = None
    if music:
        if loop_audio_to and loop_audio_to > 0:
            # Loop the track and cut the input at exactly the video length.
            cmd += ["-stream_loop", "-1", "-t", str(loop_audio_to)]
        music_idx = next_idx
        cmd += ["-i", music]
        next_idx += 1

    audio_args: list[str]
    if use_mix and music_idx is not None:
        filter_complex += (
            f";[{music_idx}:a]volume={vol}[a1]"
            f";[0:a][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        audio_args = ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm"]
    elif music_idx is not None:
        # Trending track is the only audio (ducked original or silent video).
        audio_args = ["-map", f"{music_idx}:a", "-c:a", "aac", "-b:a", "128k",
                      "-af", f"volume={vol},loudnorm"]
        if not loop_audio_to:
            audio_args = ["-shortest"] + audio_args
    elif has_audio:
        audio_args = ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm"]
    else:
        audio_args = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:a", "aac"]

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-movflags", "+faststart",
    ]
    cmd += audio_args
    cmd += [dst]
    log.info("FFmpeg: %s", " ".join(shlex.quote(c) for c in cmd))
    return cmd


def _parse_time_token(line: str, duration: float) -> float | None:
    if "time=" not in line or duration <= 0:
        return None
    try:
        t = line.split("time=")[1].split()[0]
        h, m, s = t.split(":")
        secs = int(h) * 3600 + int(m) * 60 + float(s)
        return max(0.0, min(100.0, secs / duration * 100))
    except Exception:
        return None


def run_sync_with_progress(cmd: list[str], duration: float, on_progress) -> None:
    """Blocking ffmpeg runner (Celery-safe). Reads stderr line by line via Popen."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace", bufsize=1
    )
    assert proc.stderr is not None
    stderr_tail: list[str] = []
    for line in proc.stderr:
        line = line.strip()
        if line:
            stderr_tail.append(line[-500:])
            pct = _parse_time_token(line, duration)
            if pct is not None:
                on_progress(pct, "processing")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("FFmpeg failed: " + " | ".join(stderr_tail[-8:]))


async def run_with_progress(cmd: list[str], duration: float, on_progress) -> None:
    """Run ffmpeg, parsing `time=` tokens from stderr to report 0-100%."""
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    assert proc.stderr is not None
    stderr_tail: list[str] = []
    async for raw in proc.stderr:
        line = raw.decode(errors="replace").strip()
        if line:
            stderr_tail.append(line[-500:])
            pct = _parse_time_token(line, duration)
            if pct is not None:
                await on_progress(pct, "processing")
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed: " + " | ".join(stderr_tail[-8:]))
