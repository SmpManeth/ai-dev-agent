"""Agent report formatters (investigation + patch proposal)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    if state.apply_patch and state.patch_applied:
        sections.append("Step 2 complete — patch applied locally (see Step 3)")
    else:
        sections.append("Step 2 complete — patch NOT applied to repository")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_apply_section(state: AgentState) -> str:
    """Build Step 3 patch apply section."""
    if not state.apply_patch:
        return ""

    sections: list[str] = [
        "",
        "=" * REPORT_WIDTH,
        "PATCH APPLY (Step 3)",
        "=" * REPORT_WIDTH,
        "",
        f"Patch Validation Status:\n{state.patch_validation_status or '(not run)'}",
        "",
        f"Patch Apply Status:\n{state.patch_apply_status or '(not run)'}",
        "",
    ]

    if state.patch_apply_error:
        sections.append(_section("Apply Error", state.patch_apply_error))
        sections.append("")

    changed = state.changed_files or []
    changed_body = "\n".join(f"- {f}" for f in changed) if changed else "(none)"
    sections.append(_section("Changed Files", changed_body))
    sections.append("")

    if state.git_diff.strip():
        sections.append("Git Diff (preview):")
        preview = state.git_diff
        if len(preview) > 3000:
            preview = preview[:3000] + "\n... [truncated] ..."
        sections.append(preview)
    else:
        sections.append("Git Diff:\n(no diff — apply may have failed or repo is not git)")

    sections.append("")
    sections.append("=" * REPORT_WIDTH)
    if state.patch_applied:
        sections.append(
            "WARNING: Changes are applied locally but NOT committed or pushed."
        )
    else:
        sections.append("Step 3 — patch was not applied to the repository.")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_validation_section(state: AgentState) -> str:
    """Build Step 4 validation and self-fix section."""
    if not state.run_tests:
        return ""

    sections: list[str] = [
        "",
        "=" * REPORT_WIDTH,
        "VALIDATION (Step 4)",
        "=" * REPORT_WIDTH,
        "",
    ]

    cmds = state.validation_commands or []
    cmd_body = "\n".join(f"- {c}" for c in cmds) if cmds else "(none detected)"
    sections.append(_section("Validation Commands", cmd_body))
    sections.append("")

    sections.append(f"Final Status:\n{state.validation_status or 'skipped'}")
    sections.append("")
    sections.append(f"Retry Attempts:\n{state.retry_count} / {state.max_retries}")
    sections.append("")

    if state.validation_errors:
        err_body = "\n".join(f"- {e}" for e in state.validation_errors)
        sections.append(_section("Error Summary", err_body))
        sections.append("")

    if state.validation_output:
        sections.append("Validation Output (preview):")
        preview = state.validation_output
        if len(preview) > 2500:
            preview = preview[:2500] + "\n... [truncated] ..."
        sections.append(preview)
        sections.append("")

    if state.self_fix_history:
        sections.append("Self-Fix History:")
        for entry in state.self_fix_history:
            retry = entry.get("retry", "?")
            apply_st = entry.get("patch_apply_status", "n/a")
            sections.append(f"  - Retry {retry}: apply={apply_st}")
        sections.append("")

    sections.append("=" * REPORT_WIDTH)
    if state.validation_status == "passed":
        sections.append("Step 4 complete — validation passed")
    elif state.validation_status == "failed":
        sections.append("Step 4 complete — validation failed after retries")
    else:
        sections.append("Step 4 — validation skipped")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_commit_section(state: AgentState) -> str:
    """Build Step 5 git branch + commit section."""
    if not state.do_commit:
        return ""

    sections: list[str] = [
        "",
        "=" * REPORT_WIDTH,
        "GIT COMMIT (Step 5)",
        "=" * REPORT_WIDTH,
        "",
        f"Final Status:\n{state.commit_status or 'skipped'}",
        "",
    ]

    if state.original_branch:
        sections.append(f"Original Branch:\n{state.original_branch}")
        sections.append("")

    if state.branch_name:
        sections.append(f"New Branch:\n{state.branch_name}")
        sections.append("")

    changed = state.changed_files or []
    if changed:
        sections.append(_section("Changed Files", "\n".join(f"- {f}" for f in changed)))
        sections.append("")

    if state.commit_message:
        sections.append(_section("Commit Message", state.commit_message))
        sections.append("")

    if state.commit_hash:
        sections.append(f"Commit Hash:\n{state.commit_hash}")
        sections.append("")

    if state.commit_error:
        sections.append(_section("Commit Error", state.commit_error))
        sections.append("")

    sections.append("=" * REPORT_WIDTH)
    if state.commit_status == "committed":
        sections.append("Step 5 complete — local branch and commit created (not pushed)")
    elif state.commit_status == "rejected":
        sections.append("Step 5 — commit rejected by safety rules")
    else:
        sections.append("Step 5 — commit skipped or failed")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_github_section(state: AgentState) -> str:
    """Build Step 6 GitHub push + draft PR section."""
    if not state.create_pr:
        return ""

    sections: list[str] = [
        "",
        "=" * REPORT_WIDTH,
        "GITHUB DRAFT PR (Step 6)",
        "=" * REPORT_WIDTH,
        "",
        f"Branch Pushed:\n{state.push_status or 'skipped'}",
        "",
    ]

    if state.push_error:
        sections.append(_section("Push Error", state.push_error))
        sections.append("")

    sections.append(f"PR Status:\n{state.pr_status or 'skipped'}")
    sections.append("")

    if state.pr_url:
        sections.append(f"PR URL:\n{state.pr_url}")
        sections.append("")

    if state.pr_number:
        sections.append(f"PR Number:\n{state.pr_number}")
        sections.append("")

    if state.pr_error:
        sections.append(_section("PR Error", state.pr_error))
        sections.append("")

    sections.append("=" * REPORT_WIDTH)
    if state.pr_status in ("created", "exists"):
        sections.append("WARNING: Human review required before merge.")
        sections.append("Draft PR created — not merged or approved.")
    else:
        sections.append("Step 6 — push/PR skipped or failed")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_jira_section(state: AgentState) -> str:
    """Build Step 7 Jira update section."""
    if not state.update_jira and not state.jira_issue_key:
        return ""

    sections: list[str] = [
        "",
        "=" * REPORT_WIDTH,
        "JIRA UPDATE (Step 7)",
        "=" * REPORT_WIDTH,
        "",
    ]

    if state.jira_issue_key:
        sections.append(f"Issue Key:\n{state.jira_issue_key}")
        sections.append("")
    if state.jira_summary:
        sections.append(_section("Jira Summary", state.jira_summary))
        sections.append("")

    sections.append(f"Update Status:\n{state.jira_update_status or 'skipped'}")
    sections.append("")
    sections.append(f"Comment Added:\n{state.jira_comment_added}")
    sections.append("")
    sections.append(f"Transitioned to In Review:\n{state.jira_transitioned}")
    sections.append("")

    if state.jira_error:
        sections.append(_section("Jira Error", state.jira_error))
        sections.append("")

    sections.append("=" * REPORT_WIDTH)
    if state.jira_update_status == "updated":
        sections.append("Step 7 complete — Jira updated with PR link")
    elif state.jira_update_status == "partial":
        sections.append("Step 7 partial — comment and/or transition incomplete")
    else:
        sections.append("Step 7 — Jira update skipped or failed")
    sections.append("=" * REPORT_WIDTH)

    return "\n".join(sections)


def format_full_report(state: AgentState) -> str:
    """Full report: Steps 1–7 as applicable."""
    report = format_step1_report(state) + format_patch_section(state)
    if state.apply_patch:
        report += format_apply_section(state)
        if state.patch_applied:
            report = report.replace(
                "Step 1 complete — repository not modified",
                "Step 1 complete — investigation only (repo later modified in Step 3)",
            )
    report += format_validation_section(state)
    report += format_commit_section(state)
    report += format_github_section(state)
    report += format_jira_section(state)
    return report


def export_run_summary(state: AgentState) -> dict[str, Any]:
    """Machine-readable summary for Laravel dashboard integration."""
    research = state.research_result
    if isinstance(research, dict):
        research = ResearchResult.model_validate(research) if research else None

    return {
        "task_description": state.task_description,
        "status": state.current_step,
        "risk_level": state.risk_level,
        "validation_status": state.validation_status or "skipped",
        "validation_commands": state.validation_commands,
        "patch_apply_status": state.patch_apply_status,
        "patch_applied": state.patch_applied,
        "commit_status": state.commit_status,
        "commit_hash": state.commit_hash,
        "push_status": state.push_status,
        "branch_name": state.branch_name,
        "pr_url": state.pr_url,
        "pr_number": state.pr_number,
        "pr_status": state.pr_status,
        "jira_issue_key": state.jira_issue_key,
        "jira_update_status": state.jira_update_status,
        "changed_files": state.changed_files or state.affected_files,
        "error_message": state.patch_apply_error
        or state.commit_error
        or state.pr_error
        or state.jira_error,
        "root_cause": research.suspected_root_cause if research else "",
        "recommended_fix": research.recommended_fix if research else "",
    }


def write_run_summary(state: AgentState, path: str | Path) -> Path:
    """Write JSON summary file for external control panels."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(export_run_summary(state), indent=2),
        encoding="utf-8",
    )
    return target
