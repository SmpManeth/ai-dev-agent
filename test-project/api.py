"""Minimal API using username validation."""

from validators import validate_username


def register_user(username: str) -> dict:
    ok, err = validate_username(username)
    if not ok:
        return {"success": False, "error": err}
    return {"success": True, "username": username}
