#!/usr/bin/env python3
"""CLI: clone or pull the configured GitHub repo. Prints repo path on stdout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.repo_sync import ensure_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GitHub repo for the AI agent")
    parser.add_argument(
        "--repo",
        default="",
        help="Optional local path; default is workspace from GITHUB_OWNER/REPO",
    )
    args = parser.parse_args()

    print("AI Agent — repository sync", file=sys.stderr, flush=True)

    try:
        result = ensure_repository(args.repo or None)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(f"Done: {result.message}", file=sys.stderr, flush=True)
    print(result.path, flush=True)


if __name__ == "__main__":
    main()
