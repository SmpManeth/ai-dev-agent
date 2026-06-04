#!/usr/bin/env python3
"""CLI entrypoint for the local bug-fix coding agent."""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

# LangChain structured-output triggers noisy (harmless) pydantic serializer warnings.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
    module="pydantic",
)

from rich.console import Console

from batch_jira import run_batch_from_jira
from config import get_settings
from jira_runner import load_jira_issue
from tools.git_commit_tool import jira_branch_name
from tools.repo_sync import ensure_repository, resolve_workspace_path
from report import format_full_report, write_run_summary
from tools.task_teardown import TaskTeardownOptions, teardown_after_task
from workflows.bug_fix_graph import run_bug_fix_workflow

console = Console()


def _default_progress_dir() -> Path:
    """Dashboard progress folder so CLI batch runs appear in the control plane."""
    root = Path(__file__).resolve().parent
    dashboard = root / "dashboard" / "storage" / "app" / "agent-progress"
    dashboard.mkdir(parents=True, exist_ok=True)
    return dashboard


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Local AI coding agent — investigate, patch, validate, commit, "
            "GitHub draft PR, and optional Jira updates"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Local repo path (optional with --from-jira; uses GITHUB_OWNER/REPO workspace)",
    )
    parser.add_argument("--task", default="", help="Bug description (optional with Jira)")
    parser.add_argument("--apply-patch", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--branch-name", default="")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument(
        "--jira-issue",
        default="",
        help="Optional: run workflow for a single Jira issue (testing)",
    )
    parser.add_argument(
        "--from-jira",
        action="store_true",
        help="Batch: process all open Jira issues labeled ai-fix",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=1,
        metavar="N",
        help="Jira issues per run (default: 1 — finish PR, then next issue on next cycle)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --from-jira: list issues only, no file/git/PR changes",
    )
    parser.add_argument("--revert-patch", action="store_true")
    parser.add_argument(
        "--summary-json",
        default="",
        help="Write machine-readable run summary JSON to this path (single run)",
    )
    parser.add_argument(
        "--batch-json",
        default="",
        help="Write batch results JSON (--from-jira)",
    )
    parser.add_argument(
        "--sync-repo",
        action="store_true",
        help="Clone or pull latest base branch before running (default for --from-jira)",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Do not clone/pull; use --repo path as-is",
    )
    parser.add_argument(
        "--progress-json",
        default="",
        help="Write live pipeline progress JSON (single run)",
    )
    parser.add_argument(
        "--progress-dir",
        default="",
        help="Directory for per-issue progress JSON files (--from-jira)",
    )
    return parser.parse_args()


def _validate_repo(repo: Path | None) -> Path:
    if repo is None:
        console.print("[red]Repository path is required[/red]")
        sys.exit(1)
    resolved = repo.resolve()
    if not resolved.is_dir():
        console.print(f"[red]Repository path does not exist:[/red] {resolved}")
        sys.exit(1)
    return resolved


def _run_one(
    *,
    repo: Path,
    task: str,
    apply_patch: bool,
    run_tests: bool,
    do_commit: bool,
    branch_name: str,
    create_pr: bool,
    update_jira: bool,
    jira_issue_key: str,
    jira_summary: str,
    jira_description: str,
    summary_json: str | None = None,
    progress_json: str | None = None,
) -> int:
    """Run workflow once; return exit code."""
    from tools.task_teardown import prepare_workspace_for_task

    settings = get_settings()
    exit_code = 1
    final_state = None
    try:
        if branch_name or jira_issue_key:
            prepare_workspace_for_task(
                repo,
                issue_key=jira_issue_key,
                task_branch=branch_name or "",
                settings=settings,
                progress_path=progress_json,
            )
        final_state = run_bug_fix_workflow(
            str(repo),
            task,
            apply_patch=apply_patch,
            run_tests=run_tests,
            do_commit=do_commit,
            branch_name=branch_name,
            create_pr=create_pr,
            update_jira=update_jira,
            jira_issue_key=jira_issue_key,
            jira_summary=jira_summary,
            jira_description=jira_description,
            progress_json_path=progress_json or "",
        )
        console.print(format_full_report(final_state), highlight=False)
        console.print()
        if summary_json:
            write_run_summary(final_state, summary_json)
        exit_code = 0
        if apply_patch and final_state.patch_apply_status == "apply_failed":
            exit_code = 1
        if run_tests and final_state.validation_status == "failed":
            exit_code = 1
        if do_commit and final_state.commit_status in ("failed", "rejected"):
            exit_code = 1
        if create_pr and final_state.pr_status in ("failed", "rejected"):
            exit_code = 1
        if create_pr and final_state.push_status == "failed":
            exit_code = 1
        if update_jira and final_state.jira_update_status in ("failed", "rejected"):
            exit_code = 1
    except Exception as exc:
        console.print(f"[red]Workflow failed:[/red] {exc}")
        exit_code = 1
    finally:
        teardown_after_task(
            repo,
            settings,
            options=TaskTeardownOptions(
                issue_key=jira_issue_key,
                task_branch=branch_name,
                progress_path=progress_json,
                clear_outputs=True,
                remove_progress_file=False,
            ),
        )
    return exit_code


def _resolve_repo(args: argparse.Namespace, settings) -> Path:
    """Resolve repo path and optionally sync from GitHub."""
    do_sync = (
        not args.skip_sync
        and (args.sync_repo or args.from_jira)
        and settings.auto_sync_repo
    )

    repo_arg = str(args.repo) if args.repo else ""
    if args.from_jira and not args.skip_sync and not repo_arg:
        try:
            repo_arg = str(resolve_workspace_path(settings))
        except RuntimeError:
            pass

    if do_sync:
        try:
            sync = ensure_repository(repo_arg or None, settings)
            console.print(f"Repository sync: {sync.message}", style="dim")
            return _validate_repo(sync.path)
        except (OSError, RuntimeError) as exc:
            console.print(f"[red]Repository sync failed:[/red] {exc}")
            sys.exit(1)

    return _validate_repo(args.repo)


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    repo = _resolve_repo(args, settings)

    if args.revert_patch:
        from tools.patch_tool import revert_patch

        try:
            changed = revert_patch(repo, files=None)
        except RuntimeError as exc:
            console.print(f"[red]Revert failed:[/red] {exc}")
            sys.exit(1)
        if changed:
            console.print(f"Reverted {len(changed)} file(s):", highlight=False)
            for path in changed:
                console.print(f"  - {path}", highlight=False)
        else:
            console.print("No changed files to revert.", highlight=False)
        return

    if args.jira_issue and args.from_jira:
        console.print("[red]Use only one of --jira-issue or --from-jira[/red]")
        sys.exit(1)

    if args.from_jira:
        if not args.dry_run:
            if not args.create_pr:
                console.print("[red]Batch mode requires --create-pr[/red]")
                sys.exit(1)
            if not settings.has_llm:
                console.print("[red]Missing OPENAI_API_KEY[/red]")
                sys.exit(1)
            if not settings.has_github:
                console.print("[red]Missing GITHUB_TOKEN for --create-pr[/red]")
                sys.exit(1)
        if not settings.has_jira:
            console.print(
                "[red]Missing Jira config.[/red] "
                "Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY"
            )
            sys.exit(1)

        apply_patch = args.apply_patch or args.run_tests or args.commit or args.create_pr
        if not args.dry_run and not apply_patch:
            console.print(
                "[yellow]Enabling --apply-patch --run-tests --commit for batch run.[/yellow]"
            )

        try:
            summary = run_batch_from_jira(
                repo,
                run_tests=args.run_tests or not args.dry_run,
                dry_run=args.dry_run,
                max_tasks=max(1, args.max_tasks),
                settings=settings,
                batch_json_path=args.batch_json or None,
                skip_repo_sync=settings.auto_sync_repo and not args.skip_sync,
                progress_dir=args.progress_dir or str(_default_progress_dir()),
            )
            if not args.progress_dir:
                console.print(
                    f"Pipeline progress: {_default_progress_dir()}",
                    style="dim",
                )
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Jira batch failed:[/red] {exc}")
            sys.exit(1)

        if summary.failed > 0:
            sys.exit(1)
        sys.exit(0)

    use_jira = bool(args.jira_issue.strip())
    apply_patch = args.apply_patch or args.run_tests or args.commit or args.create_pr
    do_commit = args.commit or args.create_pr

    if use_jira:
        if not args.create_pr:
            console.print("[red]Jira single-issue mode requires --create-pr[/red]")
            sys.exit(1)
        apply_patch = True
        do_commit = True

    if not use_jira and not args.task.strip():
        console.print("[red]--task is required unless using --from-jira[/red]")
        sys.exit(1)

    if not use_jira and args.repo is None:
        console.print("[red]--repo is required for single-task mode[/red]")
        sys.exit(1)

    if not settings.has_llm:
        console.print("[red]Missing OPENAI_API_KEY[/red]")
        sys.exit(1)
    if (args.create_pr or args.from_jira) and not settings.has_github:
        console.print("[red]Missing GITHUB_TOKEN (required for PR / auto repo sync)[/red]")
        sys.exit(1)
    if use_jira and not settings.has_jira:
        console.print(
            "[red]Missing Jira config.[/red] Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN"
        )
        sys.exit(1)

    task = args.task
    jira_key = ""
    jira_summary = ""
    jira_description = ""
    update_jira = False
    branch_name = (args.branch_name or "").strip()

    if args.jira_issue.strip():
        try:
            work = load_jira_issue(args.jira_issue.strip(), settings)
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Jira issue failed:[/red] {exc}")
            sys.exit(1)
        task = work.task_description
        jira_key = work.issue.key
        jira_summary = work.issue.summary
        jira_description = work.issue.description
        update_jira = True
        branch_name = branch_name or jira_branch_name(jira_key)
        console.print(f"Jira: {jira_key} — {jira_summary}\n", highlight=False)

    flow = ["Planner", "Researcher", "Patcher"]
    if apply_patch:
        flow.append("PatchApplier")
    if args.run_tests:
        flow.append("TestRunner")
    if do_commit:
        flow.append("GitCommitter")
    if args.create_pr:
        flow.append("GitHubPr")
    if update_jira:
        flow.append("JiraUpdater")
    console.print(f"Repository: {repo}", highlight=False)
    console.print(f"Task: {task[:120]}{'...' if len(task) > 120 else ''}", highlight=False)
    console.print(f"Running: {' → '.join(flow)}...\n", style="dim")

    sys.exit(
        _run_one(
            repo=repo,
            task=task,
            apply_patch=apply_patch,
            run_tests=args.run_tests,
            do_commit=do_commit,
            branch_name=branch_name,
            create_pr=args.create_pr,
            update_jira=update_jira,
            jira_issue_key=jira_key,
            jira_summary=jira_summary,
            jira_description=jira_description,
            summary_json=args.summary_json or None,
            progress_json=args.progress_json or None,
        )
    )


if __name__ == "__main__":
    main()
