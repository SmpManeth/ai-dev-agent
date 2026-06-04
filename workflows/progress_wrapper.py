"""LangGraph node wrappers that emit pipeline progress."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tools.agent_console import log_detail, log_step
from tools.pipeline_progress import PHASE_LABELS, NODE_PHASES, PipelinePhase, reporter_from_state


def with_pipeline_progress(
    node_name: str,
    node_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap a graph node to write progress before execution."""

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        reporter = reporter_from_state(state)
        phase, _ = NODE_PHASES.get(node_name, (PipelinePhase.PLANNING, 0))
        label = PHASE_LABELS.get(phase, node_name)
        issue = (state.get("jira_issue_key") or "").strip()
        prefix = f"[{issue}] " if issue else ""
        log_step(f"{prefix}→ {label}…")
        if reporter:
            reporter.enter_node(node_name, state)
        try:
            result = node_fn(state)
        except Exception as exc:
            if reporter:
                reporter.complete_failed(str(exc), state)
            raise
        merged = {**state, **result}
        step = merged.get("current_step") or node_name
        log_detail(f"    ✓ {node_name} ({step})")
        if node_name == "patch_applier":
            status = merged.get("patch_apply_status") or "unknown"
            files = merged.get("changed_files") or []
            log_detail(f"    apply: {status}, files={len(files)}")
        elif node_name == "test_runner":
            log_detail(
                f"    tests: {merged.get('validation_status') or 'unknown'}"
            )
        elif node_name == "git_committer":
            log_detail(
                f"    commit: {merged.get('commit_status') or 'unknown'}"
            )
        elif node_name == "github_pr":
            log_detail(f"    pr: {merged.get('pr_status') or 'unknown'}")
        if reporter:
            phase = _phase_after_node(node_name, merged)
            if phase:
                reporter.write(phase, node=node_name, retry_count=int(merged.get("retry_count", 0)))
        return result

    return wrapped


def _phase_after_node(node_name: str, state: dict[str, Any]) -> PipelinePhase | None:
    if node_name == "patch_applier" and state.get("patch_apply_status") == "apply_failed":
        return PipelinePhase.FAILED
    if node_name == "test_runner" and state.get("validation_status") == "failed":
        return PipelinePhase.RUNNING_TESTS
    if node_name == "git_committer" and state.get("commit_status") == "failed":
        return PipelinePhase.FAILED
    if node_name == "github_pr" and state.get("pr_status") == "failed":
        return PipelinePhase.FAILED
    return None
