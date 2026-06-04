"""Clone and sync target git repositories automatically."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from config import Settings, get_settings


def _log(message: str, *, stream: TextIO | None = None) -> None:
    """Write progress to stderr so stdout stays clean for scripts."""
    out = stream or sys.stderr
    print(message, file=out, flush=True)


@dataclass(frozen=True)
class RepoSyncResult:
    """Outcome of clone/pull."""

    path: Path
    action: str
    branch: str
    message: str


def normalize_github_repo_name(repo: str) -> str:
    """Extract repo name from 'Blvs-Web-Site' or a GitHub URL."""
    value = repo.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    match = re.search(r"github\.com/[^/]+/([^/]+)$", value)
    if match:
        return match.group(1)
    if "/" in value:
        return value.split("/")[-1]
    return value


def normalize_github_owner(owner: str) -> str:
    """Reject email-style values; return org/user slug."""
    value = owner.strip()
    if "@" in value:
        raise RuntimeError(
            "GITHUB_OWNER must be the GitHub org or username, not an email address."
        )
    return value


def resolve_workspace_path(
    settings: Settings | None = None,
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> Path:
    """Default local path: {workspace_root}/{owner}/{repo}."""
    settings = settings or get_settings()
    gh_owner = normalize_github_owner(
        owner or settings.github_owner or "",
    )
    gh_repo = normalize_github_repo_name(
        repo or settings.github_repo or "",
    )
    if not gh_owner or not gh_repo:
        raise RuntimeError(
            "Set GITHUB_OWNER and GITHUB_REPO in .env (or pass --repo)."
        )

    root = Path(
        settings.workspace_root
        or (Path(__file__).resolve().parent.parent / "workspaces")
    ).resolve()
    return root / gh_owner / gh_repo


def _authenticated_clone_url(owner: str, repo: str, token: str) -> str:
    if token:
        return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    return f"https://github.com/{owner}/{repo}.git"


def _run_git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")


def _is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _remove_workspace_dir(path: Path) -> None:
    """Remove a broken or outdated workspace checkout."""
    if path.exists():
        _log(f"Removing {path} …")
        shutil.rmtree(path)


def _run_git_live(cmd: list[str], *, cwd: Path | None = None) -> None:
    """Run git with live stdout/stderr (for long clone/fetch operations)."""
    _log(f"Running: git {' '.join(cmd[1:] if cmd and cmd[0] == 'git' else cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git command failed (exit {result.returncode})")


def clone_repository(
    dest: Path,
    settings: Settings | None = None,
) -> RepoSyncResult:
    """Clone GitHub repository into dest (parent dirs created)."""
    settings = settings or get_settings()
    owner = normalize_github_owner(settings.github_owner or "")
    repo = normalize_github_repo_name(settings.github_repo or "")
    token = (settings.github_token or "").strip()

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and any(dest.iterdir()):
        if _is_git_repo(dest):
            _log(f"Repository already exists at {dest}, pulling latest.")
            return pull_latest(dest, settings)
        _remove_workspace_dir(dest)

    url = _authenticated_clone_url(owner, repo, token)
    _log(f"Cloning {owner}/{repo} into {dest} …")
    _log("(Large repos can take several minutes — git progress appears below.)")

    result = subprocess.run(
        ["git", "clone", "--progress", url, str(dest)],
        check=False,
    )
    if result.returncode != 0:
        _remove_workspace_dir(dest)
        raise RuntimeError(
            f"git clone failed (exit {result.returncode}). "
            "Check GITHUB_TOKEN and network access."
        )

    base = (settings.github_base_branch or "main").strip() or "main"
    _log(f"Checking out branch {base} …")
    _run_git(dest, "checkout", base)
    reset_worktree_to_origin(dest, settings)
    _ensure_dependencies_if_present(dest)

    return RepoSyncResult(
        path=dest,
        action="cloned",
        branch=base,
        message=f"Cloned {owner}/{repo} @ {base}",
    )


def pull_latest(
    repo_path: Path,
    settings: Settings | None = None,
) -> RepoSyncResult:
    """Fetch and fast-forward the configured base branch from origin."""
    settings = settings or get_settings()
    repo = repo_path.resolve()
    if not _is_git_repo(repo):
        raise RuntimeError(f"Not a git repository: {repo}")

    base = (settings.github_base_branch or "main").strip() or "main"
    token = (settings.github_token or "").strip()

    _log(f"Pulling latest {base} in {repo} …")

    if token:
        owner = normalize_github_owner(settings.github_owner or "")
        repo_name = normalize_github_repo_name(settings.github_repo or "")
        push_url = _authenticated_clone_url(owner, repo_name, token)
        _run_git(repo, "remote", "set-url", "origin", push_url)

    _log("Fetching from origin …")
    _run_git_live(["git", "-C", str(repo), "fetch", "origin"])
    _run_git(repo, "checkout", base)

    pull = subprocess.run(
        ["git", "-C", str(repo), "pull", "--ff-only", "origin", base],
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        _log("Pull failed with local changes — stashing and retrying …")
        subprocess.run(
            ["git", "-C", str(repo), "stash", "push", "-u", "-m", "ai-agent-auto-stash"],
            capture_output=True,
            check=False,
        )
        _run_git(repo, "checkout", base)
        pull = subprocess.run(
            ["git", "-C", str(repo), "pull", "--ff-only", "origin", base],
            capture_output=True,
            text=True,
            check=False,
        )
    if pull.returncode != 0:
        err = pull.stderr.strip() or pull.stdout.strip()
        raise RuntimeError(f"git pull failed: {err}")

    reset_worktree_to_origin(repo, settings)
    _ensure_dependencies_if_present(repo)

    return RepoSyncResult(
        path=repo,
        action="pulled",
        branch=base,
        message=f"Synced origin/{base}",
    )


def _ensure_dependencies_if_present(repo: Path) -> None:
    """Pre-install composer/npm deps after sync so validation can run."""
    try:
        from tools.test_tool import ensure_project_dependencies

        ok, log = ensure_project_dependencies(repo)
        if log:
            _log(log.splitlines()[-1] if log else "Dependencies ready.")
        if not ok:
            _log("Note: composer/npm install skipped or failed; agent will use lightweight checks.")
    except (OSError, RuntimeError) as exc:
        _log(f"Warning: dependency install skipped: {exc}")


def reset_worktree_to_origin(
    repo_path: str | Path,
    settings: Settings | None = None,
) -> None:
    """
    Reset to a clean base branch before the agent edits files.

    Avoids leftover changes causing patch apply errors (e.g. 'already exists').
    """
    settings = settings or get_settings()
    repo = Path(repo_path).resolve()
    if not _is_git_repo(repo):
        return

    base = (settings.github_base_branch or "main").strip() or "main"
    _log(f"Resetting worktree to origin/{base} …")
    _run_git(repo, "checkout", base)
    _run_git(repo, "reset", "--hard", f"origin/{base}")
    # Do not `git clean -fd`: it removes vendor/ and node_modules/ (untracked).
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "clean",
            "-fd",
            "--exclude=vendor/",
            "--exclude=node_modules/",
        ],
        capture_output=True,
        check=False,
    )


def ensure_repository(
    repo_path: str | Path | None = None,
    settings: Settings | None = None,
) -> RepoSyncResult:
    """
    Ensure a local clone exists and is up to date on the base branch.

    If the workspace already exists: pull latest from base branch.
    If pull fails: delete workspace and clone fresh.
    """
    settings = settings or get_settings()
    path = Path(repo_path).resolve() if repo_path else resolve_workspace_path(settings)

    _log(f"Workspace target: {path}")

    if _is_git_repo(path):
        try:
            return pull_latest(path, settings)
        except RuntimeError as exc:
            _log(f"Pull failed ({exc}). Re-cloning repository …")
            _remove_workspace_dir(path)
            return clone_repository(path, settings)

    if path.exists() and any(path.iterdir()):
        _log("Existing folder is not a valid git repo — removing and cloning fresh …")
        _remove_workspace_dir(path)

    return clone_repository(path, settings)
