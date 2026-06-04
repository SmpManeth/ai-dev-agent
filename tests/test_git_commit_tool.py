"""Tests for git commit tool helpers."""

from tools.git_commit_tool import (
    format_commit_message,
    generate_branch_name,
    validate_files_for_commit,
)


def test_generate_branch_name() -> None:
    name = generate_branch_name("Fix username validation message")
    assert name.startswith("ai-fix/")
    assert "username" in name


def test_format_commit_message() -> None:
    msg = format_commit_message("Fix username validation message")
    assert msg == "fix: fix username validation message"


def test_validate_files_for_commit_blocks_env() -> None:
    allowed, blocked = validate_files_for_commit(["validators.py", ".env"])
    assert "validators.py" in allowed
    assert ".env" in blocked
