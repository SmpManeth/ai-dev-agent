"""Run shell commands with live terminal output (streamed line-by-line)."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.agent_console import console, log_detail
from tools.audit_log import audit_command
from tools.command_guard import assert_command_allowed
from tools.security_policy import SecurityViolation
from tools.secret_mask import mask_secrets
from tools.security_policy import max_runtime_seconds


@dataclass(frozen=True)
class LoggedProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def stream_logs_enabled() -> bool:
    """Live subprocess logs on by default; set AGENT_STREAM_LOGS=0 to disable."""
    return os.environ.get("AGENT_STREAM_LOGS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _format_argv(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(a)) for a in argv)


def _print_stream_line(line: str, *, prefix: str = "    │ ") -> None:
    text = mask_secrets(line.rstrip("\n\r"))
    if not text:
        return
    if len(text) > 240:
        text = text[:237] + "…"
    console.print(f"{prefix}{text}", style="dim", highlight=False)


def run_logged(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    stream: bool | None = None,
    echo_command: bool = True,
    task_key: str = "",
    skip_command_guard: bool = False,
) -> LoggedProcessResult:
    """
    Run a command; optionally stream merged stdout/stderr to the terminal.

    Full output is still captured and returned for validation records.
    """
    argv_list = [str(a) for a in argv]
    if not skip_command_guard:
        try:
            assert_command_allowed(argv_list)
            audit_command(argv_list, task_key=task_key, allowed=True)
        except SecurityViolation as exc:
            audit_command(argv_list, task_key=task_key, allowed=False)
            raise

    if timeout is None:
        timeout = max_runtime_seconds()

    if echo_command:
        log_detail(f"  $ {_format_argv(argv_list)}")

    use_stream = stream if stream is not None else stream_logs_enabled()
    if not use_stream:
        completed = subprocess.run(
            argv_list,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        out = mask_secrets(completed.stdout or "")
        err = mask_secrets(completed.stderr or "")
        if completed.returncode != 0 and (out or err):
            _print_failure_tail(out, err)
        return LoggedProcessResult(
            argv=argv_list,
            returncode=completed.returncode,
            stdout=out,
            stderr=err,
        )

    deadline = time.monotonic() + timeout if timeout else None
    proc = subprocess.Popen(
        argv_list,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    lines: list[str] = []
    assert proc.stdout is not None

    while True:
        if deadline and time.monotonic() > deadline:
            proc.kill()
            proc.wait(timeout=5)
            msg = f"Command timed out after {timeout}s"
            _print_stream_line(msg, prefix="    │ ")
            return LoggedProcessResult(
                argv=argv_list,
                returncode=124,
                stdout="\n".join(lines),
                stderr=msg,
            )

        line = proc.stdout.readline()
        if line == "" and proc.poll() is not None:
            break
        if line:
            lines.append(line.rstrip("\n\r"))
            _print_stream_line(line)

    code = proc.wait()
    combined = mask_secrets("\n".join(lines))
    if code != 0:
        _print_failure_tail(combined, "")

    return LoggedProcessResult(
        argv=argv_list,
        returncode=code,
        stdout=combined,
        stderr="",
    )


def _print_failure_tail(stdout: str, stderr: str, *, max_lines: int = 12) -> None:
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    if not combined:
        return
    tail = combined.splitlines()[-max_lines:]
    log_detail("  ✗ last output:")
    for line in tail:
        _print_stream_line(line, prefix="    │ ")
