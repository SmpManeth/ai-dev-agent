"""Recursive code search within a repository."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config import get_settings
from tools.file_tool import FileTool, _SKIP_DIRS, _SKIP_EXTENSIONS


@dataclass(frozen=True)
class SearchMatch:
    """A single search hit in a source file."""

    file_path: str
    line_number: int
    line_text: str


class SearchTool:
    """Search file contents under a repository root."""

    def __init__(self, repo_path: str | Path) -> None:
        self.root = Path(repo_path).resolve()
        self._file_tool = FileTool(self.root)
        self._settings = get_settings()

    def search_code(
        self,
        root: str | Path | None,
        query: str,
        *,
        case_sensitive: bool = False,
        is_regex: bool = False,
    ) -> list[SearchMatch]:
        """
        Search recursively for a string or regex in text files.

        Args:
            root: Subdirectory to search (None = entire repo).
            query: Literal string or regex pattern.
            case_sensitive: Match case when True.
            is_regex: Treat query as regex when True.
        """
        if not query.strip():
            return []

        scan_root = self.root if root is None else (self.root / root).resolve()
        try:
            scan_root.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"Search root escapes repository: {root}") from exc

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query, flags) if is_regex else None
        query_lower = query.lower()

        matches: list[SearchMatch] = []
        max_results = self._settings.max_search_results

        for current, dirnames, filenames in scan_root.walk(top_down=True):
            dirnames[:] = sorted(
                d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
            )
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                full = current / name
                if full.suffix.lower() in _SKIP_EXTENSIONS:
                    continue
                rel = full.relative_to(self.root).as_posix()
                try:
                    content = self._file_tool.read_file(rel)
                except (OSError, ValueError, PermissionError, FileNotFoundError):
                    continue

                for line_no, line in enumerate(content.splitlines(), start=1):
                    hit = False
                    if is_regex and pattern is not None:
                        hit = pattern.search(line) is not None
                    elif case_sensitive:
                        hit = query in line
                    else:
                        hit = query_lower in line.lower()

                    if hit:
                        matches.append(
                            SearchMatch(
                                file_path=rel,
                                line_number=line_no,
                                line_text=line.strip()[:500],
                            )
                        )
                        if len(matches) >= max_results:
                            return matches
        return matches

    def format_matches(self, matches: list[SearchMatch]) -> str:
        """Format matches for LLM context."""
        if not matches:
            return "(no matches)"
        lines = []
        for m in matches[:30]:
            lines.append(f"{m.file_path}:{m.line_number}: {m.line_text}")
        if len(matches) > 30:
            lines.append(f"... and {len(matches) - 30} more matches")
        return "\n".join(lines)
