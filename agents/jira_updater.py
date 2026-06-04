"""Jira updater agent: comment PR link and transition to In Review."""

from __future__ import annotations

from typing import Any

from config import get_settings
from models.state import AgentState
from tools.jira_tool import add_comment, format_jira_comment, transition_issue


class JiraUpdaterAgent:
    """Updates Jira after a draft PR is created."""

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.update_jira or not state.jira_issue_key:
            return {
                "current_step": "jira_skipped",
                "jira_update_status": "skipped",
                "jira_error": "",
            }

        if not state.create_pr:
            return self._reject("PR creation was not enabled (--create-pr required).")

        if state.pr_status not in ("created", "exists") or not state.pr_url:
            return self._reject(
                f"No PR to report (pr_status={state.pr_status})."
            )

        settings = get_settings()
        if not settings.has_jira:
            return self._reject("Jira credentials not configured.")

        comment_text = format_jira_comment(
            pr_url=state.pr_url,
            branch_name=state.branch_name or "(unknown)",
            validation_status=state.validation_status or "skipped",
        )

        comment_added = False
        transitioned = False
        errors: list[str] = []

        try:
            add_comment(state.jira_issue_key, comment_text, settings)
            comment_added = True
        except RuntimeError as exc:
            errors.append(f"Comment failed: {exc}")

        review_status = (settings.jira_in_review_status or "In Review").strip()
        try:
            transitioned = transition_issue(
                state.jira_issue_key,
                review_status,
                settings,
            )
            if not transitioned:
                errors.append(
                    f"Transition '{review_status}' not available for {state.jira_issue_key}."
                )
        except RuntimeError as exc:
            errors.append(f"Transition failed: {exc}")

        status = "updated" if comment_added else "failed"
        if comment_added and errors:
            status = "partial"

        reasoning = (
            f"{state.reasoning}\n\n"
            f"JiraUpdater: comment={comment_added}, transition={transitioned} "
            f"on {state.jira_issue_key}."
        ).strip()

        return {
            "current_step": "jira_updated",
            "jira_comment_added": comment_added,
            "jira_transitioned": transitioned,
            "jira_update_status": status,
            "jira_error": "; ".join(errors),
            "reasoning": reasoning,
        }

    def _reject(self, reason: str) -> dict[str, Any]:
        return {
            "current_step": "jira_rejected",
            "jira_comment_added": False,
            "jira_transitioned": False,
            "jira_update_status": "rejected",
            "jira_error": reason,
        }


def jira_updater_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for Jira updater."""
    return JiraUpdaterAgent().run(AgentState.from_graph_dict(state))
