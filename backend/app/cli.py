"""Administrative CLI.

    python -m app.cli reset-password <username>
    python -m app.cli create-admin <username>
    python -m app.cli list-users
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.config import get_settings
from app.core.security import hash_password, now_iso, validate_password_policy
from app.db.connection import connect
from app.db.migrations import run_migrations
from app.db.repos import sessions as sessions_repo
from app.db.repos import users as users_repo


def _prompt_password(username: str) -> str:
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    error = validate_password_policy(password, username)
    if error:
        sys.exit(error)
    return password


async def reset_password(username: str) -> int:
    settings = get_settings()
    async with connect(settings.db_path) as db:
        await run_migrations(db, now_iso())
        user = await users_repo.get_by_username(db, username)
        if user is None:
            print(f"User not found: {username}", file=sys.stderr)
            return 1
        password = _prompt_password(username)
        now = now_iso()
        await users_repo.update_fields(
            db, user["id"], now, password_hash=hash_password(password, settings.bcrypt_rounds),
            password_changed_at=now, failed_logins=0, locked_until=None, is_active=1,
        )
        await sessions_repo.revoke_all_for_user(db, user["id"], now)
    print(f"Password updated for {username}; all sessions revoked.")
    return 0


async def create_admin(username: str) -> int:
    settings = get_settings()
    async with connect(settings.db_path) as db:
        await run_migrations(db, now_iso())
        if await users_repo.get_by_username(db, username):
            print(f"User already exists: {username}", file=sys.stderr)
            return 1
        password = _prompt_password(username)
        await users_repo.create(db, username, hash_password(password, settings.bcrypt_rounds), "admin", now_iso())
    print(f"Admin user {username} created.")
    return 0


async def list_users() -> int:
    settings = get_settings()
    async with connect(settings.db_path) as db:
        await run_migrations(db, now_iso())
        users = await users_repo.list_all(db)
    print(f"{'ID':<5}{'USERNAME':<32}{'ROLE':<10}{'ACTIVE':<8}{'MFA':<5}LAST LOGIN")
    for u in users:
        print(f"{u['id']:<5}{u['username']:<32}{u['role']:<10}{'yes' if u['is_active'] else 'no':<8}{'yes' if u['totp_enabled'] else 'no':<5}{u['last_login_at'] or '-'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="TunnBox admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reset-password").add_argument("username")
    sub.add_parser("create-admin").add_argument("username")
    sub.add_parser("list-users")
    args = parser.parse_args(argv)
    if args.command == "reset-password":
        return asyncio.run(reset_password(args.username))
    if args.command == "create-admin":
        return asyncio.run(create_admin(args.username))
    return asyncio.run(list_users())


if __name__ == "__main__":
    sys.exit(main())
