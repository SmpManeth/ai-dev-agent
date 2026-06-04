"""Expand planner file list with related paths for deeper root-cause analysis."""

from __future__ import annotations

import re
from pathlib import Path

from tools.search_tool import SearchTool


def _basename_stems(paths: list[str]) -> list[str]:
    stems: list[str] = []
    for path in paths:
        name = Path(path).name
        if "." in name:
            stems.append(Path(name).stem)
        else:
            stems.append(name)
    return [s for s in stems if len(s) >= 3]


def expand_investigation_paths(
    repo_path: str | Path,
    planned_paths: list[str],
    task_description: str,
    *,
    max_files: int = 12,
) -> list[str]:
    """
    Return deduplicated paths: planned files plus closely related sources.

    Adds ripgrep hits for file stems and task keywords in Laravel/JS stacks.
    """
    root = Path(repo_path).resolve()
    search = SearchTool(root)
    seen: set[str] = set()
    ordered: list[str] = []

    def add(path: str) -> None:
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized in seen:
            return
        if not (root / normalized).is_file():
            return
        seen.add(normalized)
        ordered.append(normalized)

    for path in planned_paths:
        add(path)

    stems = _basename_stems(planned_paths)
    for stem in stems[:4]:
        for match in search.search_code(None, stem)[:6]:
            add(match.file_path)
        if len(ordered) >= max_files:
            return ordered[:max_files]

    keywords = re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", task_description)
    stop = {
        "this", "that", "with", "from", "when", "should", "issue", "error",
        "fix", "bug", "ticket", "jira", "description", "recent", "comments",
    }
    for word in keywords:
        if word.lower() in stop:
            continue
        for match in search.search_code(None, word)[:4]:
            add(match.file_path)
        if len(ordered) >= max_files:
            break

    # Laravel: if JS changed, include common entrypoints once
    laravel_hints = (
        "resources/views",
        "routes/web.php",
        "app/Http",
        "webpack.mix.js",
        "vite.config",
    )
    if any(p.endswith((".js", ".ts", ".vue", ".jsx", ".tsx")) for p in planned_paths):
        for hint in laravel_hints:
            for candidate in root.rglob("*"):
                if len(ordered) >= max_files:
                    return ordered[:max_files]
                rel = candidate.relative_to(root).as_posix()
                if hint in rel and candidate.is_file():
                    add(rel)

    return ordered[:max_files]
