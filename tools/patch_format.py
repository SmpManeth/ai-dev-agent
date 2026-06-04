"""Normalize LLM-generated unified diffs for apply."""

from __future__ import annotations

import re
from pathlib import Path

from tools.patch_guard import extract_diff_paths

_HUNK_SHORT = re.compile(r"^@@\s+-(\d+)\s+\+(\d+)\s*@@?$")
_HUNK_BROKEN = re.compile(r"^@@\s+-(\d+)\s+\+(\d+)$")


def fix_hunk_body_prefixes(diff: str) -> str:
    """
    Ensure hunk body lines use unified-diff prefixes (space / - / +).

    LLMs often omit the leading space on context lines, which makes git report
    "corrupt patch at line N".
    """
    lines = diff.splitlines()
    out: list[str] = []
    in_hunk = False
    last_was_plus = False

    for line in lines:
        if line.startswith("@@"):
            in_hunk = True
            last_was_plus = False
            out.append(line)
            continue
        if line.startswith("---") or line.startswith("+++"):
            in_hunk = False
            last_was_plus = False
            out.append(line)
            continue
        if in_hunk:
            if line.startswith("+"):
                last_was_plus = True
                out.append(line)
                continue
            if line.startswith("-"):
                last_was_plus = False
                out.append(line)
                continue
            if line.startswith(" "):
                last_was_plus = False
                out.append(line)
                continue
            if not line:
                out.append("+")
                last_was_plus = True
                continue
            if last_was_plus:
                out.append(f"+{line}")
                last_was_plus = True
            else:
                out.append(f" {line}")
                last_was_plus = False
            continue
        out.append(line)

    return "\n".join(out) + ("\n" if out else "")


def normalize_unified_diff(diff: str) -> str:
    """Fix common malformed unified diff patterns from LLM output."""
    lines: list[str] = []
    for raw in diff.splitlines():
        line = raw
        # Only strip leading junk on +/- lines, not context lines (need leading space)
        if raw.startswith("-") and not raw.startswith("---"):
            line = "-" + raw[1:].lstrip()
        elif raw.startswith("+") and not raw.startswith("+++"):
            line = "+" + raw[1:].lstrip()

        stripped = line.strip()
        if stripped.startswith("@@"):
            m = _HUNK_SHORT.match(stripped)
            if m:
                line = f"@@ -{m.group(1)},1 +{m.group(2)},1 @@"
            else:
                m2 = _HUNK_BROKEN.match(stripped)
                if m2:
                    line = f"@@ -{m2.group(1)},1 +{m2.group(2)},1 @@"

        lines.append(line)

    return fix_hunk_body_prefixes("\n".join(lines) + ("\n" if lines else ""))


def build_single_hunk_diff(path: str, old_line: str, new_line: str) -> str:
    """Build a minimal valid unified diff for a one-line replacement."""
    return (
        f"--- {path}\n"
        f"+++ {path}\n"
        f"@@ -1,1 +1,1 @@\n"
        f"-{old_line}\n"
        f"+{new_line}\n"
    )


def repair_diff_if_needed(diff: str, files_read: dict[str, str]) -> str:
    """
    Normalize diff; if still not apply-friendly, rebuild single-file one-line hunks.
    """
    normalized = normalize_unified_diff(diff)
    removed: list[str] = []
    added: list[str] = []
    for line in normalized.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])

    paths = extract_diff_paths(normalized)
    if len(paths) == 1 and len(removed) == len(added) and removed:
        path = paths[0]
        content = files_read.get(path, "")
        if all(old in content for old in removed):
            # Rebuild clean hunks with correct line numbers
            parts = [f"--- {path}", f"+++ {path}"]
            for old, new in zip(removed, added, strict=True):
                idx = content.find(old)
                if idx == -1:
                    continue
                line_no = content[:idx].count("\n") + 1
                parts.append(f"@@ -{line_no},1 +{line_no},1 @@")
                parts.append(f"-{old}")
                parts.append(f"+{new}")
            if len(parts) > 2:
                return "\n".join(parts) + "\n"

    return normalized


def fix_dev_null_headers(diff: str, repo_root: Path) -> str:
    """
    Rewrite false new-file headers when the target path already exists on disk.

    LLMs often emit ``--- /dev/null`` + ``+++ README.md`` for edits to existing files,
    which makes ``git apply`` fail with "already exists in working directory".
    """
    lines = diff.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in ("--- /dev/null", "--- dev/null") and i + 1 < len(lines):
            plus = lines[i + 1]
            if plus.startswith("+++"):
                path = plus[4:].strip().split("\t")[0]
                path = path.removeprefix("b/").removeprefix("a/")
                target = repo_root / path
                if target.is_file():
                    out.append(f"--- a/{path}")
                    out.append(f"+++ b/{path}")
                    i += 2
                    continue
        out.append(line)
        i += 1
    return "\n".join(out) + ("\n" if out else "")


def prepare_patch_for_apply(diff: str, repo_root: Path) -> str:
    """Normalize and repair a patch against the current repository tree."""
    prepared = normalize_unified_diff(diff)
    prepared = fix_dev_null_headers(prepared, repo_root)
    files_read: dict[str, str] = {}
    for path in extract_diff_paths(prepared):
        file_path = repo_root / path
        if file_path.is_file():
            files_read[path] = file_path.read_text(encoding="utf-8")
    return repair_diff_if_needed(prepared, files_read)
