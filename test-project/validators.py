"""Username validation helpers."""

import re

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

# Bug: error message says "email" instead of "username"
USERNAME_ERROR = "Invalid email format. Use 3-20 alphanumeric characters."


def validate_username(value: str) -> tuple[bool, str | None]:
    """Return (ok, error_message)."""
    if not value:
        return False, "Username is required."
    if not USERNAME_PATTERN.match(value):
        return False, USERNAME_ERROR
    return True, None
