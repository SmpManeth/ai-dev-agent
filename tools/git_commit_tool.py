"""Local git branch and commit operations (no push)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.patch_guard import is_forbidden_path


@dataclass(frozen=True)
class GitStartContext:
    """Repository state before branch/commit."""

    git_root: Path
    repo_path: Path
    original_branch: str
    ready: bool
    error: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommitResult:
    """Outcome of branch + commit."""

    success: bool
    branch_created: bool
    branch_name: str
    commit_created: bool
    commit_hash: str
    commit_message: str
    original_branch: str
    staged_files: list[str]
    error: str = ""


def _run_git(git_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(git_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def get_git_root(repo_path: str | Path) -> Path | None:
    """Return git work tree root for repo_path, or None."""
    repo = Path(repo_path).resolve()
    result = _run_git(repo, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def get_current_branch(repo_path: str | Path) -> str:
    """Return current branch name (or 'HEAD' if detached)."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        return ""
    result = _run_git(git_root, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "HEAD"


def resolve_git_paths(repo_path: str | Path, relative_paths: list[str]) -> list[str]:
    """Map repo-relative paths to paths relative to git root."""
    repo = Path(repo_path).resolve()
    git_root = get_git_root(repo)
    if git_root is None:
        return relative_paths

    resolved: list[str] = []
    for rel in relative_paths:
        abs_file = (repo / rel).resolve()
        try:
            resolved.append(abs_file.relative_to(git_root).as_posix())
        except ValueError:
            resolved.append(rel.replace("\\", "/"))
    return resolved


def jira_branch_name(issue_key: str) -> str:
    """Branch name for a Jira issue: ai-fix/ABC-123."""
    key = issue_key.strip().upper()
    if not key:
        raise ValueError("Jira issue key is required for branch name.")
    return f"ai-fix/{key}"


def generate_branch_name(task_description: str) -> str:
    """Build ai-fix/{slug} from task text (non-Jira runs)."""
    slug = task_description.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")[:60] or "task"
    if not slug.startswith("fix-"):
        slug = f"fix-{slug}"
    return f"ai-fix/{slug}"


def format_commit_message(task_description: str) -> str:
    """Conventional commit message: fix: {summary}."""
    summary = task_description.strip().lower()
    summary = re.sub(r"\s+", " ", summary)
    if not summary:
        summary = "apply agent patch"
    return f"fix: {summary}"


def format_commit_message_for_jira(issue_key: str, summary: str) -> str:
    """Commit message: fix(ABC-123): summary."""
    key = issue_key.strip().upper()
    text = re.sub(r"\s+", " ", summary.strip()) or "apply agent patch"
    return f"fix({key}): {text}"


def branch_exists(repo_path: str | Path, branch_name: str) -> bool:
    """Return True if a local branch ref exists."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        return False
    result = _run_git(git_root, "rev-parse", "--verify", branch_name)
    return result.returncode == 0


def checkout_branch(repo_path: str | Path, branch_name: str) -> None:
    """Checkout an existing branch."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        raise RuntimeError("Not a git repository.")
    result = _run_git(git_root, "checkout", branch_name)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "checkout failed")


def checkout_base_branch(repo_path: str | Path, base_branch: str = "main") -> None:
    """Checkout base branch for the next batch item."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        raise RuntimeError("Not a git repository.")
    name = base_branch.strip() or "main"
    for candidate in (name, f"origin/{name}"):
        result = _run_git(git_root, "checkout", candidate)
        if result.returncode == 0:
            return
    raise RuntimeError(f"Could not checkout base branch '{name}'.")


def ensure_clean_start(repo_path: str | Path) -> GitStartContext:
    """
    Verify git is available and capture the starting branch.

    Warns (but does not block) if the worktree has other unstaged changes.
    """
    repo = Path(repo_path).resolve()
    git_root = get_git_root(repo)
    if git_root is None:
        return GitStartContext(
            git_root=repo,
            repo_path=repo,
            original_branch="",
            ready=False,
            error="Not a git repository.",
        )

    branch = get_current_branch(repo)
    warnings: list[str] = []

    status = _run_git(git_root, "status", "--porcelain")
    if status.returncode == 0 and status.stdout.strip():
        line_count = len(status.stdout.strip().splitlines())
        if line_count > 0:
            warnings.append(
                f"Worktree has {line_count} changed path(s) before commit step."
            )

    return GitStartContext(
        git_root=git_root,
        repo_path=repo,
        original_branch=branch,
        ready=True,
        warnings=tuple(warnings),
    )


def create_branch(repo_path: str | Path, branch_name: str) -> None:
    """Create and checkout a new branch from current HEAD."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        raise RuntimeError("Not a git repository.")

    safe_name = branch_name.strip()
    if not safe_name or " " in safe_name:
        raise ValueError(f"Invalid branch name: {branch_name!r}")

    exists = _run_git(git_root, "rev-parse", "--verify", safe_name)
    if exists.returncode == 0:
        checkout = _run_git(git_root, "checkout", safe_name)
        if checkout.returncode != 0:
            raise RuntimeError(checkout.stderr.strip() or "checkout failed")
        return

    create = _run_git(git_root, "checkout", "-b", safe_name)
    if create.returncode != 0:
        raise RuntimeError(create.stderr.strip() or "branch creation failed")


def stage_changes(repo_path: str | Path, files: list[str]) -> list[str]:
    """Stage only the given repository-relative paths. Returns git-root paths staged."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        raise RuntimeError("Not a git repository.")

    git_paths = resolve_git_paths(repo_path, files)
    if not git_paths:
        raise ValueError("No files to stage.")

    staged: list[str] = []
    for path in git_paths:
        add = _run_git(git_root, "add", "--", path)
        if add.returncode == 0:
            staged.append(path)
    if not staged:
        raise RuntimeError("git add failed for all paths.")
    return staged


def commit_changes(repo_path: str | Path, commit_message: str) -> str:
    """Create a commit with the staged changes. Returns commit hash."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        raise RuntimeError("Not a git repository.")

    msg = commit_message.strip()
    if not msg:
        raise ValueError("Commit message cannot be empty.")

    commit = _run_git(git_root, "commit", "-m", msg)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "commit failed")

    return get_commit_hash(repo_path)


def get_commit_hash(repo_path: str | Path) -> str:
    """Return full SHA of HEAD."""
    git_root = get_git_root(repo_path)
    if git_root is None:
        return ""
    result = _run_git(git_root, "rev-parse", "HEAD")
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def validate_files_for_commit(files: list[str]) -> tuple[list[str], list[str]]:
    """Return (allowed, blocked) paths."""
    allowed: list[str] = []
    blocked: list[str] = []
    for path in files:
        if is_forbidden_path(path):
            blocked.append(path)
        else:
            allowed.append(path)
    return allowed, blocked
