"""Shared terminal progress lines for long-running agent steps."""

from __future__ import annotations

import sys

from rich.console import Console

# Unbuffered-friendly console so long-running steps show lines immediately.
console = Console(stderr=False, force_terminal=True)


def log_step(message: str, *, style: str = "bold cyan") -> None:
    """Print a single progress line (flushed immediately)."""
    console.print(message, style=style, highlight=False)
    sys.stdout.flush()


def log_detail(message: str) -> None:
    console.print(message, style="dim", highlight=False)
    sys.stdout.flush()
