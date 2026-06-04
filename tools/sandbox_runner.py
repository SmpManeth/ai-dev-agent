"""Run subprocess commands inside an isolated Docker container."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.audit_log import append_audit_event
from tools.command_guard import assert_command_allowed
from tools.security_policy import SecurityViolation, get_hardening_policy
from tools.subprocess_log import LoggedProcessResult, run_logged


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    used_sandbox: bool


def docker_available() -> bool:
    return shutil.which("docker") is not None


def should_use_sandbox() -> bool:
    policy = get_hardening_policy()
    if not policy.sandbox_enabled:
        return False
    env = os.environ.get("AI_AGENT_USE_SANDBOX", "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    if env in ("1", "true", "yes", "on"):
        return docker_available()
    return policy.sandbox_enabled and docker_available()


def run_in_sandbox(
    argv: list[str],
    *,
    workspace: str | Path,
    timeout: int | None = None,
    task_key: str = "",
    cwd_relative: str = ".",
) -> SandboxResult:
    """
    Execute argv inside Docker with only the workspace mounted read-write at /workspace.

    Falls back to host run_logged when sandbox is disabled or Docker is unavailable.
    """
    assert_command_allowed(argv, label="sandbox command")
    workspace = Path(workspace).resolve()
    policy = get_hardening_policy()
    effective_timeout = timeout or policy.max_runtime_minutes * 60

    if not should_use_sandbox():
        result = run_logged(
            argv,
            cwd=workspace / cwd_relative if cwd_relative != "." else workspace,
            timeout=effective_timeout,
        )
        return SandboxResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            used_sandbox=False,
        )

    if not docker_available():
        raise SecurityViolation("Sandbox enabled but docker CLI is not available.")

    inner_cwd = "/workspace" if cwd_relative in (".", "") else f"/workspace/{cwd_relative}"
    inner_cmd = " ".join(_shell_quote(str(a)) for a in argv)
    network = policy.sandbox_network or "none"

    docker_argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        network,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{workspace}:/workspace",
        "-w",
        inner_cwd,
        policy.sandbox_image,
        "sh",
        "-c",
        inner_cmd,
    ]

    append_audit_event(
        "sandbox_exec",
        task_key=task_key,
        detail=inner_cmd[:500],
        context={"image": policy.sandbox_image, "network": network},
    )

    try:
        completed = subprocess.run(
            docker_argv,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        append_audit_event(
            "sandbox_timeout",
            task_key=task_key,
            level="error",
            detail=f"Exceeded {effective_timeout}s",
        )
        raise SecurityViolation(f"Sandbox command timed out after {effective_timeout}s")

    return SandboxResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        used_sandbox=True,
    )


def cleanup_sandbox_containers(prefix: str = "ai-agent-sandbox") -> None:
    """Best-effort remove leftover containers (name filter)."""
    if not docker_available():
        return
    subprocess.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"name={prefix}",
            "-f",
            "status=exited",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _shell_quote(value: str) -> str:
    if not value:
        return "''"
    if all(c.isalnum() or c in "-_./:" for c in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"
