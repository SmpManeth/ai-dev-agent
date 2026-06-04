"""GitHub agent: push branch and open draft pull request."""

from __future__ import annotations

from typing import Any

from config import get_settings
from models.state import AgentState, ResearchResult
from tools.github_tool import (
    create_draft_pr,
    find_open_pr_for_branch,
    format_pr_body,
    format_pr_body_for_jira,
    format_pr_title,
    format_pr_title_for_jira,
    get_pr_number,
    get_pr_url,
    push_branch,
    resolve_github_target,
)


class GitHubPrAgent:
    """Pushes branch and creates a draft PR after successful local commit."""

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.create_pr:
            return {
                "current_step": "pr_skipped",
                "pr_status": "skipped",
                "push_status": "skipped",
            }

        settings = get_settings()
        if not settings.has_github:
            return self._fail_push_pr(
                "GITHUB_TOKEN is not set.",
                push_status="rejected",
                pr_status="rejected",
            )

        from tools.security_policy import get_hardening_policy
        import os

        policy = get_hardening_policy()
        if policy.require_approval_before_pr and not os.environ.get(
            "AI_AGENT_PR_APPROVED", ""
        ).strip():
            return self._fail_push_pr(
                "PR creation requires human approval (require_approval_before_pr).",
                push_status="rejected",
                pr_status="rejected",
            )

        if state.commit_status != "committed" or not state.commit_created:
            return self._fail_push_pr(
                f"Commit not created (status={state.commit_status}).",
                push_status="rejected",
                pr_status="rejected",
            )

        if not state.branch_created or not state.branch_name:
            return self._fail_push_pr(
                "Branch was not created successfully.",
                push_status="rejected",
                pr_status="rejected",
            )

        token = settings.github_token or ""
        branch = state.branch_name

        try:
            target = resolve_github_target(state.repo_path, settings)
        except RuntimeError as exc:
            return self._fail_push_pr(str(exc), push_status="rejected", pr_status="rejected")

        # Push branch
        try:
            push_branch(state.repo_path, branch, token, settings=settings)
            push_status = "pushed"
            push_error = ""
            branch_pushed = True
        except (OSError, RuntimeError) as exc:
            return self._fail_push_pr(
                str(exc),
                push_status="failed",
                pr_status="skipped",
                branch_pushed=False,
            )

        # Check existing PR
        try:
            existing = find_open_pr_for_branch(
                target.owner, target.repo, branch, token
            )
        except RuntimeError as exc:
            return {
                "branch_pushed": True,
                "push_status": push_status,
                "push_error": "",
                "pr_status": "failed",
                "pr_created": False,
                "pr_error": str(exc),
                "pr_url": "",
                "pr_number": 0,
                "current_step": "pr_failed",
            }

        if existing:
            pr_url = get_pr_url(existing)
            pr_number = get_pr_number(existing)
            return {
                "branch_pushed": True,
                "push_status": push_status,
                "push_error": "",
                "pr_created": True,
                "pr_url": pr_url,
                "pr_number": pr_number,
                "pr_status": "exists",
                "pr_error": "",
                "current_step": "pr_exists",
                "reasoning": (
                    f"{state.reasoning}\n\n"
                    f"GitHubPr: open PR already exists #{pr_number}."
                ).strip(),
            }

        research = state.research_result
        if isinstance(research, dict):
            research = ResearchResult.model_validate(research) if research else None

        changed = state.changed_files or state.affected_files
        root = research.suspected_root_cause if research else ""

        if state.jira_issue_key:
            title = format_pr_title_for_jira(
                state.jira_issue_key,
                state.jira_summary or state.task_description,
            )
            body = format_pr_body_for_jira(
                issue_key=state.jira_issue_key,
                summary=state.jira_summary or state.task_description,
                root_cause=root,
                changed_files=changed,
                validation_status=state.validation_status or "skipped",
                validation_commands=state.validation_commands,
            )
        else:
            title = format_pr_title(state.task_description)
            body = format_pr_body(
                task_description=state.task_description,
                root_cause=root,
                recommended_fix=research.recommended_fix if research else "",
                changed_files=changed,
                validation_commands=state.validation_commands,
                validation_status=state.validation_status or "skipped",
                commit_hash=state.commit_hash,
            )

        try:
            response = create_draft_pr(
                target.owner,
                target.repo,
                title,
                branch,
                target.base_branch,
                body,
                token,
            )
        except RuntimeError as exc:
            return {
                "branch_pushed": True,
                "push_status": push_status,
                "push_error": "",
                "pr_status": "failed",
                "pr_created": False,
                "pr_error": str(exc),
                "pr_url": "",
                "pr_number": 0,
                "current_step": "pr_failed",
            }

        pr_url = get_pr_url(response)
        pr_number = get_pr_number(response)

        reasoning = (
            f"{state.reasoning}\n\n"
            f"GitHubPr: pushed {branch}, draft PR #{pr_number}."
        ).strip()

        return {
            "branch_pushed": True,
            "push_status": push_status,
            "push_error": "",
            "pr_created": True,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "pr_status": "created",
            "pr_error": "",
            "current_step": "pr_created",
            "reasoning": reasoning,
        }

    def _fail_push_pr(
        self,
        message: str,
        *,
        push_status: str,
        pr_status: str,
        branch_pushed: bool = False,
    ) -> dict[str, Any]:
        return {
            "branch_pushed": branch_pushed,
            "push_status": push_status,
            "push_error": message,
            "pr_created": False,
            "pr_url": "",
            "pr_number": 0,
            "pr_status": pr_status,
            "pr_error": message,
            "current_step": "pr_rejected",
        }


def github_pr_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for GitHub PR agent."""
    return GitHubPrAgent().run(AgentState.from_graph_dict(state))
