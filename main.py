#!/usr/bin/env python3
"""CLI entrypoint for the local bug-fix coding agent (read + plan mode)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from config import get_settings
from models.state import AgentState, PlannerResult, ResearchResult
from workflows.bug_fix_graph import run_bug_fix_workflow

console = Console()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local AI coding agent — bug investigation (read + plan only)",
    )
    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
        help="Path to the local repository to inspect",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Bug description / task to investigate",
    )
    return parser.parse_args()


def _validate_repo(repo: Path) -> Path:
    resolved = repo.resolve()
    if not resolved.is_dir():
        console.print(f"[red]Repository path does not exist:[/red] {resolved}")
        sys.exit(1)
    return resolved


def _render_output(state: AgentState) -> None:
    """Format final agent state with Rich."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]AI Dev Agent[/bold cyan] — Read + Plan Mode",
            border_style="cyan",
        )
    )

    console.print(Panel(state.task_description, title="Task", border_style="blue"))

    console.print(Panel(state.repo_summary or "(no summary)", title="Repository Summary"))

    planner = state.planner_result
    if isinstance(planner, dict):
        planner = PlannerResult.model_validate(planner)

    if planner:
        console.print(Panel(planner.understanding, title="Issue Understanding", border_style="green"))

        plan_tree = Tree("[bold]Investigation Plan[/bold]")
        for step in planner.plan:
            plan_tree.add(step)
        console.print(plan_tree)

        if planner.files_to_investigate:
            files_table = Table(title="Files to Investigate (Planner)")
            files_table.add_column("Path", style="yellow")
            for f in planner.files_to_investigate:
                files_table.add_row(f)
            console.print(files_table)

    if state.files_read:
        inspected = Table(title="Files Inspected (Researcher)")
        inspected.add_column("Path", style="cyan")
        inspected.add_column("Size (chars)", justify="right")
        for path, content in state.files_read.items():
            inspected.add_row(path, str(len(content)))
        console.print(inspected)

    research = state.research_result
    if isinstance(research, dict):
        research = ResearchResult.model_validate(research)

    if research:
        console.print(
            Panel(
                research.suspected_root_cause,
                title="Root Cause Analysis",
                border_style="red",
            )
        )

        if research.evidence:
            evidence_tree = Tree("[bold]Evidence[/bold]")
            for item in research.evidence:
                evidence_tree.add(item)
            console.print(evidence_tree)

        console.print(
            Panel(
                research.recommended_fix,
                title="Recommended Fix (not applied)",
                border_style="magenta",
            )
        )

    if state.proposed_changes:
        changes_table = Table(title="Proposed Changes (suggestions only)")
        changes_table.add_column("File")
        changes_table.add_column("Description")
        changes_table.add_column("Rationale")
        for change in state.proposed_changes:
            if hasattr(change, "file_path"):
                row = change
            else:
                from models.state import ProposedChange

                row = ProposedChange.model_validate(change)
            changes_table.add_row(row.file_path, row.description[:60], row.rationale[:60])
        console.print(changes_table)

    if state.reasoning:
        console.print(Panel(Markdown(state.reasoning), title="Agent Reasoning"))

    console.print(
        Panel(
            f"[dim]Step:[/dim] {state.current_step}  |  "
            f"[dim]Files in repo:[/dim] {len(state.files_found)}  |  "
            f"[dim]Mode:[/dim] READ + PLAN (no writes)",
            border_style="dim",
        )
    )


def main() -> None:
    args = _parse_args()
    repo = _validate_repo(args.repo)

    settings = get_settings()
    if not settings.has_llm:
        console.print(
            "[red]Missing OPENAI_API_KEY.[/red]\n"
            "Export your key or create ai-dev-agent/.env with:\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  OPENAI_MODEL=gpt-4o-mini  # optional"
        )
        sys.exit(1)

    console.print(f"[bold]Repository:[/bold] {repo}")
    console.print(f"[bold]Task:[/bold] {args.task}")
    console.print("[dim]Running planner → researcher workflow...[/dim]\n")

    try:
        final_state = run_bug_fix_workflow(str(repo), args.task)
    except Exception as exc:
        console.print(f"[red]Workflow failed:[/red] {exc}")
        sys.exit(1)

    _render_output(final_state)
    console.print("\n[green]Done.[/green] No files were modified.\n")


if __name__ == "__main__":
    main()
