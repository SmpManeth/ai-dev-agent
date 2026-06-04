"""Agent report formatters (investigation + patch proposal)."""

from __future__ import annotations

from models.state import AgentState, PlannerResult, ResearchResult

REPORT_WIDTH = 50
STATUS_READY = "READY FOR PATCH GENERATION"
STATUS_NEEDS_MORE = "NEEDS MORE INVESTIGATION"
STATUS_INCOMPLETE = "INCOMPLETE"


def _banner(title: str = "AI CODING AGENT REPORT") -> str:
    line = "=" * REPORT_WIDTH
    return f"{line}\n{title}\n{line}"


def _section(title: str, body: str) -> str:
    text = body.strip() if body else "(none)"
    return f"{title}:\n{text}"


def _numbered_plan(steps: list[str]) -> str:
    if not steps:
        return "(no plan steps)"
    return "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))


def _files_investigated(state: AgentState, planner: PlannerResult | None) -> list[str]:
    if state.files_read:
        return list(state.files_read.keys())
    if planner and planner.files_to_investigate:
        return list(planner.files_to_investigate)
    return []


def derive_status(state: AgentState, research: ResearchResult | None) -> str:
    if research is None:
        return STATUS_INCOMPLETE
    if not state.files_read and not (
        state.planner_result and state.planner_result.files_to_investigate
    ):
        return STATUS_NEEDS_MORE
    if research.confidence >= 60 and research.suspected_root_cause.strip():
        return STATUS_READY
    if research.suspected_root_cause.strip():
        return STATUS_NEEDS_MORE
    return STATUS_INCOMPLETE


def format_step1_report(state: AgentState) -> str:
    """Build Step 1 investigation report."""
    planner = state.planner_result
    if isinstance(planner, dict):
        planner = PlannerResult.model_validate(planner)

    research = state.research_result
    if isinstance(research, dict):
        research = ResearchResult.model_validate(research)

    sections: list[str] = [_banner(), ""]

    sections.append(_section("Task", state.task_description))
    sections.append("")

    repo_body = state.repo_summary_display or state.repo_summary or "(no summary)"
    sections.append(_section("Repository Summary", repo_body))
    sections.append("")

    investigated = _files_investigated(state, planner)
    files_body = "\n".join(f"- {path}" for path in investigated) if investigated else "(none)"
    sections.append(_section("Files Investigated", files_body))
    sections.append("")

    understanding = planner.understanding if planner else state.understanding
    sections.append(_section("Understanding", understanding or ""))
    sections.append("")

    plan_steps = (planner.plan if planner else None) or state.plan
    sections.append(_section("Investigation Plan", _numbered_plan(plan_steps)))
    sections.append("")

    if research:
        sections.append(_section("Root Cause", research.suspected_root_cause))
        sections.append("")
        sections.append(_section("Recommended Fix", research.recommended_fix))
        sections.append("")
        sections.append(f"Confidence:\n{research.confidence}%")
        sections.append("")
        sections.append(f"Status:\n{derive_status(state, research)}")
    else:
        sections.append(_section("Root Cause", "(analysis not completed)"))
        sections.append("")
        sections.append(_section("Recommended Fix", "(analysis not completed)"))
        sections.append("")
        sections.append("Confidence:\n0%")
        sections.append("")
        sections.append(f"Status:\n{derive_status(state, None)}")

    sections.append("")
    sections.append("=" * REPORT_WIDTH)
    sections.append("Step 1 complete — repository not modified")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_patch_section(state: AgentState) -> str:
    """Build Step 2 patch proposal section."""
    research = state.research_result
    if isinstance(research, dict):
        research = ResearchResult.model_validate(research) if research else None

    sections: list[str] = ["", "=" * REPORT_WIDTH, "PATCH PROPOSAL (Step 2)", "=" * REPORT_WIDTH, ""]

    if research:
        sections.append(_section("Root Cause", research.suspected_root_cause))
        sections.append("")
        sections.append(_section("Recommended Fix", research.recommended_fix))
        sections.append("")

    affected = state.affected_files or []
    affected_body = "\n".join(f"- {f}" for f in affected) if affected else "(none)"
    sections.append(_section("Affected Files", affected_body))
    sections.append("")

    sections.append(f"Risk Level:\n{state.risk_level or 'high'}")
    sections.append("")
    sections.append(_section("Patch Summary", state.patch_summary or "(none)"))
    sections.append("")

    if state.proposed_changes:
        sections.append(_section("Proposed Changes", state.proposed_changes))
        sections.append("")

    patch_path = state.patch_file_path or "(not saved)"
    sections.append(f"Patch File:\n{patch_path}")
    sections.append("")

    if state.unified_diff.strip():
        sections.append("Unified Diff (preview):")
        preview = state.unified_diff
        if len(preview) > 2000:
            preview = preview[:2000] + "\n... [truncated — see patch file] ..."
        sections.append(preview)
    else:
        sections.append("Unified Diff:\n(no patch generated)")

    sections.append("")
    sections.append("=" * REPORT_WIDTH)
    sections.append("Step 2 complete — patch NOT applied to repository")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_full_report(state: AgentState) -> str:
    """Full report: Step 1 investigation + Step 2 patch proposal."""
    return format_step1_report(state) + format_patch_section(state)
