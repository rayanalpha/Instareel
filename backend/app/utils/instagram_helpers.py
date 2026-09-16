"""Session persistence + anti-detection helpers for instagrapi."""
import logging
import os

log = logging.getLogger("igfunnel.instagram")

# Must track the newest instagrapi release: Instagram rejects logins from
# outdated app versions ("Your version of Instagram is out of date").
# Values below mirror instagrapi 3.0.2 config defaults (Instagram 446.x,
# Pixel 8 Pro / Android 14). Only the per-account `device`/`uuid` vary.
APP_VERSION = "446.0.0.49.77"
VERSION_CODE = "385211303"
BLOKS_VERSIONING_ID = "935a519904e9017324cdedb64a283a3c2c1a3d5b0bbc698b451f5aef72cc11df"
ANDROID_VERSION = 34
ANDROID_RELEASE = "14"
DPI = "480dpi"
RESOLUTION = "1344x2992"
MANUFACTURER = "Google/google"
MODEL = "Pixel 8 Pro"
CPU = "husky"


def session_path_for(username: str, media_root: str) -> str:
    d = os.path.join(media_root, "sessions")
    os.makedirs(d, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    return os.path.join(d, f"{safe}.json")


def device_settings_for(username: str) -> dict:
    """Deterministic per-account device fingerprint (stable across restarts).

    Hardware profile matches instagrapi defaults; only `device` and `uuid`
    vary per account so fingerprints stay consistent for each account.
    """
    import hashlib

    h = hashlib.md5(username.encode()).hexdigest()
    return {
        "app_version": APP_VERSION,
        "version_code": VERSION_CODE,
        "bloks_versioning_id": BLOKS_VERSIONING_ID,
        "android_version": ANDROID_VERSION,
        "android_release": ANDROID_RELEASE,
        "dpi": DPI,
        "resolution": RESOLUTION,
        "manufacturer": MANUFACTURER,
        "device": f"husky_{h[:4]}",
        "model": MODEL,
        "cpu": CPU,
        "uuid": h,
    }
