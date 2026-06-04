"""Tests for Jira tool helpers."""

from tools.jira_tool import (
    JiraIssue,
    build_task_from_issue,
    format_jira_comment,
    is_high_risk_text,
    validate_issue_for_agent,
    adf_to_plain,
)


def test_adf_to_plain() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Hello"}],
            }
        ],
    }
    assert "Hello" in adf_to_plain(doc)


def test_validate_issue_requires_label() -> None:
    issue = JiraIssue(
        key="AI-1",
        summary="Fix username validation message",
        description="The error message is wrong for usernames.",
        labels=["other"],
        status="To Do",
    )
    ok, reason = validate_issue_for_agent(issue)
    assert not ok
    assert "ai-fix" in reason


def test_validate_issue_rejects_high_risk() -> None:
    issue = JiraIssue(
        key="AI-2",
        summary="Fix payment auth login bug",
        description="Detailed enough description here.",
        labels=["ai-fix"],
        status="To Do",
    )
    ok, _ = validate_issue_for_agent(issue)
    assert not ok
    assert is_high_risk_text("payment auth")


def test_validate_issue_accepts_good_ticket() -> None:
    issue = JiraIssue(
        key="AI-3",
        summary="Fix username validation message",
        description="Error text says email instead of username in validators.",
        labels=["ai-fix"],
        status="To Do",
    )
    ok, reason = validate_issue_for_agent(issue)
    assert ok, reason
    assert "AI-3" in build_task_from_issue(issue)


def test_format_jira_comment() -> None:
    text = format_jira_comment(
        pr_url="https://github.com/o/r/pull/1",
        branch_name="ai-fix/foo",
        validation_status="passed",
    )
    assert "draft PR" in text
    assert "github.com" in text
    assert "human review" in text
