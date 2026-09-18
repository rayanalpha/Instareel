"""Create an Instagram API session from a browser sessionid cookie.

This bypasses the password login flow entirely — useful whenever
Instagram's device-verification bloks flow blocks API logins (fresh
accounts, datacenter IPs, new devices).

Typical use (on any PC with a residential IP):

    1. Log into instagram.com in your browser (the target account).
    2. Press F12 -> Application tab -> Cookies -> https://www.instagram.com
    3. Copy the value of the `sessionid` cookie and run:
           python session_from_browser.py <ig_username> <sessionid_cookie>

Alternatives:
    --cookies-file cookies.txt   Netscape cookies.txt or JSON export from a
                                 cookie-editor extension (avoids copy mistakes)
    --proxy http://user:pass@host:port
                                 route the verification through a proxy
    --retries N                  transient-error retries (default: 2)

The script sanitizes the cookie (quotes/whitespace/URL-encoding), verifies
it belongs to the given username, proves it with a real API call BEFORE
saving, and round-trips the saved file — so a bad cookie can never produce
a silently broken session file.
"""
import argparse
import os
import sys
import time
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).parent))

from app.services.instagram_service import classify_error  # noqa: E402
from app.utils.instagram_helpers import (  # noqa: E402
    device_settings_for,
    extract_sessionid,
    parse_cookies_file,
    sanitize_sessionid,
    session_path_for,
    sessionid_looks_valid,
)


def fail(msg: str, hint: str = "") -> NoReturn:
    print(f"\nFAILED: {msg}")
    if hint:
        print(f"Hint: {hint}")
    sys.exit(1)


def build_client(username: str, proxy: "str | None" = None):
    from instagrapi import Client

    cl = Client()
    cl.set_device(device_settings_for(username))
    cl.delay_range = [1, 3]
    if proxy:
        cl.set_proxy(proxy)
    return cl


def login_with_retry(cl, sessionid: str, retries: int) -> None:
    """login_by_sessionid, retrying transient errors only (never bad cookies)."""
    attempt = 0
    while True:
        try:
            cl.login_by_sessionid(sessionid)
            return
        except AssertionError as exc:
            # instagrapi's own format gate (^\\d+, len>30) — retrying is pointless.
            fail(f"Rejected sessionid format ({exc}).",
                 "Copy the FULL sessionid value from DevTools (it starts with digits). "
                 "If you pasted it by hand, use --cookies-file with a cookies.txt export instead.")
        except Exception as exc:  # noqa: BLE001
            kind = classify_error(exc)
            if kind in ("challenge", "login_required"):
                fail(f"Instagram demands verification ({kind}): {exc}",
                     "This cookie/account needs a human step: open instagram.com in the "
                     "same browser, complete the checkpoint, then copy a FRESH sessionid "
                     "and run again.")
            if kind == "throttled" or attempt >= retries:
                fail(f"Login error ({kind}): {exc}",
                     "The network/IP is rate-limited or the cookie expired. Wait a few "
                     "minutes, copy a fresh sessionid, or pass --proxy with a residential proxy.")
            attempt += 1
            print(f"Transient error ({kind}), retry {attempt}/{retries} in 5s…")
            time.sleep(5)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an IG API session from a browser cookie.")
    ap.add_argument("username", help="Instagram username (must own the cookie)")
    ap.add_argument("sessionid", nargs="?", default=None, help="sessionid cookie value")
    ap.add_argument("--cookies-file", default=None, help="Netscape cookies.txt or JSON export")
    ap.add_argument("--proxy", default=None, help="optional proxy URL for verification")
    ap.add_argument("--retries", type=int, default=2, help="transient-error retries (default: 2)")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the pre-save timeline proof call (gentle mode: for accounts "
                         "where any extra API call gets sessions killed; the username "
                         "ownership check and file round-trip still apply)")
    args = ap.parse_args()

    username = (args.username or "").strip().lstrip("@")
    if not username:
        fail("Empty username.", "Usage: python session_from_browser.py <ig_username> <sessionid>")

    # ---- 1. obtain + sanitize the sessionid ----
    sessionid: str | None = None
    if args.cookies_file:
        try:
            raw = Path(args.cookies_file).read_text(encoding="utf-8")
        except OSError as exc:
            fail(f"Cannot read cookies file: {exc}")
        cookies = parse_cookies_file(raw)
        if not cookies:
            fail("No cookies parsed from the file.",
                 "Export from instagram.com (not another site) as Netscape cookies.txt or JSON.")
        sessionid = extract_sessionid(cookies)
        if sessionid is None:
            fail("No usable sessionid in the file.",
                 "Make sure you are logged into instagram.com in that browser profile, "
                 "then export again.")
        print(f"Read {len(cookies)} cookies from file; sessionid found.")
    elif args.sessionid:
        sessionid = sanitize_sessionid(args.sessionid)
    else:
        fail("No sessionid given.",
             "Pass it as 2nd argument or use --cookies-file. See --help.")

    assert sessionid is not None
    if not sessionid_looks_valid(sessionid):
        fail("Malformed sessionid (must start with digits and be longer than 30 chars).",
             "Copy the FULL value — a truncated paste is the usual cause. "
             "Prefer --cookies-file to avoid copy mistakes.")

    # ---- 2. login ----
    cl = build_client(username, args.proxy)
    print(f"Logging in {username} via browser session…")
    login_with_retry(cl, sessionid, max(0, args.retries))

    # ---- 3. ownership check: the cookie must belong to THIS account ----
    server_user = (getattr(cl, "username", "") or "").strip()
    if not server_user:
        fail("Login returned no username.", "Copy a fresh sessionid and try again.")
    if server_user.lower() != username.lower():
        fail(f"Cookie belongs to @{server_user}, not @{username}.",
             "Log into the RIGHT account in the browser (check the avatar/username), "
             "then copy its sessionid — or fix the username argument.")

    # ---- 4. prove it with a real API call BEFORE saving ----
    # (skipped in --no-verify gentle mode: on hijack-sensitive accounts the
    # extra call itself can get all sessions killed)
    if not args.no_verify:
        try:
            cl.get_timeline_feed()
        except Exception as exc:  # noqa: BLE001
            fail(f"Session logged in but API calls fail ({classify_error(exc)}): {exc}",
                 "The cookie is half-valid (auth ok, API blocked). Complete any checkpoint "
                 "in the browser, copy a fresh sessionid, and retry — or rerun this same "
                 "command with --no-verify for one minimal-footprint attempt.")
    else:
        print("Gentle mode: skipping timeline proof (username match already confirmed).")

    # ---- 5. save with the exact filename the server expects ----
    out = Path(session_path_for(username, os.getcwd()))
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        cl.dump_settings(str(out))
    except Exception as exc:  # noqa: BLE001
        fail(f"Could not write {out}: {exc}")

    # ---- 6. round-trip: the file must load back with the cookie inside ----
    try:
        from instagrapi import Client as FreshClient

        probe = FreshClient()
        data = probe.load_settings(str(out)) or {}
        saved = ((data.get("cookies") or {}).get("sessionid") or "")
        if saved != sessionid:
            fail("Saved file does not contain the session cookie (round-trip mismatch).",
                 "Disk or permissions issue — check free space and try again.")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"Saved file failed to load back: {exc}")

    print(f"\nOK — verified as @{server_user}, session saved to {out}")
    print("Next steps:")
    print(f"  1. In the dashboard: Accounts -> Upload session, select {out.name}")
    print(f"     (or copy it to the server as media/sessions/{out.name})")
    print("  2. Press 'Test session' — it must report valid.")
    print("  3. If 'Test session' fails on the server, its IP is the problem —")
    print("     bind a residential proxy to the account and test again.")


if __name__ == "__main__":
    main()
