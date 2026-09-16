"""Create an Instagram API session from a browser sessionid cookie.

This bypasses the password login flow entirely — useful for fresh accounts
where Instagram's device-verification bloks flow blocks API logins.

Steps:
  1. Log into instagram.com in your browser (any PC with a residential IP).
  2. Press F12 -> Application tab -> Cookies -> https://www.instagram.com
  3. Copy the value of the `sessionid` cookie.
  4. Run:
         python session_from_browser.py <ig_username> <sessionid_cookie>
  5. Copy the produced file (note: dots in the username become
     underscores, e.g. deer.9693176 -> deer_9693176.json) to the server:
         backend/media/sessions/<safe-username>.json
  6. Press "Test session" in the dashboard — it should report valid.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.utils.instagram_helpers import device_settings_for, session_path_for  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    username, sessionid = sys.argv[1], sys.argv[2]

    from instagrapi import Client

    cl = Client()
    cl.set_device(device_settings_for(username))
    cl.delay_range = [1, 3]

    print(f"Building session for {username} from browser sessionid…")
    try:
        cl.login_by_sessionid(sessionid)
    except Exception as exc:  # noqa: BLE001 — print a friendly hint and exit
        print(f"Failed: {exc}")
        print("The cookie is probably expired or copied incompletely.")
        print("Log into instagram.com again and copy the FULL sessionid value.")
        sys.exit(1)

    # session_path_for joins root + "sessions", so pass cwd to get ./sessions/<safe>.json
    out = Path(session_path_for(username, os.getcwd()))
    out.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(str(out))
    print(f"\nOK — logged in as {cl.username}, session saved to {out}")
    print("Next steps:")
    print(f"  1. Copy {out} to the server as:")
    print(f"     media/sessions/{out.name}")
    print("  2. In the dashboard press 'Test session' — it should say the session is valid.")


if __name__ == "__main__":
    main()
