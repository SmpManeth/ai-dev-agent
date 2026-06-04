"""Self-fix loop: revert failed patch, regenerate from validation errors, re-apply."""

from __future__ import annotations

from typing import Any

from agents.patcher import PatcherAgent
from agents.researcher import ResearcherAgent
from models.state import AgentState
from tools.file_tool import FileTool
from tools.investigation_paths import expand_investigation_paths
from tools.patch_tool import revert_patch


class SelfFixAgent:
    """One self-fix iteration: revert → (optional re-research) → patcher → patch_applier node applies."""

    def run(self, state: AgentState) -> dict[str, Any]:
        retry = state.retry_count + 1
        apply_errors: list[str] = []
        if state.patch_apply_error:
            apply_errors.append(state.patch_apply_error)

        history_entry = {
            "retry": retry,
            "validation_errors": list(state.validation_errors) + apply_errors,
            "patch_apply_error": state.patch_apply_error,
            "fix_verification_errors": list(state.fix_verification_errors),
            "validation_output": (state.validation_output or "")[:2000],
            "fix_verification_output": (state.fix_verification_output or "")[:2000],
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

        validation_errors = list(state.validation_errors) + apply_errors
        working = state.model_copy(
            update={
                "files_read": refreshed,
                "retry_count": retry,
                "self_fix_history": history,
                "risk_level": "medium",
                "fix_verification_status": "",
                "fix_verification_confidence": 0,
                "patch_apply_status": "",
                "patch_applied": False,
                "patch_apply_error": "",
                "validation_errors": validation_errors,
            }
        )

        if apply_errors:
            working = working.model_copy(
                update={
                    "task_description": (
                        f"{state.task_description}\n\n"
                        f"## Previous patch did not apply (retry {retry})\n"
                        f"{state.patch_apply_error[:4000]}\n\n"
                        "Regenerate unified_diff using EXACT lines from the file excerpts below."
                    ),
                }
            )

        if state.fix_verification_status == "failed":
            gaps = "\n".join(state.fix_verification_errors) or state.fix_verification_output
            working = working.model_copy(
                update={
                    "task_description": (
                        f"{state.task_description}\n\n"
                        f"## Fix verification rejected previous patch (retry {retry})\n"
                        f"{gaps[:4000]}"
                    ),
                }
            )
            from models.state import PlannerResult

            planner = working.planner_result
            if isinstance(planner, dict):
                planner = PlannerResult.model_validate(planner) if planner else None
            paths = list(planner.files_to_investigate) if planner else []
            paths = expand_investigation_paths(
                state.repo_path,
                paths or list(refreshed.keys()),
                working.task_description,
                max_files=12,
            )
            if planner is not None:
                working = working.model_copy(
                    update={
                        "planner_result": planner.model_copy(
                            update={"files_to_investigate": paths},
                        ),
                    },
                )
            research_updates = ResearcherAgent(state.repo_path).run(working)
            working = working.model_copy(update=research_updates)

        patcher_updates = PatcherAgent().run(working)
        merged = {**working.model_dump(mode="json"), **patcher_updates}

        history[-1]["patch_summary"] = merged.get("patch_summary", "")
        history[-1]["has_diff"] = bool((merged.get("unified_diff") or "").strip())

        reasoning = (
            f"{state.reasoning}\n\n"
            f"SelfFix retry {retry}/{state.max_retries}: "
            f"revert={'ok' if not revert_error else revert_error}, "
            f"patch={'yes' if history[-1]['has_diff'] else 'empty'}."
        ).strip()

        return {
            **merged,
            "retry_count": retry,
            "self_fix_history": history,
            "reasoning": reasoning,
            "current_step": "self_fixed",
            "apply_patch": True,
        }


def self_fix_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for self-fix loop."""
    return SelfFixAgent().run(AgentState.from_graph_dict(state))
