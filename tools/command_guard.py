"""Validate subprocess commands against production allow/block lists."""

from __future__ import annotations

import shlex
from typing import Sequence

from tools.security_policy import SecurityViolation, get_hardening_policy


def _argv_to_string(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(a)) for a in argv)


def assert_command_allowed(argv: Sequence[str], *, label: str = "command") -> None:
    """Raise SecurityViolation if argv matches a blocked pattern or fails allowlist."""
    if not argv:
        raise SecurityViolation(f"Empty {label} is not allowed.")

    policy = get_hardening_policy()
    joined = _argv_to_string(argv)
    executable = str(argv[0]).strip().lower()
    base = executable.rsplit("/", maxsplit=1)[-1]

    for pattern in policy.blocked_command_patterns:
        if pattern.search(joined):
            raise SecurityViolation(
                f"Blocked {label}: matches dangerous pattern ({pattern.pattern})"
            )

    allowed = policy.allowed_command_prefixes
    if allowed:
        ok = False
        for prefix in allowed:
            p = prefix.strip().lower()
            if base == p or executable == p or joined.lower().startswith(p + " "):
                ok = True
                break
            if base.startswith(p) or base.endswith(f"/{p}"):
                ok = True
                break
            if f"/{p}" in executable:
                ok = True
                break
        if not ok:
            raise SecurityViolation(
                f"Command not in allowlist: {base}. Allowed prefixes: {', '.join(allowed)}"
            )


def is_command_allowed(argv: Sequence[str]) -> bool:
    try:
        assert_command_allowed(argv)
        return True
    except SecurityViolation:
        return False
