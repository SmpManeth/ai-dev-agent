"""Write proposed patch artifacts to the agent outputs directory."""

from __future__ import annotations

from pathlib import Path

from config import get_outputs_dir


def get_patch_paths() -> tuple[Path, Path]:
    """Return (patch file, summary file) paths under outputs/."""
    root = get_outputs_dir()
    return root / "latest.patch", root / "latest_summary.md"


def write_patch_artifacts(
    *,
    unified_diff: str,
    patch_summary: str,
    task_description: str,
    root_cause: str,
    recommended_fix: str,
    affected_files: list[str],
    risk_level: str,
    proposed_changes: str,
    confidence: int,
    skipped: bool,
    skip_reason: str = "",
) -> tuple[Path, Path]:
    """
    Persist latest.patch and latest_summary.md.

    Returns absolute paths to both files.
    """
    patch_path, summary_path = get_patch_paths()
    patch_path.parent.mkdir(parents=True, exist_ok=True)

    patch_body = unified_diff if unified_diff.strip() else "# No patch generated\n"
    patch_path.write_text(patch_body, encoding="utf-8")

    status = "SKIPPED" if skipped else ("GENERATED" if unified_diff.strip() else "EMPTY")
    files_list = "\n".join(f"- `{f}`" for f in affected_files) or "- (none)"

    summary_md = f"""# Patch Proposal Summary

## Status
{status}

## Task
{task_description}

## Root Cause
{root_cause}

## Recommended Fix
{recommended_fix}

## Proposed Changes
{proposed_changes or "(none)"}

## Affected Files
{files_list}

## Risk Level
{risk_level}

## Research Confidence
{confidence}%

## Patch Summary
{patch_summary}

"""
    if skip_reason:
        summary_md += f"""## Skip Reason
{skip_reason}

"""
    summary_md += f"""## Patch File
`{patch_path}`

## Unified Diff
```
{unified_diff or "(empty)"}
```
"""
    summary_path.write_text(summary_md, encoding="utf-8")
    return patch_path.resolve(), summary_path.resolve()
