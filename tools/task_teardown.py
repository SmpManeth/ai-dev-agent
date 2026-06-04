"""Reset workspace and agent artifacts after each task (success, failure, or stop)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import Settings, get_settings
from tools.agent_console import log_detail, log_step
from tools.git_commit_tool import (
    checkout_base_branch,
    delete_local_branch,
    get_current_branch,
    get_git_root,
)
from tools.patch_output import get_patch_paths
from tools.patch_tool import _cleanup_orig_files
from tools.repo_sync import reset_worktree_to_origin


@dataclass(frozen=True)
class TaskTeardownResult:
    base_branch: str
    deleted_branches: tuple[str, ...]
    outputs_cleared: bool
    progress_removed: bool


@dataclass(frozen=True)
class TaskTeardownOptions:
    """What to clean when a task ends or before the next one starts."""

    issue_key: str = ""
    task_branch: str = ""
    progress_path: str | Path | None = None
    clear_outputs: bool = True
    remove_progress_file: bool = False
    delete_all_ai_fix_branches: bool = True
    sync_with_origin: bool = True


def _list_local_branches(repo_path: Path, pattern: str) -> list[str]:
    git_root = get_git_root(repo_path)
    if git_root is None:
        return []
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(git_root), "branch", "--list", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        name = line.strip().lstrip("* ").strip()
        if name:
            names.append(name)
    return names


def _clear_agent_outputs() -> bool:
    patch_path, summary_path = get_patch_paths()
    removed = False
    for path in (patch_path, summary_path):
        if path.is_file():
            path.unlink()
            removed = True
    return removed


def _remove_progress_file(path: str | Path | None) -> bool:
    if not path:
        return False
    p = Path(path)
    tmp = p.with_suffix(".json.tmp")
    removed = False
    for candidate in (p, tmp):
        if candidate.is_file():
            candidate.unlink()
            removed = True
    return removed


def teardown_after_task(
    repo_path: str | Path,
    settings: Settings | None = None,
    *,
    options: TaskTeardownOptions | None = None,
) -> TaskTeardownResult:
    """
    Leave the workspace identical to a fresh checkout of the base branch.

    - Checkout base branch and hard-reset to origin/base
    - Remove untracked files (except vendor/ and node_modules/)
    - Delete local ai-fix/* branches (including this task's branch)
    - Clear latest patch artifacts under outputs/
    - Optionally remove per-issue progress JSON
    """
    settings = settings or get_settings()
    opts = options or TaskTeardownOptions()
    repo = Path(repo_path).resolve()
    base = (settings.github_base_branch or "main").strip() or "main"

    prefix = f"[{opts.issue_key}] " if opts.issue_key else ""
    log_step(f"{prefix}Cleaning workspace for next task…", style="bold yellow")

    deleted: list[str] = []

    if opts.sync_with_origin and get_git_root(repo) is not None:
        try:
            reset_worktree_to_origin(repo, settings)
        except RuntimeError as exc:
            log_detail(f"  Warning: origin reset failed: {exc}")
            try:
                checkout_base_branch(repo, base)
            except RuntimeError:
                pass
    elif get_git_root(repo) is not None:
        try:
            checkout_base_branch(repo, base)
            import subprocess

            subprocess.run(
                ["git", "-C", str(get_git_root(repo)), "reset", "--hard", f"origin/{base}"],
                capture_output=True,
                check=False,
            )
        except RuntimeError:
            pass

    if get_git_root(repo) is not None:
        _cleanup_orig_files(repo)

        branches_to_drop: set[str] = set()
        if opts.task_branch.strip():
            branches_to_drop.add(opts.task_branch.strip())
        if opts.delete_all_ai_fix_branches:
            branches_to_drop.update(_list_local_branches(repo, "ai-fix/*"))

        current = get_current_branch(repo)
        if current in branches_to_drop or (
            current.startswith("ai-fix/") and opts.delete_all_ai_fix_branches
        ):
            try:
                checkout_base_branch(repo, base)
            except RuntimeError:
                pass

        for branch in sorted(branches_to_drop):
            if delete_local_branch(repo, branch, base_branch=base):
                deleted.append(branch)
                log_detail(f"  Deleted local branch {branch}")

        try:
            reset_worktree_to_origin(repo, settings)
        except RuntimeError:
            pass

    outputs_cleared = False
    if opts.clear_outputs:
        outputs_cleared = _clear_agent_outputs()
        if outputs_cleared:
            log_detail("  Cleared outputs/latest.patch and latest_summary.md")

    progress_removed = False
    if opts.remove_progress_file:
        progress_removed = _remove_progress_file(opts.progress_path)
        if progress_removed:
            log_detail("  Removed progress JSON for this task")

    log_detail(f"  Workspace on origin/{base} — ready for next issue")

    return TaskTeardownResult(
        base_branch=base,
        deleted_branches=tuple(deleted),
        outputs_cleared=outputs_cleared,
        progress_removed=progress_removed,
    )


def prepare_workspace_for_task(
    repo_path: str | Path,
    *,
    issue_key: str,
    task_branch: str,
    settings: Settings | None = None,
    progress_path: str | Path | None = None,
) -> TaskTeardownResult:
    """Hard reset to base and remove stale branches before starting a task."""
    return teardown_after_task(
        repo_path,
        settings,
        options=TaskTeardownOptions(
            issue_key=issue_key,
            task_branch=task_branch,
            progress_path=progress_path,
            clear_outputs=True,
            remove_progress_file=False,
            delete_all_ai_fix_branches=True,
            sync_with_origin=True,
        ),
    )
