"""Repository stack detection and display summary for Step 1 reports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tools.git_tool import RepoSummary

_EXT_LABELS: dict[str, str] = {
    ".php": "PHP",
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".vue": "Vue",
    ".blade.php": "Blade",
}


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def detect_project_kind(repo_root: Path) -> str:
    """Infer project type from marker files."""
    root = repo_root.resolve()

    if (root / "artisan").is_file() and (root / "composer.json").is_file():
        composer = _read_json(root / "composer.json") or {}
        require = composer.get("require", {})
        if isinstance(require, dict):
            for pkg in require:
                if "laravel/framework" in pkg:
                    version = str(require[pkg]).lstrip("^~>=<v")
                    major = version.split(".", maxsplit=1)[0] if version else ""
                    if major.isdigit():
                        return f"Laravel {major} application"
            return "Laravel application"
        return "PHP (Laravel-style) application"

    if (root / "manage.py").is_file():
        return "Django application"

    if (root / "package.json").is_file():
        pkg = _read_json(root / "package.json") or {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if isinstance(deps, dict):
            if "next" in deps:
                return "Next.js application"
            if "react" in deps:
                return "React application"
        return "Node.js application"

    if (root / "Cargo.toml").is_file():
        return "Rust application"

    if (root / "go.mod").is_file():
        return "Go application"

    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file():
        return "Java application"

    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        return "Python project"

    if any(root.glob("**/*.py")):
        return "Python project"

    if any(root.glob("**/*.php")):
        return "PHP application"

    return "Software repository"


def count_files_by_language(files: list[str]) -> list[tuple[str, int]]:
    """Return (label, count) pairs for the most common source extensions."""
    counts: Counter[str] = Counter()
    for rel in files:
        path = Path(rel)
        suffix = path.suffix.lower()
        if suffix == ".php" and path.name.endswith(".blade.php"):
            counts[".blade.php"] += 1
        elif suffix:
            counts[suffix] += 1

    ranked: list[tuple[str, int]] = []
    for ext, count in counts.most_common():
        label = _EXT_LABELS.get(ext)
        if label:
            ranked.append((label, count))
    return ranked


def build_display_repo_summary(
    repo_root: str | Path,
    git: RepoSummary,
    files: list[str],
) -> str:
    """Human-readable repository summary for the Step 1 report."""
    root = Path(repo_root).resolve()
    lines: list[str] = [detect_project_kind(root)]

    for label, count in count_files_by_language(files)[:4]:
        noun = "file" if count == 1 else "files"
        lines.append(f"{count} {label} {noun}")

    if git.is_git_repo:
        lines.append(f"Current branch: {git.branch or 'unknown'}")
        if git.dirty:
            lines.append("Working tree: dirty (uncommitted changes)")
        else:
            lines.append("Working tree: clean")
        if git.untracked_count:
            lines.append(f"Untracked files: {git.untracked_count}")
    else:
        lines.append("Version control: not a git repository")

    return "\n".join(lines)
