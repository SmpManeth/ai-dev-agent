"""Tests for GitHub tool helpers."""

from tools.github_tool import (
    format_pr_body,
    format_pr_title,
    get_pr_number,
    get_pr_url,
    parse_github_remote,
)


def test_parse_github_remote_https() -> None:
    assert parse_github_remote("https://github.com/acme/my-app.git") == ("acme", "my-app")


def test_parse_github_remote_ssh() -> None:
    assert parse_github_remote("git@github.com:acme/my-app.git") == ("acme", "my-app")


def test_format_pr_title() -> None:
    assert format_pr_title("Fix username validation") == "fix: fix username validation"


def test_format_pr_body_includes_safety_note() -> None:
    body = format_pr_body(
        task_description="Fix bug",
        root_cause="Bad constant",
        recommended_fix="Update constant",
        changed_files=["validators.py"],
        validation_commands=["pytest"],
        validation_status="passed",
        commit_hash="abc123",
    )
    assert "Fix bug" in body
    assert "validators.py" in body
    assert "autonomous AI coding agent" in body
    assert "abc123" in body


def test_get_pr_url_and_number() -> None:
    resp = {"html_url": "https://github.com/o/r/pull/1", "number": 1}
    assert get_pr_url(resp) == "https://github.com/o/r/pull/1"
    assert get_pr_number(resp) == 1
