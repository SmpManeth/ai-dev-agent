"""Patcher agent: generate a safe proposed unified diff (no repo writes)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from config import get_settings, load_agent_prompt, load_prompt
from tools.llm_factory import build_agent_llm
from models.state import AgentState, PatchResult, PlannerResult, ResearchResult
from tools.patch_guard import (
    diff_only_touches_files,
    extract_diff_paths,
    filter_allowed_files,
    is_forbidden_path,
    normalize_risk_level,
)
from tools.diff_guard import validate_proposed_diff
from tools.file_excerpt import excerpt_for_patch
from tools.file_tool import FileTool
from tools.patch_format import repair_diff_if_needed
from tools.patch_output import write_patch_artifacts

CONFIDENCE_MIN_FOR_PATCH = 60


def _patch_context(content: str, path: str, task: str) -> str:
    anchors = [w for w in re.split(r"\W+", task) if len(w) > 6][:12]
    return excerpt_for_patch(content, extra_anchors=anchors + [path.split("/")[-1]])


def _disk_files_for_repair(
    repo_path: str,
    diff: str,
    files_read: dict[str, str],
) -> dict[str, str]:
    """Load full on-disk content for paths touched by the diff (repair uses real lines)."""
    paths = extract_diff_paths(diff) or list(files_read.keys())
    tool = FileTool(repo_path)
    out: dict[str, str] = dict(files_read)
    for path in paths:
        try:
            out[path] = tool.read_file(path)
        except (OSError, ValueError, PermissionError, FileNotFoundError):
            pass
    return out


def _strip_markdown_fences(diff: str) -> str:
    text = diff.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[\w]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


class PatcherAgent:
    """Produces a proposed patch file from research results."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _self_fix_addon(self, state: AgentState) -> str:
        if state.retry_count <= 0:
            return ""
        try:
            return load_prompt("self_fix_patcher_addon.txt")
        except FileNotFoundError:
            return ""

    def _validation_feedback_block(self, state: AgentState) -> str:
        fix_errors = getattr(state, "fix_verification_errors", None) or []
        apply_err = (state.patch_apply_error or "").strip()
        if (
            not state.validation_errors
            and not state.validation_output
            and not fix_errors
            and not apply_err
        ):
            return ""
        error_items = list(state.validation_errors) + list(fix_errors)
        if apply_err:
            error_items.append(f"Patch apply failed: {apply_err}")
        errors = "\n".join(f"- {e}" for e in error_items) or "(none)"
        fix_block = ""
        if fix_errors or state.fix_verification_output:
            fix_block = f"""
### Fix verification (patch did not solve the bug)
{(state.fix_verification_output or '')[:4000]}
"""
        return f"""
## Failures (self-fix retry {state.retry_count})
The previous patch was reverted. Address root cause and verification feedback.

### Error summary
{errors}
{fix_block}
### Command output
{state.validation_output[:8000]}
"""

    def _skip_result(
        self,
        state: AgentState,
        *,
        summary: str,
        reason: str,
        risk: str = "high",
    ) -> dict[str, Any]:
        """Build state update when no patch is generated."""
        research = state.research_result
        root_cause = research.suspected_root_cause if research else ""
        recommended = research.recommended_fix if research else ""
        confidence = research.confidence if research else 0

        patch_path, _ = write_patch_artifacts(
            unified_diff="",
            patch_summary=summary,
            task_description=state.task_description,
            root_cause=root_cause,
            recommended_fix=recommended,
            affected_files=[],
            risk_level=risk,
            proposed_changes=reason,
            confidence=confidence,
            skipped=True,
            skip_reason=reason,
        )

        result = PatchResult(
            proposed_changes=reason,
            affected_files=[],
            risk_level="high",  # type: ignore[arg-type]
            patch_summary=summary,
            unified_diff="",
        )

        reasoning = f"{state.reasoning}\n\nPatcher: no patch generated ({reason})".strip()

        return {
            "current_step": "patched",
            "proposed_changes": reason,
            "affected_files": [],
            "risk_level": "high",
            "patch_summary": summary,
            "unified_diff": "",
            "patch_file_path": str(patch_path),
            "patch_result": result.model_dump(),
            "reasoning": reasoning,
        }

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute patch proposal logic and return state updates."""
        research = state.research_result
        if research is None:
            return self._skip_result(
                state,
                summary="Research phase did not complete.",
                reason="Missing research_result.",
            )

        if isinstance(research, dict):
            research = ResearchResult.model_validate(research)

        is_retry = state.retry_count > 0
        if (
            not is_retry
            and research.confidence < CONFIDENCE_MIN_FOR_PATCH
        ):
            return self._skip_result(
                state,
                summary=(
                    f"Patch not generated: research confidence ({research.confidence}%) "
                    f"is below threshold ({CONFIDENCE_MIN_FOR_PATCH}%)."
                ),
                reason=f"Low confidence ({research.confidence}%).",
            )

        if not state.files_read:
            return self._skip_result(
                state,
                summary="Patch not generated: no file contents available to diff against.",
                reason="No files_read in state.",
            )

        planner = state.planner_result
        if isinstance(planner, dict):
            planner = PlannerResult.model_validate(planner) if planner else None

        plan_steps = (planner.plan if planner else None) or state.plan
        plan_text = "\n".join(f"{i}. {step}" for i, step in enumerate(plan_steps, start=1))

        file_sections = []
        for path, content in state.files_read.items():
            if content.startswith("(unable to read"):
                continue
            file_sections.append(
                f"### {path}\n```\n{_patch_context(content, path, state.task_description)}\n```"
            )
        files_text = "\n\n".join(file_sections)

        system = load_agent_prompt("patcher_prompt.txt")
        if is_retry:
            system = system + "\n\n" + self._self_fix_addon(state)
        user_content = f"""## Bug description
{state.task_description}

## Investigation plan
{plan_text or "(none)"}

## Root cause
{research.suspected_root_cause}

## Recommended fix
{research.recommended_fix}

## Research confidence
{research.confidence}%

## Evidence
{chr(10).join(f"- {e}" for e in research.evidence) or "(none)"}

## Files (original content — diff must only modify these paths)
{files_text}
{self._validation_feedback_block(state)}

Respond with JSON: proposed_changes, affected_files, risk_level, patch_summary, unified_diff.
"""

        llm = build_agent_llm("patcher", self._settings)
        structured = llm.with_structured_output(PatchResult)
        result: PatchResult = structured.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user_content),
            ]
        )

        result.risk_level = normalize_risk_level(str(result.risk_level))
        raw_diff = _strip_markdown_fences(result.unified_diff)
        result.unified_diff = repair_diff_if_needed(
            raw_diff,
            _disk_files_for_repair(state.repo_path, raw_diff, state.files_read),
        )

        guard_errors = validate_proposed_diff(
            result.unified_diff,
            state.files_read,
            task_description=state.task_description,
        )
        if guard_errors:
            return self._skip_result(
                state,
                summary="Patch blocked by safety guard: " + "; ".join(guard_errors[:3]),
                reason=guard_errors[0],
            )

        allowed_candidates, blocked = filter_allowed_files(result.affected_files)
        if blocked:
            return self._skip_result(
                state,
                summary=f"Patch blocked: forbidden paths {blocked}.",
                reason=f"Forbidden paths: {', '.join(blocked)}",
            )

        if result.risk_level == "high":
            if is_retry and result.unified_diff.strip():
                result = result.model_copy(update={"risk_level": "medium"})
            else:
                return self._skip_result(
                    state,
                    summary=result.patch_summary or "Patch not generated: risk level is high.",
                    reason="Patcher or guard classified risk as high.",
                )

        diff_paths = extract_diff_paths(result.unified_diff) or allowed_candidates
        allowed_set = set(state.files_read.keys())
        final_files, blocked_from_diff = filter_allowed_files(diff_paths)
        if blocked_from_diff:
            return self._skip_result(
                state,
                summary=f"Patch blocked: diff touches forbidden paths {blocked_from_diff}.",
                reason=f"Diff forbidden paths: {', '.join(blocked_from_diff)}",
            )

        if result.unified_diff.strip() and not diff_only_touches_files(
            result.unified_diff, allowed_set
        ):
            return self._skip_result(
                state,
                summary="Patch blocked: diff references files not provided in files_read.",
                reason="Diff paths outside files_read.",
            )

        if not result.unified_diff.strip():
            return self._skip_result(
                state,
                summary=result.patch_summary or "No unified diff produced.",
                reason="Empty unified_diff from patcher.",
                risk=result.risk_level,
            )

        for path in final_files:
            if is_forbidden_path(path):
                return self._skip_result(
                    state,
                    summary=f"Patch blocked: forbidden path {path}.",
                    reason=f"Forbidden: {path}",
                )

        patch_path, _ = write_patch_artifacts(
            unified_diff=result.unified_diff,
            patch_summary=result.patch_summary,
            task_description=state.task_description,
            root_cause=research.suspected_root_cause,
            recommended_fix=research.recommended_fix,
            affected_files=final_files,
            risk_level=result.risk_level,
            proposed_changes=result.proposed_changes,
            confidence=research.confidence,
            skipped=False,
        )

        reasoning = (
            f"{state.reasoning}\n\n"
            f"Patcher: proposed patch for {len(final_files)} file(s), "
            f"risk={result.risk_level}."
        ).strip()

        return {
            "current_step": "patched",
            "proposed_changes": result.proposed_changes,
            "affected_files": final_files,
            "risk_level": result.risk_level,
            "patch_summary": result.patch_summary,
            "unified_diff": result.unified_diff,
            "patch_file_path": str(patch_path),
            "patch_result": result.model_dump(),
            "reasoning": reasoning,
        }


def patcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for the patcher agent."""
    agent_state = AgentState.from_graph_dict(state)
    if agent_state.research_result is None and state.get("research_result"):
        agent_state.research_result = ResearchResult.model_validate(
            state["research_result"]
        )
    agent = PatcherAgent()
    return agent.run(agent_state)
