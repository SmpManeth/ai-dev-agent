"""Extract token usage from LangChain structured outputs."""

from __future__ import annotations

from typing import Any

from tools.cost_tracker import record_usage


def track_from_response(
    response: Any,
    *,
    task_key: str = "",
    model: str = "",
) -> None:
    """Best-effort token accounting from LLM response metadata."""
    if not task_key:
        return
    prompt = 0
    completion = 0
    meta = getattr(response, "response_metadata", None) or {}
    if isinstance(meta, dict):
        usage = meta.get("token_usage") or meta.get("usage") or {}
        if isinstance(usage, dict):
            prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            completion = int(
                usage.get("completion_tokens") or usage.get("output_tokens") or 0
            )
    if prompt or completion:
        record_usage(
            task_key,
            prompt_tokens=prompt,
            completion_tokens=completion,
            model=model,
        )
