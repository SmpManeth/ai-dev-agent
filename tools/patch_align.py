"""Realign LLM unified diffs to on-disk file content (line numbers and context)."""

from __future__ import annotations

import re

from tools.patch_guard import extract_diff_paths

_SWIPER_INIT = re.compile(r"new\s+Swiper\s*\(", re.I)
_LOOP_FALSE = re.compile(r"loop\s*:\s*false", re.I)


def _nonempty_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.strip()]


def _lines_match(file_line: str, patch_line: str) -> bool:
    a = file_line.rstrip("\n\r")
    b = patch_line.rstrip("\n\r")
    if a == b:
        return True
    return a.strip() == b.strip()


def find_block_start(file_lines: list[str], block: list[str]) -> int | None:
    """Return 0-based index where contiguous block matches, or None."""
    block = _nonempty_lines(block)
    if not block:
        return None
    n = len(block)
    limit = len(file_lines) - n + 1
    for i in range(limit):
        if all(_lines_match(file_lines[i + j], block[j]) for j in range(n)):
            return i
    return None


def _subsequence_in_window(window: list[str], needles: list[str]) -> bool:
    idx = 0
    for line in window:
        if idx < len(needles) and _lines_match(line, needles[idx]):
            idx += 1
    return idx == len(needles)


def find_containing_window(
    file_lines: list[str], needles: list[str]
) -> tuple[int, int] | None:
    """
    Smallest contiguous line range in file that contains all needles in order.

    Handles LLM hunks with wrong context lines mixed with one real anchor line.
    """
    needles = _nonempty_lines(needles)
    if not needles:
        return None
    n = len(file_lines)
    best: tuple[int, int] | None = None
    best_size = n + 1
    for start in range(n):
        for end in range(start + 1, min(n + 1, start + 40)):
            window = file_lines[start:end]
            if _subsequence_in_window(window, needles):
                size = end - start
                if size < best_size:
                    best = (start, end)
                    best_size = size
    return best


def find_swiper_loop_line_index(file_lines: list[str]) -> int | None:
    """Line index of ``loop: false`` inside the nearest ``new Swiper(...)`` block."""
    for i, line in enumerate(file_lines):
        if not _SWIPER_INIT.search(line):
            continue
        for j in range(i, min(i + 35, len(file_lines))):
            if _LOOP_FALSE.search(file_lines[j]):
                return j
    return None


def intent_is_swiper_autoplay(removed: list[str], added: list[str]) -> bool:
    blob = " ".join(removed + added).lower()
    return "autoplay" in blob and ("loop" in blob or "swiper" in blob)


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
    if not removed:
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


def realign_diff_fuzzy(diff: str, files_read: dict[str, str]) -> str:
    """Realign using file-backed windows or Swiper autoplay heuristics."""
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

    file_lines = content.splitlines()
    rebuilt = rebuild_single_file_diff(path, content, removed, added)
    if rebuilt:
        return rebuilt

    window = find_containing_window(file_lines, removed)
    if window:
        start, end = window
        actual_removed = file_lines[start:end]
        rebuilt = rebuild_single_file_diff(path, content, actual_removed, added)
        if rebuilt:
            return rebuilt

    if not added:
        start = find_block_start(file_lines, removed)
        if start is not None:
            actual_removed = file_lines[start : start + len(_nonempty_lines(removed))]
            rebuilt = rebuild_single_file_diff(path, content, actual_removed, [])
            if rebuilt:
                return rebuilt

    if intent_is_swiper_autoplay(removed, added):
        idx = find_swiper_loop_line_index(file_lines)
        if idx is not None:
            actual_removed = [file_lines[idx]]
            rebuilt = rebuild_single_file_diff(path, content, actual_removed, added)
            if rebuilt:
                return rebuilt

    return diff


def realign_diff_to_files(diff: str, files_read: dict[str, str]) -> str:
    """Realign a single-file diff when the removed block exists on disk."""
    return realign_diff_fuzzy(diff, files_read)


def apply_swiper_autoplay_fallback(
    repo_root,
    diff: str,
) -> bool:
    """
    Apply autoplay/loop changes inside the real ``new Swiper`` block on disk.

    Used when LLM hunks target wrong line numbers (e.g. line 57 vs line 679).
    """
    from pathlib import Path

    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return False
    removed, added = _parse_removed_added(diff)
    if not intent_is_swiper_autoplay(removed, added):
        return False

    target = Path(repo_root) / paths[0]
    if not target.is_file():
        return False

    text = target.read_text(encoding="utf-8")
    file_lines = text.splitlines(keepends=True)
    if not file_lines and text:
        file_lines = [text]
    plain = [ln.rstrip("\n\r") for ln in file_lines]

    idx = find_swiper_loop_line_index(plain)
    if idx is None:
        return False

    new_lines: list[str] = []
    for line in added:
        stripped = line.strip()
        if not stripped:
            continue
        if _LOOP_FALSE.search(stripped) and "true" in stripped.lower():
            new_lines.append(line if line.endswith("\n") else line + "\n")
            continue
        if "autoplay" in stripped.lower():
            new_lines.append(line if line.endswith("\n") else line + "\n")

    if not new_lines:
        new_lines = [
            ln if ln.endswith("\n") else ln + "\n"
            for ln in added
            if ln.strip()
        ]

    old_line = file_lines[idx]
    merged = file_lines[:idx] + new_lines + file_lines[idx + 1 :]
    new_text = "".join(merged)
    if new_text == text:
        return False
    target.write_text(new_text, encoding="utf-8")
    return True
