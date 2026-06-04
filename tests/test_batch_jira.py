"""Tests for Jira batch helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from batch_jira import check_duplicate_pr
from config import Settings
from tools.git_commit_tool import format_commit_message_for_jira, jira_branch_name
from tools.github_tool import format_pr_title_for_jira
from tools.jira_tool import build_ai_fix_jql, build_task_from_issue
from tools.jira_tool import JiraIssue


def test_jira_branch_name():
    assert jira_branch_name("abc-123") == "ai-fix/ABC-123"


def test_format_commit_message_for_jira():
    msg = format_commit_message_for_jira("ABC-123", "Fix login bug")
    assert msg == "fix(ABC-123): Fix login bug"


def test_format_pr_title_for_jira():
    assert format_pr_title_for_jira("abc-123", "Fix login") == "fix(ABC-123): Fix login"


def test_build_ai_fix_jql():
    settings = Settings(
        JIRA_PROJECT_KEY="AI",
        JIRA_LABEL="ai-fix",
    )
    jql = build_ai_fix_jql(settings)
    assert "project = AI" in jql
    assert 'labels = "ai-fix"' in jql
    assert "statusCategory != Done" in jql
    assert "ORDER BY created ASC" in jql


def test_build_task_from_issue_includes_comments():
    issue = JiraIssue(
        key="AI-1",
        summary="Broken validator",
        description="Steps to reproduce",
        comment_snippets=["Try the API endpoint"],
    )
    text = build_task_from_issue(issue)
    assert "[AI-1]" in text
    assert "Broken validator" in text
    assert "Recent comments" in text


@patch("batch_jira.find_open_pr_for_branch")
def test_check_duplicate_pr_open_pr(mock_find):
    mock_find.return_value = {"html_url": "https://github.com/o/r/pull/9", "number": 9}
    settings = MagicMock()
    settings.has_github = True
    settings.github_token = "token"
    with patch("batch_jira.resolve_github_target") as mock_target:
        mock_target.return_value = MagicMock(owner="o", repo="r", base_branch="main")
        skip, reason, url = check_duplicate_pr("/tmp/repo", "ai-fix/AI-1", settings)
    assert skip is True
    assert "PR already exists" in reason
    assert url.endswith("/pull/9")


@patch("batch_jira.find_open_pr_for_branch")
def test_check_duplicate_pr_local_branch_only(mock_find):
    """Local ai-fix branches are cleaned by teardown; do not skip on branch ref alone."""
    mock_find.return_value = None
    settings = MagicMock()
    settings.has_github = False
    skip, reason, _ = check_duplicate_pr("/tmp/repo", "ai-fix/AI-2", settings)
    assert skip is False
    assert reason == ""
