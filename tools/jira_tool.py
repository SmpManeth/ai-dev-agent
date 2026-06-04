"""Jira Cloud REST API integration (read issues, comment, transition)."""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from config import Settings, get_settings

HIGH_RISK_KEYWORDS: tuple[str, ...] = (
    "payment",
    "auth",
    "login",
    "password",
    "permission",
    "security",
    "database migration",
    "migration",
    "production",
    "secret",
    "token",
)

DONE_STATUS_NAMES: frozenset[str] = frozenset(
    {"done", "closed", "resolved", "cancelled", "canceled"}
)


@dataclass
class JiraIssue:
    """Normalized Jira issue for the agent."""

    key: str
    summary: str
    description: str
    labels: list[str] = field(default_factory=list)
    status: str = ""
    status_category: str = ""
    comment_snippets: list[str] = field(default_factory=list)


def _auth_header(settings: Settings) -> str:
    email = (settings.jira_email or "").strip()
    token = (settings.jira_api_token or "").strip()
    if not email or not token:
        raise RuntimeError("JIRA_EMAIL and JIRA_API_TOKEN are required.")
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _api_base(settings: Settings) -> str:
    base = (settings.jira_base_url or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("JIRA_BASE_URL is required.")
    return base


def _request(
    settings: Settings,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> Any:
    base = _api_base(settings)
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    data = None
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": _auth_header(settings),
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API {exc.code}: {detail}") from exc


def adf_to_plain(node: Any) -> str:
    """Convert Atlassian Document Format to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text", ""))
        parts: list[str] = []
        for child in node.get("content", []) or []:
            parts.append(adf_to_plain(child))
        text = "".join(parts)
        if node.get("type") in ("paragraph", "heading", "listItem"):
            text += "\n"
        return text
    if isinstance(node, list):
        return "".join(adf_to_plain(item) for item in node)
    return ""


def _parse_issue(data: dict[str, Any]) -> JiraIssue:
    fields = data.get("fields", {}) or {}
    summary = str(fields.get("summary") or "").strip()
    desc_raw = fields.get("description")
    if isinstance(desc_raw, dict):
        description = adf_to_plain(desc_raw).strip()
    else:
        description = str(desc_raw or "").strip()

    labels = [str(l) for l in fields.get("labels", []) or []]
    status_obj = fields.get("status") or {}
    status = str(status_obj.get("name") or "")
    category = (status_obj.get("statusCategory") or {}).get("key", "")

    comments: list[str] = []
    comment_block = fields.get("comment") or {}
    for c in comment_block.get("comments", []) or []:
        body = c.get("body")
        plain = adf_to_plain(body).strip() if body else ""
        if plain:
            comments.append(plain[:500])

    return JiraIssue(
        key=str(data.get("key") or ""),
        summary=summary,
        description=description,
        labels=labels,
        status=status,
        status_category=str(category),
        comment_snippets=comments[:5],
    )


def build_task_from_issue(issue: JiraIssue) -> str:
    """Combine summary and description for agent task_description."""
    parts = [f"[{issue.key}] {issue.summary}"]
    if issue.description:
        parts.append(issue.description)
    if issue.comment_snippets:
        parts.append("Recent comments:")
        parts.extend(f"- {c}" for c in issue.comment_snippets[:3])
    return "\n\n".join(parts)


def is_high_risk_text(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in HIGH_RISK_KEYWORDS)


def validate_issue_for_agent(
    issue: JiraIssue,
    settings: Settings | None = None,
) -> tuple[bool, str]:
    """Apply safety rules before running the agent on an issue."""
    settings = settings or get_settings()
    required_label = (settings.jira_label or "ai-fix").strip().lower()

    if not issue.key:
        return False, "Missing issue key."
    if not issue.summary.strip():
        return False, "Issue summary is empty."
    if not issue.description.strip():
        return False, "Issue description is empty."
    if issue.status.lower() in DONE_STATUS_NAMES or issue.status_category.lower() == "done":
        return False, f"Issue status is Done/closed ({issue.status})."

    label_set = {label.lower() for label in issue.labels}
    if required_label not in label_set:
        return False, f"Issue must have label '{required_label}'."

    combined = f"{issue.summary}\n{issue.description}"
    if is_high_risk_text(combined):
        return False, "Issue text matches high-risk keywords; skipped."

    if len(issue.summary) < 8:
        return False, "Issue summary too vague."

    return True, ""


def fetch_issue(issue_key: str, settings: Settings | None = None) -> JiraIssue:
    """Fetch a single Jira issue by key."""
    settings = settings or get_settings()
    key = issue_key.strip().upper()
    path = f"/rest/api/3/issue/{key}"
    params = {"fields": "summary,description,labels,status,comment"}
    data = _request(settings, "GET", path, params=params)
    return _parse_issue(data)


def build_ai_fix_jql(settings: Settings | None = None) -> str:
    """JQL for open ai-fix issues in the configured project."""
    settings = settings or get_settings()
    label = (settings.jira_label or "ai-fix").strip()
    project = (settings.jira_project_key or "").strip()
    if not project:
        raise RuntimeError("JIRA_PROJECT_KEY is required for --from-jira.")
    return (
        f'project = {project} AND labels = "{label}" '
        f"AND statusCategory != Done ORDER BY created ASC"
    )


def search_jql(
    jql: str,
    settings: Settings | None = None,
    *,
    max_results: int = 50,
    fields: list[str] | None = None,
) -> list[JiraIssue]:
    """
    Search issues using Jira Cloud enhanced JQL API (POST /rest/api/3/search/jql).
    """
    settings = settings or get_settings()
    field_list = fields or [
        "summary",
        "description",
        "labels",
        "status",
        "comment",
    ]
    limit = max(1, min(max_results, 100))
    issues: list[JiraIssue] = []
    next_page_token: str | None = None

    while len(issues) < max_results:
        body: dict[str, Any] = {
            "jql": jql,
            "maxResults": min(limit, max_results - len(issues)),
            "fields": field_list,
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        data = _request(settings, "POST", "/rest/api/3/search/jql", body=body)
        for item in data.get("issues", []) or []:
            issues.append(_parse_issue(item))
            if len(issues) >= max_results:
                break

        next_page_token = data.get("nextPageToken") or None
        if not next_page_token:
            break

    return issues


def search_ai_fix_issues(
    settings: Settings | None = None,
    *,
    max_results: int = 50,
) -> list[JiraIssue]:
    """Search open issues labeled ai-fix in the configured project."""
    settings = settings or get_settings()
    jql = build_ai_fix_jql(settings)
    return search_jql(jql, settings, max_results=max_results)


def _plain_to_adf(text: str) -> dict[str, Any]:
    paragraphs = []
    for line in text.splitlines() or [text]:
        line = line.strip()
        if line:
            paragraphs.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }
            )
    if not paragraphs:
        paragraphs.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "(empty)"}],
            }
        )
    return {"type": "doc", "version": 1, "content": paragraphs}


def format_jira_comment(
    *,
    pr_url: str,
    branch_name: str,
    validation_status: str,
) -> str:
    """Plain-text comment (converted to ADF when posting)."""
    return f"""AI Bug Fix Agent created a draft PR.

PR:
{pr_url}

Branch:
{branch_name}

Validation:
{validation_status}

Note:
This PR requires human review before merge."""


def format_jira_failure_comment(reason: str) -> str:
    """Comment when the AI agent fails on an issue."""
    return f"""AI Bug Fix Agent could not complete this issue.

Reason:
{reason.strip() or "Unknown error"}

The batch will continue with the next issue. Please review manually."""


def format_jira_skip_comment(reason: str, *, pr_url: str = "") -> str:
    """Comment when an issue is skipped (duplicate PR/branch)."""
    lines = [
        "AI Bug Fix Agent skipped this issue.",
        "",
        f"Reason: {reason.strip() or 'Skipped'}",
    ]
    if pr_url:
        lines.extend(["", f"Existing PR: {pr_url}"])
    return "\n".join(lines)


def add_comment(issue_key: str, comment: str, settings: Settings | None = None) -> None:
    """Add a comment to a Jira issue."""
    settings = settings or get_settings()
    key = issue_key.strip().upper()
    path = f"/rest/api/3/issue/{key}/comment"
    body = {"body": _plain_to_adf(comment)}
    _request(settings, "POST", path, body=body)


def get_transitions(issue_key: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Return available transitions for an issue."""
    settings = settings or get_settings()
    key = issue_key.strip().upper()
    path = f"/rest/api/3/issue/{key}/transitions"
    data = _request(settings, "GET", path)
    return list(data.get("transitions", []) or [])


def transition_issue(
    issue_key: str,
    transition_name: str,
    settings: Settings | None = None,
) -> bool:
    """
    Transition issue by transition name (case-insensitive).

    Returns True if a matching transition was applied.
    """
    settings = settings or get_settings()
    target = transition_name.strip().lower()
    transitions = get_transitions(issue_key, settings)
    transition_id = None
    for t in transitions:
        name = str(t.get("name") or "").lower()
        if name == target:
            transition_id = t.get("id")
            break

    if not transition_id:
        return False

    key = issue_key.strip().upper()
    path = f"/rest/api/3/issue/{key}/transitions"
    _request(settings, "POST", path, body={"transition": {"id": transition_id}})
    return True
