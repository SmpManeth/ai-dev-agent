"""Real-time pipeline progress files for dashboard polling."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class PipelinePhase(str, Enum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    SYNCING_REPO = "syncing_repo"
    PLANNING = "planning"
    RESEARCHING = "researching"
    GENERATING_PATCH = "generating_patch"
    VALIDATING_PATCH = "validating_patch"
    APPLYING_PATCH = "applying_patch"
    RUNNING_TESTS = "running_tests"
    SELF_FIXING = "self_fixing"
    COMMITTING = "committing"
    PUSHING = "pushing"
    CREATING_PR = "creating_pr"
    UPDATING_JIRA = "updating_jira"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


PHASE_LABELS: dict[PipelinePhase, str] = {
    PipelinePhase.NOT_STARTED: "Not started",
    PipelinePhase.QUEUED: "Queued — waiting for agent",
    PipelinePhase.SYNCING_REPO: "Syncing repository with origin",
    PipelinePhase.PLANNING: "Planning investigation",
    PipelinePhase.RESEARCHING: "Researching root cause",
    PipelinePhase.GENERATING_PATCH: "Generating code patch",
    PipelinePhase.VALIDATING_PATCH: "Validating patch safety",
    PipelinePhase.APPLYING_PATCH: "Applying patch to workspace",
    PipelinePhase.RUNNING_TESTS: "Running validation tests",
    PipelinePhase.SELF_FIXING: "Self-fixing after test failure",
    PipelinePhase.COMMITTING: "Creating branch and commit",
    PipelinePhase.PUSHING: "Pushing branch to GitHub",
    PipelinePhase.CREATING_PR: "Opening draft pull request",
    PipelinePhase.UPDATING_JIRA: "Updating Jira ticket",
    PipelinePhase.COMPLETED: "Completed successfully",
    PipelinePhase.FAILED: "Failed",
    PipelinePhase.SKIPPED: "Skipped",
    PipelinePhase.WAITING_APPROVAL: "Waiting for approval",
}

NODE_PHASES: dict[str, tuple[PipelinePhase, int]] = {
    "planner": (PipelinePhase.PLANNING, 1),
    "researcher": (PipelinePhase.RESEARCHING, 2),
    "patcher": (PipelinePhase.GENERATING_PATCH, 3),
    "patch_applier": (PipelinePhase.APPLYING_PATCH, 4),
    "test_runner": (PipelinePhase.RUNNING_TESTS, 5),
    "self_fix": (PipelinePhase.SELF_FIXING, 6),
    "git_committer": (PipelinePhase.COMMITTING, 7),
    "github_pr": (PipelinePhase.CREATING_PR, 8),
    "jira_updater": (PipelinePhase.UPDATING_JIRA, 9),
}

STEP_TOTAL = 9


def progress_path_for_issue(progress_dir: str | Path, issue_key: str) -> Path:
    safe = issue_key.replace("/", "_").strip() or "unknown"
    return Path(progress_dir) / f"{safe}.json"


class PipelineProgressReporter:
    """Writes atomic JSON snapshots for Laravel to poll."""

    def __init__(
        self,
        path: str | Path,
        *,
        issue_key: str = "",
        jira_summary: str = "",
    ) -> None:
        self.path = Path(path)
        self.issue_key = issue_key
        self.jira_summary = jira_summary
        self.started_at = _now_iso()
        self.history: list[dict[str, str]] = []

    def write(
        self,
        phase: PipelinePhase,
        *,
        label: str | None = None,
        node: str = "",
        step: int | None = None,
        retry_count: int = 0,
        terminal: bool = False,
        success: bool | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if label is None:
            label = PHASE_LABELS.get(phase, phase.value)
        if step is None and node in NODE_PHASES:
            step = NODE_PHASES[node][1]

        entry = {"phase": phase.value, "label": label, "at": _now_iso()}
        if not self.history or self.history[-1].get("phase") != phase.value:
            self.history.append(entry)
            if len(self.history) > 30:
                self.history = self.history[-30:]

        percent = _percent_for_phase(phase, step)
        payload: dict[str, Any] = {
            "issue_key": self.issue_key,
            "jira_summary": self.jira_summary,
            "phase": phase.value,
            "label": label,
            "percent": percent,
            "step": step or 0,
            "step_total": STEP_TOTAL,
            "node": node,
            "retry_count": retry_count,
            "terminal": terminal,
            "success": success,
            "error": (error or "")[:2000] if error else None,
            "started_at": self.started_at,
            "updated_at": _now_iso(),
            "history": self.history,
            "pid": os.getpid(),
        }
        if extra:
            payload.update(extra)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def enter_node(self, node: str, state: dict[str, Any] | None = None) -> None:
        phase, step = NODE_PHASES.get(node, (PipelinePhase.PLANNING, 0))
        retry = int((state or {}).get("retry_count", 0))
        label = PHASE_LABELS[phase]
        if node == "self_fix" and retry:
            label = f"Self-fix attempt {retry} — regenerating patch"
        self.write(phase, label=label, node=node, step=step, retry_count=retry)

    def complete_success(self, state: dict[str, Any] | None = None) -> None:
        self.write(
            PipelinePhase.COMPLETED,
            terminal=True,
            success=True,
            extra=_state_snapshot(state),
        )

    def complete_failed(self, error: str, state: dict[str, Any] | None = None) -> None:
        self.write(
            PipelinePhase.FAILED,
            label=f"Failed: {error[:120]}",
            terminal=True,
            success=False,
            error=error,
            extra=_state_snapshot(state),
        )

    def complete_skipped(self, reason: str) -> None:
        self.write(
            PipelinePhase.SKIPPED,
            label=reason,
            terminal=True,
            success=False,
            error=reason,
        )


def _percent_for_phase(phase: PipelinePhase, step: int | None) -> int:
    if phase == PipelinePhase.COMPLETED:
        return 100
    if phase in (PipelinePhase.FAILED, PipelinePhase.SKIPPED):
        return step and min(95, int(step / STEP_TOTAL * 100)) or 0
    if phase == PipelinePhase.NOT_STARTED:
        return 0
    if phase == PipelinePhase.QUEUED:
        return 2
    if step and step > 0:
        return min(95, int(step / STEP_TOTAL * 100))
    return 5


def _state_snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {}
    return {
        "validation_status": state.get("validation_status"),
        "commit_status": state.get("commit_status"),
        "pr_status": state.get("pr_status"),
        "pr_url": state.get("pr_url"),
        "patch_apply_status": state.get("patch_apply_status"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reporter_from_state(state: dict[str, Any]) -> PipelineProgressReporter | None:
    path = (state.get("progress_json_path") or "").strip()
    if not path:
        return None
    return PipelineProgressReporter(
        path,
        issue_key=str(state.get("jira_issue_key") or ""),
        jira_summary=str(state.get("jira_summary") or ""),
    )
