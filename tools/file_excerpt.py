"""Extract focused excerpts from large files for LLM patch context."""

from __future__ import annotations

import re

DEFAULT_MAX_CHARS = 14_000
ANCHOR_PATTERNS = (
    re.compile(r"new\s+Swiper\s*\(", re.I),
    re.compile(r"loop\s*:\s*false", re.I),
    re.compile(r"autoplay\s*:", re.I),
    re.compile(r"swiper", re.I),
)


def excerpt_for_patch(
    content: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    extra_anchors: list[str] | None = None,
    context_lines: int = 45,
) -> str:
    """
    Return full content if small enough; otherwise slices around anchor lines.
    """
    if len(content) <= max_chars:
        return content

    lines = content.splitlines()
    hit_indexes: set[int] = set()

    for i, line in enumerate(lines):
        for pat in ANCHOR_PATTERNS:
            if pat.search(line):
                hit_indexes.add(i)
        if extra_anchors:
            lower = line.lower()
            for anchor in extra_anchors:
                if anchor and anchor.lower() in lower:
                    hit_indexes.add(i)

    if not hit_indexes:
        half = max_chars // 2
        return (
            content[:half]
            + "\n\n... [truncated — middle omitted] ...\n\n"
            + content[-half:]
        )

    ranges: list[tuple[int, int]] = []
    for idx in sorted(hit_indexes):
        start = max(0, idx - context_lines)
        end = min(len(lines), idx + context_lines + 1)
        ranges.append((start, end))

    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    parts: list[str] = []
    for i, (start, end) in enumerate(merged):
        if i:
            parts.append("\n... [excerpt gap] ...\n")
        parts.append("\n".join(lines[start:end]))

    text = "\n".join(parts)
    if len(text) > max_chars:
        half = max_chars // 2
        return text[:half] + "\n\n... [truncated] ...\n\n" + text[-half:]
    return text
