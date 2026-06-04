"""Token and estimated cost tracking per task."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.audit_log import append_audit_event
from tools.security_policy import SecurityViolation, get_hardening_policy

# Rough USD per 1M tokens (override via env); used for estimates only.
_DEFAULT_COST_PER_1M: dict[str, float] = {
    "gpt-4o": 5.0,
    "gpt-4o-mini": 0.3,
    "gpt-5.3-codex": 8.0,
    "default": 5.0,
}


@dataclass
class CostRecord:
    task_key: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_usd: float = 0.0
    model: str = ""
    calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_key": self.task_key,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_usd": round(self.estimated_usd, 4),
            "model": self.model,
            "calls": self.calls,
        }


def _cost_path(task_key: str) -> Path:
    root = Path(__file__).resolve().parent.parent / "outputs" / "cost"
    root.mkdir(parents=True, exist_ok=True)
    safe = (task_key or "unknown").replace("/", "_")
    return root / f"{safe}.json"


def load_cost(task_key: str) -> CostRecord:
    path = _cost_path(task_key)
    if not path.is_file():
        return CostRecord(task_key=task_key)
    data = json.loads(path.read_text(encoding="utf-8"))
    return CostRecord(
        task_key=task_key,
        prompt_tokens=int(data.get("prompt_tokens", 0)),
        completion_tokens=int(data.get("completion_tokens", 0)),
        total_tokens=int(data.get("total_tokens", 0)),
        estimated_usd=float(data.get("estimated_usd", 0)),
        model=str(data.get("model", "")),
        calls=int(data.get("calls", 0)),
    )


def save_cost(record: CostRecord) -> None:
    _cost_path(record.task_key).write_text(
        json.dumps(record.to_dict(), indent=2),
        encoding="utf-8",
    )


def _estimate_usd(model: str, total_tokens: int) -> float:
    rate = _DEFAULT_COST_PER_1M.get("default", 5.0)
    for key, price in _DEFAULT_COST_PER_1M.items():
        if key in model.lower():
            rate = price
            break
    return (total_tokens / 1_000_000) * rate


def record_usage(
    task_key: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    model: str = "",
) -> CostRecord:
    policy = get_hardening_policy()
    record = load_cost(task_key)
    record.prompt_tokens += max(0, prompt_tokens)
    record.completion_tokens += max(0, completion_tokens)
    record.total_tokens = record.prompt_tokens + record.completion_tokens
    record.calls += 1
    if model:
        record.model = model
    record.estimated_usd = _estimate_usd(record.model, record.total_tokens)

    if record.total_tokens > policy.max_tokens_per_task:
        append_audit_event(
            "token_limit_exceeded",
            task_key=task_key,
            level="error",
            detail=f"Total tokens {record.total_tokens} exceeds max {policy.max_tokens_per_task}",
        )
        raise SecurityViolation(
            f"Token budget exceeded for task ({record.total_tokens} > {policy.max_tokens_per_task})"
        )

    save_cost(record)
    append_audit_event(
        "token_usage",
        task_key=task_key,
        detail=f"+{prompt_tokens}p +{completion_tokens}c → {record.total_tokens} total",
        context=record.to_dict(),
    )
    return record
