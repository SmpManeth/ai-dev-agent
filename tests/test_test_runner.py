"""Test runner always validates after apply; --run-tests only selects full suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agents.test_runner import TestRunnerAgent
from models.state import AgentState
from tools.test_tool import ValidationResult


def test_runs_lightweight_validation_without_run_tests_flag(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^10.0"}}',
        encoding="utf-8",
    )
    views = tmp_path / "resources" / "views"
    views.mkdir(parents=True)
    (views / "page.blade.php").write_text("<div></div>\n", encoding="utf-8")

    mock_result = ValidationResult(
        status="passed",
        project_type="laravel",
        commands_attempted=["php -l"],
        output="Full test suite skipped for PHP/Blade-only patch.",
    )
    mock_run = MagicMock(return_value=mock_result)
    monkeypatch.setattr("agents.test_runner.run_validation", mock_run)

    state = AgentState(
        repo_path=str(tmp_path),
        task_description="fix slider",
        apply_patch=True,
        patch_applied=True,
        run_tests=False,
        changed_files=["resources/views/page.blade.php"],
    )
    out = TestRunnerAgent().run(state)

    assert out["validation_status"] == "passed"
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["full_test_suite"] is False
