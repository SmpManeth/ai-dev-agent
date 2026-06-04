"""Tests for repository profiling."""

from pathlib import Path

from tools.git_tool import RepoSummary
from tools.repo_profile import build_display_repo_summary, count_files_by_language, detect_project_kind


def test_detect_python_project(tmp_path: Path) -> None:
    (tmp_path / "validators.py").write_text("x = 1\n", encoding="utf-8")
    assert detect_project_kind(tmp_path) == "Python project"


def test_count_files_by_language() -> None:
    files = ["a.py", "b.py", "api.php"]
    counts = count_files_by_language(files)
    labels = [label for label, _ in counts]
    assert "Python" in labels
    assert "PHP" in labels


def test_build_display_repo_summary(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    git = RepoSummary(
        is_git_repo=True,
        branch="main",
        recent_commits=[],
        dirty=False,
        untracked_count=0,
    )
    text = build_display_repo_summary(tmp_path, git, ["main.py"])
    assert "Python project" in text
    assert "Current branch: main" in text
    assert "Working tree: clean" in text
