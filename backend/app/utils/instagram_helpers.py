"""Session persistence + anti-detection helpers for instagrapi."""
import logging
import os

log = logging.getLogger("igfunnel.instagram")


def session_path_for(username: str, media_root: str) -> str:
    d = os.path.join(media_root, "sessions")
    os.makedirs(d, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    return os.path.join(d, f"{safe}.json")


def device_settings_for(username: str) -> dict:
    """Deterministic per-account device fingerprint (stable across restarts)."""
    import hashlib

    h = hashlib.md5(username.encode()).hexdigest()
    return {
        "app_version": "302.0.0.34.111",
        "android_version": 28,
        "android_release": "9.0",
        "dpi": "420dpi",
        "resolution": "1080x1920",
        "manufacturer": "samsung",
        "device": f"starlte_{h[:4]}",
        "model": "SM-G960F",
        "cpu": "exynos9810",
        "version_code": "471750796",
        "uuid": h,
    }
