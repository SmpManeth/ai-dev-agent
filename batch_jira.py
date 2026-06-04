"""Batch processor for Jira ai-fix issues."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from config import Settings, get_settings
from jira_runner import JiraWorkItem, build_task_from_issue
from tools.git_commit_tool import jira_branch_name
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
from tools.pipeline_progress import (
    PipelinePhase,
    PipelineProgressReporter,
    progress_path_for_issue,
)
from tools.repo_sync import ensure_repository
from tools.task_teardown import (
    TaskTeardownOptions,
    prepare_workspace_for_task,
    teardown_after_task,
)
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
    pipeline_phase: str = ""
    pipeline_label: str = ""
    pipeline_percent: int = 0

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

    Skips only when an open PR already exists on GitHub for this branch.

    Local ai-fix branches are removed by workspace teardown before each run.
    """
    settings = settings or get_settings()
    repo = Path(repo_path)
    _ = repo  # reserved for future local checks

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


def _finalize_task_workspace(
    repo: Path,
    *,
    issue_key: str,
    task_branch: str,
    progress_path: str,
    settings: Settings,
) -> None:
    """Full cleanup so the next Jira issue starts from a pristine base branch."""
    teardown_after_task(
        repo,
        settings,
        options=TaskTeardownOptions(
            issue_key=issue_key,
            task_branch=task_branch,
            progress_path=progress_path or None,
            clear_outputs=True,
            remove_progress_file=False,
            delete_all_ai_fix_branches=True,
            sync_with_origin=True,
        ),
    )


def run_batch_from_jira(
    repo_path: str | Path,
    *,
    run_tests: bool = True,
    dry_run: bool = False,
    max_tasks: int = 1,
    settings: Settings | None = None,
    batch_json_path: str | None = None,
    skip_repo_sync: bool = False,
    progress_dir: str | Path | None = None,
) -> BatchSummary:
    """
    Process eligible ai-fix Jira issues sequentially (default: one per run).

    Each scheduler cycle should use max_tasks=1: complete one issue end-to-end
    (patch → tests → commit → draft PR → Jira update), then exit. The next cycle
    picks up the following issue. On failure, logs/comments and continues only
    when max_tasks > 1.
    """
    from tools.audit_log import append_audit_event
    from tools.security_policy import (
        assert_agent_enabled,
        assert_repo_allowed,
        assert_repo_path_allowed,
    )

    assert_agent_enabled()
    settings = settings or get_settings()
    if settings.github_owner and settings.github_repo:
        assert_repo_allowed(settings.github_owner, settings.github_repo)
    assert_repo_path_allowed(repo_path)
    append_audit_event("batch_start", detail=str(repo_path))
    base_branch = (settings.github_base_branch or "main").strip() or "main"

    if settings.auto_sync_repo and not skip_repo_sync:
        sync = ensure_repository(repo_path, settings)
        repo = sync.path
        console.print(f"Repository sync: {sync.message}", style="dim")
    else:
        repo = Path(repo_path).resolve()

    progress_root = Path(progress_dir).resolve() if progress_dir else None
    if progress_root:
        progress_root.mkdir(parents=True, exist_ok=True)

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

        progress_path = (
            str(progress_path_for_issue(progress_root, issue.key))
            if progress_root
            else ""
        )
        reporter = (
            PipelineProgressReporter(
                progress_path,
                issue_key=issue.key,
                jira_summary=issue.summary,
            )
            if progress_path
            else None
        )

        ok, reject_reason = validate_issue_for_agent(issue, settings)
        if not ok:
            if reporter:
                reporter.complete_skipped(reject_reason)
            result = BatchItemResult(
                issue_key=issue.key,
                summary=issue.summary,
                status=BATCH_STATUS_SKIPPED,
                reason=reject_reason,
                branch_name=branch,
                pipeline_phase=PipelinePhase.SKIPPED.value,
                pipeline_label=reject_reason,
            )
            summary.skipped += 1
            _print_item_result(result)
            summary.items.append(result)
            prepare_workspace_for_task(
                repo,
                issue_key=issue.key,
                task_branch=branch,
                settings=settings,
                progress_path=progress_path,
            )
            continue

        skip, skip_reason, pr_url = check_duplicate_pr(repo, branch, settings)
        if skip:
            if reporter:
                reporter.complete_skipped(skip_reason)
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
                pipeline_phase=PipelinePhase.SKIPPED.value,
                pipeline_label=skip_reason,
            )
            summary.skipped += 1
            _print_item_result(result)
            summary.items.append(result)
            prepare_workspace_for_task(
                repo,
                issue_key=issue.key,
                task_branch=branch,
                settings=settings,
                progress_path=progress_path,
            )
            continue

        if reporter:
            reporter.write(PipelinePhase.SYNCING_REPO, label="Resetting workspace to base branch")

        prepare_workspace_for_task(
            repo,
            issue_key=issue.key,
            task_branch=branch,
            settings=settings,
            progress_path=progress_path,
        )

        task_description = build_task_from_issue(issue)
        try:
            if reporter:
                reporter.write(PipelinePhase.QUEUED, label="Starting agent pipeline")

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
                progress_json_path=progress_path,
            )
        except Exception as exc:
            reason = str(exc)
            if reporter:
                reporter.complete_failed(reason)
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
                pipeline_phase=PipelinePhase.FAILED.value,
                pipeline_label=reason[:200],
            )
            summary.failed += 1
            _print_item_result(result)
            summary.items.append(result)
            _finalize_task_workspace(
                repo,
                issue_key=issue.key,
                task_branch=branch,
                progress_path=progress_path,
                settings=settings,
            )
            continue

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
                pipeline_phase=PipelinePhase.COMPLETED.value,
                pipeline_label="Draft pull request created",
                pipeline_percent=100,
            )
            summary.pr_created += 1
            _print_item_result(result)
            summary.items.append(result)
        else:
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
                pipeline_phase=PipelinePhase.FAILED.value,
                pipeline_label=reason[:200],
            )
            summary.failed += 1
            _print_item_result(result)
            summary.items.append(result)

        _finalize_task_workspace(
            repo,
            issue_key=issue.key,
            task_branch=branch,
            progress_path=progress_path,
            settings=settings,
        )

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
