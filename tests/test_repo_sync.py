"""Tests for automatic repository sync helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings
from tools.repo_sync import (
    normalize_github_owner,
    normalize_github_repo_name,
    resolve_workspace_path,
)


def test_normalize_github_repo_name_from_url():
    assert (
        normalize_github_repo_name("https://github.com/Blue-Lotus-Vacations/Blvs-Web-Site")
        == "Blvs-Web-Site"
    )


def test_normalize_github_repo_name_plain():
    assert normalize_github_repo_name("Blvs-Web-Site") == "Blvs-Web-Site"


def test_resolve_workspace_path():
    settings = Settings(
        github_owner="Blue-Lotus-Vacations",
        github_repo="Blvs-Web-Site",
        workspace_root=Path("/tmp/workspaces"),
    )
    path = resolve_workspace_path(settings)
    assert str(path) == "/tmp/workspaces/Blue-Lotus-Vacations/Blvs-Web-Site"


def test_normalize_github_owner_rejects_email():
    with pytest.raises(RuntimeError):
        normalize_github_owner("user@example.com")
