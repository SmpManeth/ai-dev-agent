"""Append-only security audit log (JSONL) per task / global."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.secret_mask import mask_context, mask_secrets


def _audit_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    path = root / "outputs" / "audit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_audit_event(
    event: str,
    *,
    task_key: str = "",
    level: str = "info",
    detail: str = "",
    context: dict[str, Any] | None = None,
) -> Path:
    """
    Write one audit line to outputs/audit/events.jsonl and optional per-task file.
    """
    record = {
        "at": _now_iso(),
        "event": event,
        "level": level,
        "task_key": task_key,
        "detail": mask_secrets(detail),
        "context": mask_context(context or {}),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"

    global_path = _audit_dir() / "events.jsonl"
    with global_path.open("a", encoding="utf-8") as handle:
        handle.write(line)

    if task_key:
        safe = task_key.replace("/", "_")
        task_path = _audit_dir() / f"task-{safe}.jsonl"
        with task_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    return global_path


def audit_security_check(passed: bool, detail: str, task_key: str = "") -> None:
    append_audit_event(
        "security_check",
        task_key=task_key,
        level="info" if passed else "warning",
        detail=detail,
    )


def audit_command(argv: list[str], task_key: str = "", allowed: bool = True) -> None:
    from tools.secret_mask import mask_command

    append_audit_event(
        "subprocess",
        task_key=task_key,
        level="info" if allowed else "error",
        detail=" ".join(mask_command(argv)),
        context={"allowed": allowed},
    )
