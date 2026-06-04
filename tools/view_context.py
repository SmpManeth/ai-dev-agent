"""Find Blade/PHP views that contain visible copy from the bug report."""

from __future__ import annotations

import re
from pathlib import Path

from tools.search_tool import SearchTool


def _phrases_from_task(task: str, *, max_phrases: int = 5) -> list[str]:
    """Extract likely UI copy phrases (quoted text or Title Case lines)."""
    phrases: list[str] = []
    for match in re.finditer(r'"([^"]{12,120})"|\'([^\']{12,120})\'', task):
        phrase = (match.group(1) or match.group(2) or "").strip()
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    for line in task.splitlines():
        line = line.strip()
        if len(line) >= 20 and line[0].isupper() and line not in phrases:
            phrases.append(line[:120])
    return phrases[:max_phrases]


def find_views_for_task(repo_path: str | Path, task_description: str) -> list[str]:
    """
    Return repository-relative view paths whose content matches bug copy.
    """
    root = Path(repo_path).resolve()
    views_root = root / "resources" / "views"
    if not views_root.is_dir():
        return []

    search = SearchTool(root)
    found: list[str] = []
    for phrase in _phrases_from_task(task_description):
        for match in search.search_code("resources/views", phrase):
            if match.file_path.endswith((".blade.php", ".php")) and match.file_path not in found:
                found.append(match.file_path)

    task_lower = task_description.lower()
    if any(w in task_lower for w in ("slider", "carousel", "autoplay", "auto-scroll", "swiper")):
        for match in search.search_code("resources/views", "new Swiper"):
            if match.file_path.endswith(".blade.php") and match.file_path not in found:
                found.append(match.file_path)
        for match in search.search_code("resources/views", "swiper"):
            if match.file_path.endswith(".blade.php") and match.file_path not in found:
                found.append(match.file_path)

    return found[:10]
