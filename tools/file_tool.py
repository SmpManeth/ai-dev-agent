"""Filesystem read-only operations within a repository root."""

from __future__ import annotations

from pathlib import Path

from config import get_settings

# Directories commonly excluded from agent inspection
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "vendor",
    "coverage",
    ".tox",
}

# Binary / large artifact extensions to skip when listing
_SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
    ".sqlite",
    ".db",
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".class",
    ".jar",
}


class FileTool:
    """Read-only file access scoped to a repository root."""

    def __init__(self, repo_path: str | Path) -> None:
        self.root = Path(repo_path).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Repository path does not exist: {self.root}")
        self._settings = get_settings()

    def _resolve_safe(self, path: str | Path) -> Path:
        """Resolve path and ensure it stays within repo root."""
        candidate = (self.root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"Path escapes repository root: {path}") from exc
        return candidate

    def read_file(self, path: str | Path) -> str:
        """Read a text file relative to the repository root."""
        resolved = self._resolve_safe(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if resolved.suffix.lower() in _SKIP_EXTENSIONS:
            raise ValueError(f"Refusing to read binary/large file type: {resolved.suffix}")
        raw = resolved.read_bytes()
        if len(raw) > self._settings.max_file_read_bytes:
            raise ValueError(
                f"File exceeds max read size ({self._settings.max_file_read_bytes} bytes): {path}"
            )
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")

    def list_files(self, root: str | Path | None = None) -> list[str]:
        """List repository-relative file paths recursively."""
        scan_root = self._resolve_safe(root or ".")
        if not scan_root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        paths: list[str] = []
        max_files = self._settings.max_files_to_list

        for current, dirnames, filenames in scan_root.walk(top_down=True):
            # Prune skipped directories in-place for walk efficiency
            dirnames[:] = sorted(
                d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
            )
            rel_dir = current.relative_to(self.root)
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                full = current / name
                if full.suffix.lower() in _SKIP_EXTENSIONS:
                    continue
                rel = (rel_dir / name).as_posix()
                if rel.startswith("./"):
                    rel = rel[2:]
                paths.append(rel)
                if len(paths) >= max_files:
                    return paths
        return paths

    def file_exists(self, path: str | Path) -> bool:
        """Check whether a repository-relative file exists."""
        try:
            return self._resolve_safe(path).is_file()
        except (PermissionError, ValueError):
            return False
