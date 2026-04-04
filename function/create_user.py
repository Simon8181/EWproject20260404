"""CLI: create or update a user in config/ew_users.yaml

  cd repo && . .venv/bin/activate && python -m function.create_user simon developer
"""

from __future__ import annotations

import argparse
import getpass
import sys

from function.auth_roles import ROLES
from function.auth_users_store import set_password


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Add or update EW web user (PBKDF2 password).")
    p.add_argument("username", help="login id, e.g. simon")
    p.add_argument("role", choices=list(ROLES), help="developer | boss | broker")
    p.add_argument("-p", "--password", help="if omitted, prompt securely")
    args = p.parse_args(argv)
    pwd = args.password
    if not pwd:
        a = getpass.getpass("Password (min 6 chars): ")
        b = getpass.getpass("Again: ")
        if a != b:
            print("Passwords do not match.", file=sys.stderr)
            return 1
        pwd = a
    try:
        set_password(args.username, pwd, args.role)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"OK: user {args.username!r} role={args.role} written to config/ew_users.yaml")
    print("Set EW_SESSION_SECRET or EW_ADMIN_TOKEN in api.secrets.env so login cookies can be signed, then restart uvicorn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
