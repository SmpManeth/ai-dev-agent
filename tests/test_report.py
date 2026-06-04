"""Tests for Step 1 report formatting."""

from models.state import AgentState, PlannerResult, ResearchResult
from report import STATUS_READY, derive_status, format_step1_report


def test_format_step1_report_contains_required_sections() -> None:
    state = AgentState(
        repo_path="/tmp/repo",
        task_description="Fix username validation message",
        repo_summary_display="Python project\n3 Python files\nCurrent branch: main",
        planner_result=PlannerResult(
            understanding="Wrong error text for username validation.",
            files_to_investigate=["validators.py"],
            plan=["Inspect validators", "Check API usage"],
        ),
        files_read={"validators.py": "USERNAME_ERROR = '...'"},
        research_result=ResearchResult(
            suspected_root_cause="USERNAME_ERROR mentions email.",
            evidence=["validators.py line 8"],
            recommended_fix="Change USERNAME_ERROR to username wording.",
            confidence=92,
        ),
        current_step="researched",
    )
    report = format_step1_report(state)

    assert "AI CODING AGENT REPORT" in report
    assert "Fix username validation message" in report
    assert "Files Investigated" in report
    assert "- validators.py" in report
    assert "1. Inspect validators" in report
    assert "Root Cause:" in report
    assert "Confidence:\n92%" in report
    assert f"Status:\n{STATUS_READY}" in report
    assert "no files modified" in report.lower()


def test_derive_status_low_confidence() -> None:
    state = AgentState(
        repo_path="/tmp",
        task_description="x",
        files_read={"a.py": ""},
        research_result=ResearchResult(
            suspected_root_cause="maybe",
            recommended_fix="check more",
            confidence=40,
        ),
    )
    assert derive_status(state, state.research_result) == "NEEDS MORE INVESTIGATION"
