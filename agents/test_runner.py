"""Test runner agent: run project validation after patch apply."""

from __future__ import annotations

from typing import Any

from models.state import AgentState
from tools.test_tool import output_allows_commit_without_full_tests, run_validation


class TestRunnerAgent:
    """Runs validation commands against the target repository."""

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.apply_patch or not state.patch_applied:
            return {
                "current_step": "test_skipped",
                "validation_status": "skipped",
                "validation_commands": [],
                "validation_output": "Skipped: patch was not applied.",
                "validation_errors": [],
            }

        candidates = list(state.changed_files or state.affected_files or [])
        result = run_validation(
            state.repo_path,
            changed_files=candidates or None,
            full_test_suite=state.run_tests,
        )
        status = result.status
        if status == "skipped" and output_allows_commit_without_full_tests(result.output):
            status = "passed"
        commands = result.commands_attempted

        reasoning = (
            f"{state.reasoning}\n\n"
            f"TestRunner: {status} ({result.project_type}), "
            f"commands={commands}."
        ).strip()

        return {
            "current_step": "tested",
            "validation_status": status,
            "validation_commands": commands,
            "validation_output": result.output,
            "validation_errors": result.errors,
            "reasoning": reasoning,
        }


def test_runner_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for test runner."""
    return TestRunnerAgent().run(AgentState.from_graph_dict(state))
