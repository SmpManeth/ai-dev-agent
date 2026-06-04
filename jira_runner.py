"""Load and validate Jira issues for the agent CLI."""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings, get_settings
from tools.jira_tool import (
    JiraIssue,
    build_task_from_issue,
    fetch_issue,
    search_ai_fix_issues,
    validate_issue_for_agent,
)


@dataclass(frozen=True)
class JiraWorkItem:
    """Issue ready to run through the workflow."""

    issue: JiraIssue
    task_description: str


def load_jira_issue(issue_key: str, settings: Settings | None = None) -> JiraWorkItem:
    """Fetch and validate a single Jira issue."""
    settings = settings or get_settings()
    issue = fetch_issue(issue_key, settings)
    ok, reason = validate_issue_for_agent(issue, settings)
    if not ok:
        raise ValueError(f"Jira issue {issue.key} rejected: {reason}")
    return JiraWorkItem(issue=issue, task_description=build_task_from_issue(issue))


def load_jira_queue(
    settings: Settings | None = None,
    *,
    max_tasks: int = 50,
) -> list[JiraWorkItem]:
    """Search and validate all eligible ai-fix issues."""
    settings = settings or get_settings()
    issues = search_ai_fix_issues(settings, max_results=max_tasks)
    queue: list[JiraWorkItem] = []
    for issue in issues:
        ok, reason = validate_issue_for_agent(issue, settings)
        if ok:
            queue.append(
                JiraWorkItem(issue=issue, task_description=build_task_from_issue(issue))
            )
    return queue
