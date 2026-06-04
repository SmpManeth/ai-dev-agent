"""Git commit agent: create branch and commit after successful apply/validation."""

from __future__ import annotations

from typing import Any

from models.state import AgentState
from tools.git_commit_tool import (
    create_branch,
    commit_changes,
    ensure_clean_start,
    format_commit_message,
    format_commit_message_for_jira,
    generate_branch_name,
    jira_branch_name,
    resolve_git_paths,
    stage_changes,
    validate_files_for_commit,
)
from tools.patch_tool import get_changed_files
from tools.test_tool import (
    output_allows_commit_without_full_tests,
    validation_used_weak_checks,
)


def validation_allows_commit(state: AgentState) -> tuple[bool, str]:
    """Check whether validation status permits a commit."""
    output = state.validation_output or ""
    status = state.validation_status

    if status == "failed":
        return False, f"Validation failed: {(output or status)[:300]}"

    if status in ("passed", "skipped"):
        if status == "skipped" and output_allows_commit_without_full_tests(output):
            return True, "Validation accepted with reduced checks (composer/tests unavailable)."
        if validation_used_weak_checks(output):
            if state.fix_verification_status != "passed":
                return False, (
                    "Validation only ran lightweight checks (no phpunit/npm test). "
                    "Fix verification must pass before commit."
                )
        if status == "passed":
            return True, ""
        if state.fix_verification_status == "passed" and state.patch_applied:
            return True, "Fix verification passed; commit allowed."
        return False, f"Validation skipped: {output[:200]}"

    if state.fix_verification_status == "passed" and state.patch_applied:
        return True, "Fix verification passed; commit allowed."
    return False, f"Validation status is '{status or 'not run'}'."


class GitCommitterAgent:
    """Creates a local branch and commit for agent changes."""

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.do_commit:
            return {
                "current_step": "commit_skipped",
                "commit_status": "skipped",
                "commit_error": "",
            }

        if not state.apply_patch or not state.patch_applied:
            return self._reject("Patch was not applied; cannot commit.")

        if state.patch_apply_status != "applied":
            return self._reject(
                f"Patch apply status is '{state.patch_apply_status}', not 'applied'."
            )

        if state.risk_level == "high":
            return self._reject("Risk level is high; commit blocked.")

        ok_val, val_reason = validation_allows_commit(state)
        if not ok_val:
            return self._reject(val_reason)

        changed = list(state.changed_files) if state.changed_files else []
        if not changed:
            changed = get_changed_files(
                state.repo_path,
                candidates=state.affected_files or None,
            )
        if not changed:
            return self._reject("No changed files to commit.")

        allowed, blocked = validate_files_for_commit(changed)
        if blocked:
            return self._reject(f"Forbidden paths in commit set: {', '.join(blocked)}")
        if not allowed:
            return self._reject("No safe files to commit.")

        start = ensure_clean_start(state.repo_path)
        if not start.ready:
            return self._reject(start.error)

        if (state.branch_name or "").strip():
            branch_name = state.branch_name.strip()
        elif state.jira_issue_key:
            branch_name = jira_branch_name(state.jira_issue_key)
        else:
            branch_name = generate_branch_name(state.task_description)

        if state.jira_issue_key:
            commit_message = format_commit_message_for_jira(
                state.jira_issue_key,
                state.jira_summary or state.task_description,
            )
        else:
            commit_message = format_commit_message(state.task_description)
        original_branch = start.original_branch

        try:
            create_branch(state.repo_path, branch_name)
            staged = stage_changes(state.repo_path, allowed)
            commit_hash = commit_changes(state.repo_path, commit_message)
        except (OSError, RuntimeError, ValueError) as exc:
            return {
                "current_step": "commit_failed",
                "commit_status": "failed",
                "commit_error": str(exc),
                "branch_name": branch_name,
                "branch_created": False,
                "commit_created": False,
                "commit_hash": "",
                "commit_message": commit_message,
                "original_branch": original_branch,
            }

        git_paths = resolve_git_paths(state.repo_path, allowed)
        warnings = list(start.warnings)
        if val_reason and "warning" in val_reason.lower():
            warnings.append(val_reason)

        reasoning = (
            f"{state.reasoning}\n\n"
            f"GitCommitter: branch={branch_name}, commit={commit_hash[:8]}."
        ).strip()

        return {
            "current_step": "committed",
            "commit_status": "committed",
            "commit_error": "",
            "branch_created": True,
            "branch_name": branch_name,
            "commit_created": True,
            "commit_hash": commit_hash,
            "commit_message": commit_message,
            "original_branch": original_branch,
            "changed_files": allowed,
            "reasoning": reasoning,
        }

    def _reject(self, reason: str) -> dict[str, Any]:
        return {
            "current_step": "commit_rejected",
            "commit_status": "rejected",
            "commit_error": reason,
            "branch_created": False,
            "branch_name": "",
            "commit_created": False,
            "commit_hash": "",
            "commit_message": format_commit_message(""),
        }


def git_committer_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for git committer."""
    return GitCommitterAgent().run(AgentState.from_graph_dict(state))
