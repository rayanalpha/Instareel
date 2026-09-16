"""One-off manual Instagram login helper.

Run this on YOUR PC (residential IP — Instagram rarely challenges home IPs),
then copy the produced session file to the server:

    backend/media/sessions/<username>.json

After that, "Test session" in the dashboard should report the session as
valid, and workers can post without a server-side login.

Usage (from the backend folder):
    python manual_login.py <ig_username> <ig_password>
    python manual_login.py <ig_username> <ig_password> <code_from_sms>

If Instagram asks for a verification code, grab it from SMS/email and run
the same command again passing it as the third argument.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings  # noqa: E402
from app.utils.instagram_helpers import device_settings_for  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    code = sys.argv[3] if len(sys.argv) > 3 else None

    from instagrapi import Client

    cl = Client()
    cl.set_device(device_settings_for(username))
    cl.delay_range = [1, 3]

    print(f"Logging in as {username} (app {cl.device_settings.get('app_version')})…")
    try:
        cl.login(username, password, verification_code=code)
    except Exception as exc:  # noqa: BLE001 — print a friendly hint and exit
        print(f"Login failed: {exc}")
        print("If this was a 2FA/challenge error, grab the code from SMS/email and run:")
        print(f'    python manual_login.py "{username}" <password> <code_from_sms>')
        sys.exit(1)

    out_dir = Path("sessions")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{username}.json"
    cl.dump_settings(str(out))
    print(f"\nOK — session saved to {out}")
    print("Next steps:")
    print(f"  1. Copy {out} to the server as:")
    print(f'     {settings.MEDIA_ROOT}/sessions/{username}.json')
    print("  2. In the dashboard press 'Test session' — it should say the session is valid.")


if __name__ == "__main__":
    main()
