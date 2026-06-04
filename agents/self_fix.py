"""Self-fix loop: revert failed patch, regenerate from validation errors, re-apply."""

from __future__ import annotations

from typing import Any

from agents.patch_applier import PatchApplierAgent
from agents.patcher import PatcherAgent
from models.state import AgentState
from tools.file_tool import FileTool
from tools.patch_tool import revert_patch


class SelfFixAgent:
    """One self-fix iteration: revert → patcher with errors → apply."""

    def run(self, state: AgentState) -> dict[str, Any]:
        retry = state.retry_count + 1
        history_entry = {
            "retry": retry,
            "validation_errors": list(state.validation_errors),
            "validation_output": (state.validation_output or "")[:2000],
            "previous_patch_summary": state.patch_summary,
        }

        history = list(state.self_fix_history)
        history.append(history_entry)

        if retry > state.max_retries:
            return {
                "retry_count": retry,
                "self_fix_history": history,
                "current_step": "self_fix_exhausted",
                "reasoning": f"{state.reasoning}\n\nSelfFix: max retries ({state.max_retries}) reached.",
            }

        # Revert previous patch before regenerating
        revert_error = ""
        try:
            targets = state.changed_files or state.affected_files
            reverted = revert_patch(state.repo_path, files=targets or None)
            history[-1]["reverted_files"] = reverted
        except (OSError, RuntimeError) as exc:
            revert_error = str(exc)
            history[-1]["revert_error"] = revert_error

        # Refresh file contents from disk for patcher
        file_tool = FileTool(state.repo_path)
        refreshed: dict[str, str] = {}
        paths = list(state.files_read.keys()) or list(state.affected_files)
        for path in paths:
            try:
                refreshed[path] = file_tool.read_file(path)
            except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
                refreshed[path] = state.files_read.get(path, f"(unable to read: {exc})")

        patcher_state = state.model_copy(
            update={
                "files_read": refreshed,
                "retry_count": retry,
                "self_fix_history": history,
                "risk_level": "medium",
            }
        )

        patcher_updates = PatcherAgent().run(patcher_state)
        merged = {**patcher_state.model_dump(mode="json"), **patcher_updates}
        applier_state = AgentState.from_graph_dict(merged)
        applier_state.apply_patch = True

        apply_updates = PatchApplierAgent().run(applier_state)

        history[-1]["patch_apply_status"] = apply_updates.get("patch_apply_status")
        history[-1]["patch_summary"] = apply_updates.get("patch_summary", "")

        reasoning = (
            f"{state.reasoning}\n\n"
            f"SelfFix retry {retry}/{state.max_retries}: "
            f"revert={'ok' if not revert_error else revert_error}, "
            f"apply={apply_updates.get('patch_apply_status')}."
        ).strip()

        return {
            **apply_updates,
            "files_read": refreshed,
            "retry_count": retry,
            "self_fix_history": history,
            "reasoning": reasoning,
            "current_step": "self_fixed",
        }


def self_fix_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for self-fix loop."""
    return SelfFixAgent().run(AgentState.from_graph_dict(state))
