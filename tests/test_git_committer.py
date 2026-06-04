"""Tests for git committer eligibility rules."""

from models.state import AgentState
from agents.git_committer import validation_allows_commit


def test_validation_requires_pass_when_run_tests() -> None:
    state = AgentState(
        repo_path="/tmp",
        task_description="x",
        run_tests=True,
        validation_status="failed",
    )
    ok, _ = validation_allows_commit(state)
    assert ok is False


def test_validation_allows_pass() -> None:
    state = AgentState(
        repo_path="/tmp",
        task_description="x",
        run_tests=True,
        validation_status="passed",
    )
    ok, _ = validation_allows_commit(state)
    assert ok is True


def test_validation_allows_skip_without_tests() -> None:
    state = AgentState(
        repo_path="/tmp",
        task_description="x",
        run_tests=False,
        validation_status="",
    )
    ok, _ = validation_allows_commit(state)
    assert ok is True


def test_validation_allows_skipped_with_lightweight_pass_message() -> None:
    state = AgentState(
        repo_path="/tmp",
        task_description="x",
        run_tests=True,
        validation_status="skipped",
        validation_output=(
            "Running composer install (vendor/ missing) …\n\n"
            "Validation passed: patch only changes non-PHP files (README.md)."
        ),
    )
    ok, reason = validation_allows_commit(state)
    assert ok is True
    assert "reduced checks" in reason
