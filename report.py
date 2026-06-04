"""Step 1 plain-text report formatter (read + plan only — no writes)."""

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
    """Paths actually read, falling back to planner targets."""
    if state.files_read:
        return list(state.files_read.keys())
    if planner and planner.files_to_investigate:
        return list(planner.files_to_investigate)
    return []


def derive_status(state: AgentState, research: ResearchResult | None) -> str:
    """Step 1 completion status — never implies patches were applied."""
    if research is None:
        return STATUS_INCOMPLETE
    if not state.files_read and not (state.planner_result and state.planner_result.files_to_investigate):
        return STATUS_NEEDS_MORE
    if research.confidence >= 60 and research.suspected_root_cause.strip():
        return STATUS_READY
    if research.suspected_root_cause.strip():
        return STATUS_NEEDS_MORE
    return STATUS_INCOMPLETE


def format_step1_report(state: AgentState) -> str:
    """Build the Step 1 investigation report (no code changes)."""
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

    understanding = ""
    if planner:
        understanding = planner.understanding
    elif state.understanding:
        understanding = state.understanding
    sections.append(_section("Understanding", understanding))
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
        status = derive_status(state, research)
        sections.append(f"Status:\n{status}")
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
    sections.append("Mode: READ + PLAN — no files modified, no patches, no commits")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)
