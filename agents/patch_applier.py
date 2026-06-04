"""Patch applier agent: validate and apply proposed patch locally (no commit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from models.state import AgentState
from tools.patch_output import get_patch_paths
from tools.patch_tool import (
    PatchValidationResult,
    apply_patch,
    get_changed_files,
    get_git_diff,
    validate_patch,
)


class PatchApplierAgent:
    """Applies a validated patch to the target repository when enabled."""

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.apply_patch:
            return {
                "current_step": "apply_skipped",
                "patch_apply_status": "skipped",
                "patch_apply_error": "",
                "patch_validation_status": "skipped",
            }

        patch_path_str = state.patch_file_path
        if not patch_path_str:
            patch_path, _ = get_patch_paths()
            patch_path_str = str(patch_path)

        patch_path = Path(patch_path_str)
        validation: PatchValidationResult = validate_patch(
            state.repo_path,
            patch_path,
            risk_level=state.risk_level or "high",
        )

        if not validation.ok:
            errors = "; ".join(validation.errors)
            return {
                "current_step": "apply_failed",
                "patch_applied": False,
                "patch_validation_status": validation.status_text,
                "patch_apply_status": "validation_failed",
                "patch_apply_error": errors,
                "changed_files": [],
                "git_diff": "",
            }

        if not state.unified_diff.strip():
            return {
                "current_step": "apply_failed",
                "patch_applied": False,
                "patch_validation_status": "REJECTED",
                "patch_apply_status": "validation_failed",
                "patch_apply_error": "No unified diff in state; patch was not generated.",
                "changed_files": [],
                "git_diff": "",
            }

        try:
            apply_patch(state.repo_path, patch_path)
        except (OSError, RuntimeError, ValueError) as exc:
            return {
                "current_step": "apply_failed",
                "patch_applied": False,
                "patch_validation_status": validation.status_text,
                "patch_apply_status": "apply_failed",
                "patch_apply_error": str(exc),
                "changed_files": [],
                "git_diff": "",
            }

        candidates = state.affected_files or validation.affected_paths
        changed = get_changed_files(state.repo_path, candidates=candidates)
        diff = get_git_diff(state.repo_path, paths=changed or candidates)

        reasoning = (
            f"{state.reasoning}\n\n"
            f"PatchApplier: applied patch to {len(changed)} file(s)."
        ).strip()

        return {
            "current_step": "applied",
            "patch_applied": True,
            "patch_validation_status": validation.status_text,
            "patch_apply_status": "applied",
            "patch_apply_error": "",
            "changed_files": changed,
            "git_diff": diff,
            "reasoning": reasoning,
        }


def patch_applier_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for the patch applier."""
    agent_state = AgentState.from_graph_dict(state)
    return PatchApplierAgent().run(agent_state)
