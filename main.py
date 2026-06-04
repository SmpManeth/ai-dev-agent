#!/usr/bin/env python3
"""CLI entrypoint for the local bug-fix coding agent (read + plan mode)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from config import get_settings
from report import format_step1_report
from workflows.bug_fix_graph import run_bug_fix_workflow

console = Console()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local AI coding agent — Step 1 bug investigation (read + plan only)",
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

    console.print(f"Repository: {repo}", highlight=False)
    console.print(f"Task: {args.task}", highlight=False)
    console.print("Running Step 1 (read + plan only)...\n", style="dim")

    try:
        final_state = run_bug_fix_workflow(str(repo), args.task)
    except Exception as exc:
        console.print(f"[red]Workflow failed:[/red] {exc}")
        sys.exit(1)

    console.print(format_step1_report(final_state), highlight=False)
    console.print()


if __name__ == "__main__":
    main()
