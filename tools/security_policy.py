"""Production hardening policy loader and enforcement."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


class SecurityViolation(Exception):
    """Raised when an operation violates production hardening rules."""


@dataclass(frozen=True)
class HardeningPolicy:
    agent_enabled: bool = True
    sandbox_enabled: bool = False
    sandbox_image: str = "ai-dev-agent-sandbox:latest"
    sandbox_network: str = "none"
    require_approval_before_pr: bool = False
    max_retries: int = 3
    max_runtime_minutes: int = 120
    max_tokens_per_task: int = 500_000
    risk_threshold: str = "medium"
    allowed_repositories: tuple[str, ...] = ()
    blocked_file_patterns: tuple[str, ...] = ()
    blocked_command_patterns: tuple[re.Pattern[str], ...] = ()
    allowed_command_prefixes: tuple[str, ...] = ()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_policy_path() -> Path:
    return _project_root() / "hardening.defaults.json"


def _resolve_policy_path() -> Path:
    explicit = (os.environ.get("AI_AGENT_HARDENING_CONFIG") or "").strip()
    if explicit:
        return Path(explicit)
    dashboard = _project_root() / "dashboard" / "storage" / "app" / "ai-agent-hardening.json"
    if dashboard.is_file():
        return dashboard
    return _default_policy_path()


def _compile_patterns(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            compiled.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            compiled.append(re.compile(re.escape(raw), re.IGNORECASE))
    return tuple(compiled)


def load_policy_from_dict(data: dict[str, Any]) -> HardeningPolicy:
    blocked_files = data.get("blocked_file_patterns") or []
    blocked_cmds = data.get("blocked_command_patterns") or []
    allowed_cmds = data.get("allowed_command_prefixes") or []
    allowed_repos = data.get("allowed_repositories") or []
    return HardeningPolicy(
        agent_enabled=bool(data.get("agent_enabled", True)),
        sandbox_enabled=bool(data.get("sandbox_enabled", False)),
        sandbox_image=str(data.get("sandbox_image") or "ai-dev-agent-sandbox:latest"),
        sandbox_network=str(data.get("sandbox_network") or "none"),
        require_approval_before_pr=bool(data.get("require_approval_before_pr", False)),
        max_retries=max(0, min(10, int(data.get("max_retries", 3)))),
        max_runtime_minutes=max(5, min(480, int(data.get("max_runtime_minutes", 120)))),
        max_tokens_per_task=max(10_000, int(data.get("max_tokens_per_task", 500_000))),
        risk_threshold=str(data.get("risk_threshold") or "medium").lower(),
        allowed_repositories=tuple(str(r) for r in allowed_repos if str(r).strip()),
        blocked_file_patterns=tuple(str(p) for p in blocked_files),
        blocked_command_patterns=_compile_patterns(
            [str(p) for p in blocked_cmds],
        ),
        allowed_command_prefixes=tuple(str(p) for p in allowed_cmds),
    )


@lru_cache
def get_hardening_policy() -> HardeningPolicy:
    path = _resolve_policy_path()
    if not path.is_file():
        return load_policy_from_dict({})
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return load_policy_from_dict({})
    return load_policy_from_dict(data)


def reload_hardening_policy() -> HardeningPolicy:
    get_hardening_policy.cache_clear()
    return get_hardening_policy()


def assert_agent_enabled() -> None:
    if not get_hardening_policy().agent_enabled:
        raise SecurityViolation(
            "Agent is disabled (kill switch). Enable it in the control plane settings."
        )


def normalize_repo_slug(owner: str, repo: str) -> str:
    return f"{owner.strip().lower()}/{repo.strip().lower()}"


def assert_repo_allowed(owner: str, repo: str) -> None:
    policy = get_hardening_policy()
    allowed = policy.allowed_repositories
    if not allowed:
        return
    slug = normalize_repo_slug(owner, repo)
    if slug not in {a.lower() for a in allowed}:
        raise SecurityViolation(
            f"Repository {slug} is not in the allowed repository whitelist."
        )


def assert_repo_path_allowed(repo_path: str | Path) -> None:
    policy = get_hardening_policy()
    allowed = policy.allowed_repositories
    if not allowed:
        return
    path = Path(repo_path).resolve()
    parts = path.parts
    for i, part in enumerate(parts):
        if i + 1 < len(parts) and part.lower() not in ("workspaces", "workspace"):
            continue
        if i + 2 < len(parts):
            slug = normalize_repo_slug(parts[i + 1], parts[i + 2])
            if slug in {a.lower() for a in allowed}:
                return
    raise SecurityViolation(
        f"Workspace path {path} does not match allowed repositories: {', '.join(allowed)}"
    )


def is_path_blocked_by_policy(path: str) -> bool:
    normalized = path.replace("\\", "/").strip().lower()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    policy = get_hardening_policy()
    for pattern in policy.blocked_file_patterns:
        p = pattern.lower()
        if p in normalized:
            return True
        if normalized == p or normalized.endswith("/" + p):
            return True
    return False


def max_retries_for_workflow() -> int:
    return get_hardening_policy().max_retries


def max_runtime_seconds() -> int:
    return get_hardening_policy().max_runtime_minutes * 60


def risk_threshold_level() -> str:
    return get_hardening_policy().risk_threshold
