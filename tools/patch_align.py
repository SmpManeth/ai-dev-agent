"""Realign LLM unified diffs to on-disk file content (line numbers and context)."""

from __future__ import annotations

from tools.patch_guard import extract_diff_paths


def _lines_match(file_line: str, patch_line: str) -> bool:
    a = file_line.rstrip("\n\r")
    b = patch_line.rstrip("\n\r")
    if a == b:
        return True
    return a.strip() == b.strip()


def find_block_start(file_lines: list[str], block: list[str]) -> int | None:
    """Return 0-based index where contiguous block matches, or None."""
    if not block:
        return None
    n = len(block)
    limit = len(file_lines) - n + 1
    for i in range(limit):
        if all(_lines_match(file_lines[i + j], block[j]) for j in range(n)):
            return i
    return None


def _parse_removed_added(diff: str) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return removed, added


def rebuild_single_file_diff(
    path: str,
    content: str,
    removed: list[str],
    added: list[str],
    *,
    context_lines: int = 3,
) -> str | None:
    """
    Build a unified diff with correct line numbers and file-exact minus lines.

    Works when removed lines form one contiguous block in the file (counts may differ).
    """
    if not removed or not added:
        return None

    file_lines = content.splitlines()
    start = find_block_start(file_lines, removed)
    if start is None:
        return None

    ctx_start = max(0, start - context_lines)
    ctx_end = min(len(file_lines), start + len(removed) + context_lines)
    old_count = ctx_end - ctx_start
    new_count = old_count - len(removed) + len(added)

    parts = [f"--- {path}", f"+++ {path}"]
    parts.append(f"@@ -{ctx_start + 1},{old_count} +{ctx_start + 1},{new_count} @@")

    for i in range(ctx_start, start):
        parts.append(f" {file_lines[i]}")
    for i in range(start, start + len(removed)):
        parts.append(f"-{file_lines[i]}")
    for line in added:
        parts.append(f"+{line}")
    for i in range(start + len(removed), ctx_end):
        parts.append(f" {file_lines[i]}")

    return "\n".join(parts) + "\n"


def realign_diff_to_files(diff: str, files_read: dict[str, str]) -> str:
    """Realign a single-file diff when the removed block exists on disk."""
    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return diff
    path = paths[0]
    content = files_read.get(path, "")
    if not content:
        return diff
    removed, added = _parse_removed_added(diff)
    if not removed:
        return diff
    rebuilt = rebuild_single_file_diff(path, content, removed, added)
    return rebuilt if rebuilt else diff
