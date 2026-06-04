"""Redact secrets from log lines and command output."""

from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*['\"]?[\w\-\./]+",
        r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
        r"ghp_[A-Za-z0-9]{20,}",
        r"gho_[A-Za-z0-9]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"xox[baprs]-[A-Za-z0-9\-]+",
        r"sk-[A-Za-z0-9]{20,}",
        r"x-access-token:[A-Za-z0-9]+@",
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    )
)


def mask_secrets(text: str, replacement: str = "[REDACTED]") -> str:
    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def mask_command(argv: list[str]) -> list[str]:
    return [mask_secrets(part) for part in argv]


def mask_context(context: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, str):
            out[key] = mask_secrets(value)
        elif isinstance(value, dict):
            out[key] = mask_context(value)
        elif isinstance(value, list):
            out[key] = [
                mask_secrets(v) if isinstance(v, str) else v for v in value
            ]
        else:
            out[key] = value
    return out
