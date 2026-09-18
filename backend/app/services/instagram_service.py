"""instagrapi wrapper: login w/ session reuse, reel upload, bio edit, media info."""
import asyncio
import logging
import random

log = logging.getLogger("igfunnel.instagram")

CHALLENGE_MARKERS = ("challenge_required", "checkpoint_required", "feedback_required")
THROTTLE_MARKERS = ("throttled", "slow down", "try again later", "rate limit")


def _classify(exc: Exception) -> str:
    msg = f"{type(exc).__name__}: {exc}".lower()
    if any(m in msg for m in CHALLENGE_MARKERS):
        return "challenge"
    if "login_required" in msg or "login required" in msg:
        return "login_required"
    if any(m in msg for m in THROTTLE_MARKERS):
        return "throttled"
    return "generic"


def _feed_with_retry(cl) -> "tuple[bool, str]":
    """Timeline check that survives network blips without a fresh login.

    A fresh login is the strongest automation signal, so a transient network
    error must not trigger one: auth failures return immediately, anything
    else gets one retry after 5s. Returns (ok, kind).
    """
    import time

    try:
        cl.get_timeline_feed()
        return True, ""
    except Exception as exc:
        kind = _classify(exc)
        if kind in ("challenge", "login_required"):
            return False, kind
        time.sleep(5)
        try:
            cl.get_timeline_feed()
            return True, ""
        except Exception as exc2:
            return False, _classify(exc2)


def _safe_filename(settings_path: str) -> str:
    """Return the raw JSON of a session file (or ''), for diagnostics."""
    try:
        with open(settings_path, encoding="utf-8") as f:
            return f.read(200)
    except OSError:
        return ""


class InstagramService:
    def __init__(self, proxy_url: str | None = None, session_path: str | None = None):
        self.proxy_url = proxy_url
        self.session_path = session_path

    def _make_client(self, username: str, session_first: bool = True):
        from instagrapi import Client
        from app.utils.instagram_helpers import device_settings_for

        cl = Client()
        cl.delay_range = [1, 3]
        if self.proxy_url:
            cl.set_proxy(self.proxy_url)
        loaded = False
        if session_first and self.session_path:
            # Load the saved session BEFORE set_device so the file's own
            # device/uuid/cookies (not our generic fingerprint) win.
            try:
                cl.load_settings(self.session_path)
                loaded = bool(cl.settings)
                if loaded:
                    log.info("Loaded session file for %s", username)
            except FileNotFoundError:
                log.info("No session file yet for %s (path: %s)", username, self.session_path)
            except Exception as exc:
                log.warning("Session file for %s unreadable (%s); starting fresh", username, exc)
        if not loaded:
            # No usable session: fall back to the deterministic fingerprint.
            cl.set_device(device_settings_for(username))
        return cl

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Blocking (run in thread). Returns (ok, detail)."""
        import os

        cl = self._make_client(username)
        try:
            if self.session_path and os.path.exists(self.session_path):
                ok, _ = _feed_with_retry(cl)  # cheap session validity check
                if ok:
                    log.info("Reused session for %s", username)
                    return True, "session_reused"
                log.info("Stored session invalid for %s — logging in fresh", username)
            cl.login(username, password)
            if self.session_path:
                cl.dump_settings(self.session_path)
            return True, "logged_in"
        except Exception as exc:
            kind = _classify(exc)
            log.warning("Login failed for %s (%s): %s", username, kind, exc)
            return False, f"{kind}: {exc}"

    def check_session(self, username: str) -> bool:
        cl = self._make_client(username)
        try:
            ok, kind = _feed_with_retry(cl)
            log.info("Session check for %s: %s", username, "valid" if ok else f"invalid ({kind})")
            return ok
        except Exception as exc:
            log.warning("Session check for %s failed (%s): %s", username, _classify(exc), exc)
            return False

    def upload_reel(self, username: str, password: str, video_path: str, caption: str) -> tuple[str | None, str | None, str]:
        """Blocking. Returns (media_id, permalink, error)."""
        cl = self._make_client(username)
        try:
            ok, _ = _feed_with_retry(cl)
            if not ok:
                cl.login(username, password)
                if self.session_path:
                    try:
                        cl.dump_settings(self.session_path)
                    except Exception:
                        pass
            # Random pre-post delay is applied by the caller (needs async sleep).
            media = cl.clip_upload(video_path, caption=caption)
            media_id = str(getattr(media, "id", "") or getattr(media, "pk", ""))
            code = getattr(media, "code", None)
            permalink = f"https://www.instagram.com/reel/{code}/" if code else None
            return media_id or None, permalink, ""
        except Exception as exc:
            kind = _classify(exc)
            return None, None, f"{kind}: {exc}"

    def apply_bio(self, username: str, password: str, biography: str, external_url: str) -> str:
        cl = self._make_client(username)
        try:
            ok, _ = _feed_with_retry(cl)
            if not ok:
                cl.login(username, password)
            cl.account_edit(biography=biography, external_url=external_url or "")
            if self.session_path:
                try:
                    cl.dump_settings(self.session_path)
                except Exception:
                    pass
            return ""
        except Exception as exc:
            return f"{_classify(exc)}: {exc}"

    def media_info(self, username: str, media_id: str) -> dict:
        cl = self._make_client(username)
        try:
            info = cl.media_info(media_id).dict()
            return {
                "like_count": info.get("like_count", 0),
                "comment_count": info.get("comment_count", 0),
                "view_count": info.get("view_count") or info.get("play_count") or 0,
            }
        except Exception as exc:
            log.warning("media_info failed for %s: %s", media_id, exc)
            return {}


async def random_pre_post_delay(min_s: int, max_s: int) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


def classify_error(exc: Exception) -> str:
    return _classify(exc)
