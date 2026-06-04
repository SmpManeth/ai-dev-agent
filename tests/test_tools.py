"""Unit tests for repository tools (no LLM required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.file_tool import FileTool
from tools.git_tool import GitTool
from tools.search_tool import SearchTool

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "test-project"


@pytest.fixture
def repo_path() -> Path:
    assert FIXTURE_ROOT.is_dir()
    return FIXTURE_ROOT


def test_list_and_read_files(repo_path: Path) -> None:
    ft = FileTool(repo_path)
    files = ft.list_files()
    assert "validators.py" in files
    content = ft.read_file("validators.py")
    assert "username" in content.lower()


def test_search_code(repo_path: Path) -> None:
    st = SearchTool(repo_path)
    matches = st.search_code(None, "username")
    assert matches
    assert any("validators.py" in m.file_path for m in matches)


def test_git_summary(repo_path: Path) -> None:
    gt = GitTool(repo_path)
    summary = gt.get_repo_summary()
    if not summary.is_git_repo:
        pytest.skip("test-project is not a git repo; run: cd test-project && git init")
    assert summary.branch is not None


def test_path_traversal_blocked(repo_path: Path) -> None:
    ft = FileTool(repo_path)
    with pytest.raises(PermissionError):
        ft.read_file("../../etc/passwd")
