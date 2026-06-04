"""Git repository introspection (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git import InvalidGitRepositoryError, Repo
from git.exc import GitCommandError


@dataclass(frozen=True)
class CommitInfo:
    """Summary of a single git commit."""

    sha: str
    message: str
    author: str


@dataclass(frozen=True)
class RepoSummary:
    """High-level git repository metadata."""

    is_git_repo: bool
    branch: str | None
    recent_commits: list[CommitInfo]
    dirty: bool
    untracked_count: int

    def to_text(self) -> str:
        """Human-readable summary for prompts and CLI."""
        if not self.is_git_repo:
            return "Not a git repository (filesystem inspection only)."

        lines = [
            f"Branch: {self.branch or 'unknown'}",
            f"Working tree dirty: {self.dirty}",
            f"Untracked files: {self.untracked_count}",
            "Recent commits:",
        ]
        if not self.recent_commits:
            lines.append("  (none)")
        for commit in self.recent_commits:
            short = commit.sha[:8]
            msg = commit.message.split("\n", maxsplit=1)[0][:80]
            lines.append(f"  {short} — {msg} ({commit.author})")
        return "\n".join(lines)


class GitTool:
    """Read-only git operations for repository context."""

    def __init__(self, repo_path: str | Path) -> None:
        self.root = Path(repo_path).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Repository path does not exist: {self.root}")

    def get_repo_summary(self, *, max_commits: int = 5) -> RepoSummary:
        """
        Return current branch, recent commits, and working tree status.

        Falls back gracefully when the path is not a git repository.
        """
        try:
            repo = Repo(self.root, search_parent_directories=True)
        except InvalidGitRepositoryError:
            return RepoSummary(
                is_git_repo=False,
                branch=None,
                recent_commits=[],
                dirty=False,
                untracked_count=0,
            )

        try:
            branch = repo.active_branch.name
        except (TypeError, GitCommandError):
            branch = "detached HEAD"

        commits: list[CommitInfo] = []
        try:
            for commit in list(repo.iter_commits(max_count=max_commits)):
                commits.append(
                    CommitInfo(
                        sha=commit.hexsha,
                        message=commit.message.strip(),
                        author=str(commit.author),
                    )
                )
        except GitCommandError:
            pass

        dirty = repo.is_dirty(untracked_files=False)
        try:
            untracked = len(repo.untracked_files)
        except GitCommandError:
            untracked = 0

        return RepoSummary(
            is_git_repo=True,
            branch=branch,
            recent_commits=commits,
            dirty=dirty,
            untracked_count=untracked,
        )
