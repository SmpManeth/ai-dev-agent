"""Batch processor for Jira ai-fix issues."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from config import Settings, get_settings
from jira_runner import JiraWorkItem, build_task_from_issue
from tools.git_commit_tool import (
    branch_exists,
    checkout_base_branch,
    jira_branch_name,
)
from tools.github_tool import (
    find_open_pr_for_branch,
    get_pr_url,
    resolve_github_target,
)
from tools.jira_tool import (
    JiraIssue,
    add_comment,
    build_task_from_issue as _build_task,
    format_jira_failure_comment,
    format_jira_skip_comment,
    search_ai_fix_issues,
    validate_issue_for_agent,
)
from tools.patch_tool import revert_patch
from tools.repo_sync import ensure_repository, reset_worktree_to_origin
from workflows.bug_fix_graph import run_bug_fix_workflow

console = Console()

BATCH_STATUS_PR_CREATED = "pr_created"
BATCH_STATUS_FAILED = "failed"
BATCH_STATUS_SKIPPED = "skipped"
BATCH_STATUS_DRY_RUN = "dry_run"


@dataclass
class BatchItemResult:
    """Outcome for one Jira issue in a batch run."""

    issue_key: str
    summary: str
    status: str
    reason: str = ""
    pr_url: str = ""
    pr_number: int = 0
    branch_name: str = ""
    error_message: str = ""
    validation_status: str = ""
    changed_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchSummary:
    """Aggregate batch run results."""

    total_found: int = 0
    processed: int = 0
    pr_created: int = 0
    failed: int = 0
    skipped: int = 0
    dry_run: bool = False
    items: list[BatchItemResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_found": self.total_found,
            "processed": self.processed,
            "pr_created": self.pr_created,
            "failed": self.failed,
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "items": [i.to_dict() for i in self.items],
        }


def write_batch_summary(path: str | Path, summary: BatchSummary) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return target


def fetch_ai_fix_issues(
    settings: Settings | None = None,
    *,
    max_tasks: int = 50,
) -> list[JiraIssue]:
    """Fetch issues from Jira using the ai-fix JQL."""
    return search_ai_fix_issues(settings, max_results=max_tasks)


def check_duplicate_pr(
    repo_path: str | Path,
    branch_name: str,
    settings: Settings | None = None,
) -> tuple[bool, str, str]:
    """
    Return (should_skip, reason, pr_url).

    Skips when an open PR exists for the branch or the local branch already exists.
    """
    settings = settings or get_settings()
    repo = Path(repo_path)

    if branch_exists(repo, branch_name):
        if settings.has_github:
            try:
                target = resolve_github_target(repo, settings)
                token = settings.github_token or ""
                existing = find_open_pr_for_branch(
                    target.owner, target.repo, branch_name, token
                )
                if existing:
                    url = get_pr_url(existing)
                    return True, "PR already exists", url
            except RuntimeError:
                pass
        return True, f"Branch already exists: {branch_name}", ""

    if settings.has_github:
        try:
            target = resolve_github_target(repo, settings)
            token = settings.github_token or ""
            existing = find_open_pr_for_branch(
                target.owner, target.repo, branch_name, token
            )
            if existing:
                url = get_pr_url(existing)
                return True, "PR already exists", url
        except RuntimeError:
            pass

    return False, "", ""


def _failure_reason(state: Any) -> str:
    """Extract a human-readable failure reason from final workflow state."""
    if state.patch_apply_status == "apply_failed":
        return state.patch_apply_error or "Patch apply failed"
    if state.validation_status == "failed":
        return (state.validation_output or "Tests failed")[:500]
    if state.commit_status in ("failed", "rejected"):
        return state.commit_error or f"Commit {state.commit_status}"
    if state.push_status == "failed":
        return state.push_error or "Push failed"
    if state.pr_status in ("failed", "rejected"):
        return state.pr_error or f"PR {state.pr_status}"
    if state.jira_update_status == "failed":
        return state.jira_error or "Jira update failed"
    return state.patch_apply_error or state.commit_error or state.pr_error or "Workflow failed"


def _reset_repo_after_issue(repo_path: Path, base_branch: str, *, had_patch: bool) -> None:
    """Return repo to base branch for the next batch item."""
    if had_patch:
        try:
            revert_patch(repo_path, files=None)
        except RuntimeError:
            pass
    try:
        checkout_base_branch(repo_path, base_branch)
    except RuntimeError:
        pass


def run_batch_from_jira(
    repo_path: str | Path,
    *,
    run_tests: bool = True,
    dry_run: bool = False,
    max_tasks: int = 1,
    settings: Settings | None = None,
    batch_json_path: str | None = None,
    skip_repo_sync: bool = False,
) -> BatchSummary:
    """
    Process eligible ai-fix Jira issues sequentially (default: one per run).

    Each scheduler cycle should use max_tasks=1: complete one issue end-to-end
    (patch → tests → commit → draft PR → Jira update), then exit. The next cycle
    picks up the following issue. On failure, logs/comments and continues only
    when max_tasks > 1.
    """
    settings = settings or get_settings()
    base_branch = (settings.github_base_branch or "main").strip() or "main"

    if settings.auto_sync_repo and not skip_repo_sync:
        sync = ensure_repository(repo_path, settings)
        repo = sync.path
        console.print(f"Repository sync: {sync.message}", style="dim")
    else:
        repo = Path(repo_path).resolve()

    issues = fetch_ai_fix_issues(settings, max_tasks=max_tasks)
    summary = BatchSummary(total_found=len(issues), dry_run=dry_run)

    if not issues:
        console.print("No ai-fix Jira issues found.", highlight=False)
        if batch_json_path:
            write_batch_summary(batch_json_path, summary)
        return summary

    console.print(
        f"Found {len(issues)} ai-fix issue(s) for this cycle "
        f"(max {max_tasks} per run).\n",
        highlight=False,
    )

    if dry_run:
        for issue in issues:
            ok, reason = validate_issue_for_agent(issue, settings)
            branch = jira_branch_name(issue.key)
            skip, skip_reason, pr_url = check_duplicate_pr(repo, branch, settings)
            status = BATCH_STATUS_DRY_RUN
            item_reason = "Would process"
            if not ok:
                item_reason = f"Would skip (invalid): {reason}"
            elif skip:
                item_reason = f"Would skip: {skip_reason}"
            console.print(f"  {issue.key}: {issue.summary}", highlight=False)
            console.print(f"    → {item_reason}", style="dim")
            summary.items.append(
                BatchItemResult(
                    issue_key=issue.key,
                    summary=issue.summary,
                    status=status,
                    reason=item_reason,
                    pr_url=pr_url,
                    branch_name=branch,
                )
            )
        console.print("\nDry run complete — no files modified.", style="yellow")
        if batch_json_path:
            write_batch_summary(batch_json_path, summary)
        return summary

    for issue in issues:
        summary.processed += 1
        branch = jira_branch_name(issue.key)
        console.print(f"Processing {issue.key}...", style="bold")

        ok, reject_reason = validate_issue_for_agent(issue, settings)
        if not ok:
            result = BatchItemResult(
                issue_key=issue.key,
                summary=issue.summary,
                status=BATCH_STATUS_SKIPPED,
                reason=reject_reason,
                branch_name=branch,
            )
            summary.skipped += 1
            _print_item_result(result)
            summary.items.append(result)
            continue

        skip, skip_reason, pr_url = check_duplicate_pr(repo, branch, settings)
        if skip:
            try:
                add_comment(
                    issue.key,
                    format_jira_skip_comment(skip_reason, pr_url=pr_url),
                    settings,
                )
            except RuntimeError:
                pass
            result = BatchItemResult(
                issue_key=issue.key,
                summary=issue.summary,
                status=BATCH_STATUS_SKIPPED,
                reason=skip_reason,
                pr_url=pr_url,
                branch_name=branch,
            )
            summary.skipped += 1
            _print_item_result(result)
            summary.items.append(result)
            continue

        task_description = build_task_from_issue(issue)
        try:
            reset_worktree_to_origin(repo, settings)
        except RuntimeError as exc:
            console.print(f"[yellow]Worktree reset warning:[/yellow] {exc}")

        had_patch = False
        try:
            final_state = run_bug_fix_workflow(
                str(repo),
                task_description,
                apply_patch=True,
                run_tests=run_tests,
                do_commit=True,
                branch_name=branch,
                create_pr=True,
                update_jira=True,
                jira_issue_key=issue.key,
                jira_summary=issue.summary,
                jira_description=issue.description,
            )
            had_patch = bool(final_state.patch_applied)
        except Exception as exc:
            reason = str(exc)
            try:
                add_comment(
                    issue.key,
                    format_jira_failure_comment(reason),
                    settings,
                )
            except RuntimeError:
                pass
            result = BatchItemResult(
                issue_key=issue.key,
                summary=issue.summary,
                status=BATCH_STATUS_FAILED,
                reason=reason,
                error_message=reason,
                branch_name=branch,
            )
            summary.failed += 1
            _print_item_result(result)
            summary.items.append(result)
            _reset_repo_after_issue(repo, base_branch, had_patch=had_patch)
            continue

        _reset_repo_after_issue(repo, base_branch, had_patch=had_patch)

        if final_state.pr_status in ("created", "exists") and final_state.pr_url:
            result = BatchItemResult(
                issue_key=issue.key,
                summary=issue.summary,
                status=BATCH_STATUS_PR_CREATED,
                reason="",
                pr_url=final_state.pr_url,
                pr_number=final_state.pr_number,
                branch_name=branch,
                validation_status=final_state.validation_status or "",
                changed_files=list(final_state.changed_files or []),
            )
            summary.pr_created += 1
            _print_item_result(result)
            summary.items.append(result)
            continue

        reason = _failure_reason(final_state)
        try:
            add_comment(
                issue.key,
                format_jira_failure_comment(reason),
                settings,
            )
        except RuntimeError:
            pass

        result = BatchItemResult(
            issue_key=issue.key,
            summary=issue.summary,
            status=BATCH_STATUS_FAILED,
            reason=reason,
            error_message=reason,
            branch_name=branch,
            validation_status=final_state.validation_status or "",
            changed_files=list(final_state.changed_files or []),
        )
        summary.failed += 1
        _print_item_result(result)
        summary.items.append(result)

    _print_batch_completed(summary)
    if batch_json_path:
        write_batch_summary(batch_json_path, summary)
    return summary


def _print_item_result(result: BatchItemResult) -> None:
    console.print(f"Status: {result.status}", highlight=False)
    if result.reason:
        console.print(f"Reason: {result.reason}", highlight=False)
    if result.pr_url:
        console.print(f"PR: {result.pr_url}", highlight=False)
    console.print()


def _print_batch_completed(summary: BatchSummary) -> None:
    console.print("Batch completed:", style="bold")
    console.print(f"  - {summary.pr_created} PR created", highlight=False)
    console.print(f"  - {summary.failed} failed", highlight=False)
    console.print(f"  - {summary.skipped} skipped", highlight=False)


def work_item_from_issue(issue: JiraIssue) -> JiraWorkItem:
    return JiraWorkItem(issue=issue, task_description=_build_task(issue))
