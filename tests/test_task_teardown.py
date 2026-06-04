"""Tests for per-task workspace teardown."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.task_teardown import TaskTeardownOptions, teardown_after_task


@patch("tools.task_teardown.reset_worktree_to_origin")
@patch("tools.task_teardown.delete_local_branch")
@patch("tools.task_teardown._list_local_branches")
@patch("tools.task_teardown.get_git_root")
@patch("tools.task_teardown._clear_agent_outputs")
def test_teardown_deletes_ai_fix_branches(
    mock_clear_outputs,
    mock_git_root,
    mock_list_branches,
    mock_delete_branch,
    mock_reset,
    tmp_path: Path,
):
    mock_git_root.return_value = tmp_path
    mock_list_branches.return_value = ["ai-fix/BVW-1", "ai-fix/BVW-2"]
    mock_delete_branch.return_value = True
    mock_clear_outputs.return_value = True

    settings = MagicMock()
    settings.github_base_branch = "develop"

    result = teardown_after_task(
        tmp_path,
        settings,
        options=TaskTeardownOptions(
            issue_key="BVW-2",
            task_branch="ai-fix/BVW-2",
            delete_all_ai_fix_branches=True,
        ),
    )

    assert mock_reset.called
    assert mock_delete_branch.call_count >= 1
    assert "ai-fix" in result.deleted_branches[0] or result.deleted_branches
