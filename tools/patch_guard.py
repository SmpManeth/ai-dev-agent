"""Safety checks for proposed patches (no repo writes)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

RiskLevel = Literal["low", "medium", "high"]

# Exact relative paths blocked for patch apply (Step 3)
_APPLY_FORBIDDEN_EXACT: frozenset[str] = frozenset(
    {
        "composer.json",
        "package.json",
        "config/database.php",
    }
)

# Paths or fragments that must not be patched in Step 2
_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    ".env",
    ".env.",
    "credentials",
    "secret",
    "/auth/",
    "auth/",
    "authentication",
    "payment",
    "billing",
    "stripe",
    "migration",
    "migrations/",
    "schema",
    "database/migrations",
    "composer.lock",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
)

_DIFF_PATH_RE = re.compile(r"^(?:---|\+\+\+)\s+(?:[ab]/)?(.+?)(?:\s|$)", re.MULTILINE)


def _normalize_path(path: str) -> str:
    """Repository-relative path for guard checks."""
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lower()


_DOC_SUFFIXES: frozenset[str] = frozenset({".md", ".txt", ".rst", ".adoc"})
_DOC_BASENAMES: frozenset[str] = frozenset(
    {
        "readme",
        "changelog",
        "license",
        "contributing",
        "authors",
        "history",
    }
)


def is_documentation_path(path: str) -> bool:
    """True for markdown/text docs where large diffs are normal (e.g. README rewrites)."""
    normalized = _normalize_path(path)
    name = Path(normalized).name
    stem = Path(name).stem
    suffix = Path(name).suffix
    if suffix in _DOC_SUFFIXES:
        return True
    if stem in _DOC_BASENAMES:
        return True
    if normalized.startswith("docs/") or "/docs/" in normalized:
        return True
    return False


def paths_are_documentation_only(paths: list[str]) -> bool:
    return bool(paths) and all(is_documentation_path(p) for p in paths)


def is_forbidden_path(path: str) -> bool:
    """Return True if the path must not be modified."""
    normalized = _normalize_path(path)
    if normalized in _APPLY_FORBIDDEN_EXACT:
        return True
    name = normalized.rsplit("/", maxsplit=1)[-1]

    if name == ".env" or name.startswith(".env."):
        return True

    try:
        from tools.security_policy import is_path_blocked_by_policy

        if is_path_blocked_by_policy(path):
            return True
    except ImportError:
        pass

    for fragment in _FORBIDDEN_FRAGMENTS:
        if fragment in normalized:
            return True
    return False


def filter_allowed_files(paths: list[str]) -> tuple[list[str], list[str]]:
    """Split paths into allowed and blocked."""
    allowed: list[str] = []
    blocked: list[str] = []
    for path in paths:
        if is_forbidden_path(path):
            blocked.append(path)
        else:
            allowed.append(path)
    return allowed, blocked


def extract_diff_paths(unified_diff: str) -> list[str]:
    """Parse file paths from ---/+++ headers."""
    paths: list[str] = []
    for match in _DIFF_PATH_RE.finditer(unified_diff):
        raw = match.group(1).strip()
        if raw in ("/dev/null", "dev/null"):
            continue
        if raw not in paths:
            paths.append(raw)
    return paths


def diff_only_touches_files(unified_diff: str, allowed: set[str]) -> bool:
    """Ensure every path in the diff is in the allowed set."""
    for path in extract_diff_paths(unified_diff):
        normalized = path.lstrip("./")
        if normalized not in allowed and path not in allowed:
            return False
    return True


def normalize_risk_level(value: str) -> RiskLevel:
    """Coerce risk level to allowed enum."""
    lower = value.strip().lower()
    if lower in ("low", "medium", "high"):
        return lower  # type: ignore[return-value]
    return "high"
