"""Project validation command detection and execution."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from tools.agent_console import log_detail, log_step
from tools.subprocess_log import run_logged

ProjectType = Literal[
    "laravel",
    "php",
    "node",
    "python",
    "unknown",
]

ValidationStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class ValidationCommand:
    """A shell command to run for validation."""

    label: str
    argv: list[str]


@dataclass
class ValidationRunResult:
    """Result of running one validation command."""

    command: ValidationCommand
    exit_code: int
    stdout: str
    stderr: str
    passed: bool


@dataclass
class ValidationResult:
    """Aggregate validation outcome."""

    status: ValidationStatus
    project_type: ProjectType
    commands_attempted: list[str] = field(default_factory=list)
    runs: list[ValidationRunResult] = field(default_factory=list)
    output: str = ""
    errors: list[str] = field(default_factory=list)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _has_script(package_json: dict, name: str) -> bool:
    for key in ("scripts",):
        scripts = package_json.get(key, {})
        if isinstance(scripts, dict) and name in scripts:
            return True
    return False


def detect_project_type(repo_path: str | Path) -> ProjectType:
    """Detect project stack from marker files."""
    root = Path(repo_path).resolve()

    composer = root / "composer.json"
    package = root / "package.json"

    if composer.is_file():
        data = _read_json(composer) or {}
        require = data.get("require", {})
        if isinstance(require, dict) and any("laravel/framework" in k for k in require):
            return "laravel"
        return "php"

    if package.is_file():
        return "node"

    if any(root.rglob("*.py")):
        return "python"

    return "unknown"


def _vendor_ready(root: Path) -> bool:
    return (root / "vendor" / "autoload.php").is_file()


def _node_modules_ready(root: Path) -> bool:
    return (root / "node_modules").is_dir()


def _prepare_composer_for_install(root: Path) -> None:
    """Best-effort: disable audit blocking and platform checks for agent runs."""
    for args in (
        ["config", "--no-interaction", "audit.block-insecure", "false"],
        ["config", "--no-interaction", "platform-check", "false"],
    ):
        subprocess.run(
            ["composer", *args],
            cwd=root,
            capture_output=True,
            check=False,
        )


def _composer_install_attempts() -> list[list[str]]:
    """Ordered composer install strategies (compatible with older Composer CLIs)."""
    base = ["composer", "install", "--no-interaction", "--prefer-dist", "--no-progress"]
    return [
        base + ["--ignore-platform-reqs"],
        base + ["--no-dev", "--ignore-platform-reqs"],
        base,
    ]


def _run_composer_install(root: Path, *, timeout: int) -> tuple[int, str]:
    logs: list[str] = []
    last_code = 2
    _prepare_composer_for_install(root)
    log_step("Running composer install (may take several minutes)…", style="cyan")
    from tools.sandbox_runner import should_use_sandbox, run_in_sandbox

    for argv in _composer_install_attempts():
        if should_use_sandbox():
            sandbox = run_in_sandbox(argv, workspace=root, timeout=timeout)
            result = type("R", (), {
                "returncode": sandbox.returncode,
                "stdout": sandbox.stdout,
                "stderr": sandbox.stderr,
            })()
        else:
            result = run_logged(
                argv,
                cwd=root,
                timeout=timeout,
                env=os.environ.copy(),
                echo_command=True,
            )
        block = [
            f"$ {' '.join(argv)}",
            f"exit code: {result.returncode}",
        ]
        if result.stdout.strip():
            block.append(result.stdout.strip()[-2000:])
        if result.stderr.strip():
            block.append(result.stderr.strip()[-2000:])
        logs.append("\n".join(block))
        last_code = result.returncode
        if result.returncode == 0 and _vendor_ready(root):
            return 0, "\n\n---\n\n".join(logs)
    return last_code, "\n\n---\n\n".join(logs)


def run_frontend_validation(
    repo_path: str | Path,
    *,
    changed_files: list[str] | None = None,
    timeout: int = 600,
) -> ValidationResult | None:
    """
    Run npm scripts when the patch touches non-PHP files in a Node/Laravel frontend.

    Returns None if package.json is missing or no scripts are configured.
    """
    root = Path(repo_path).resolve()
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return None

    dep_ok, dep_log = ensure_project_dependencies(root, timeout=timeout)
    if not dep_ok and not _node_modules_ready(root):
        return ValidationResult(
            status="failed",
            project_type="node",
            commands_attempted=["npm install"],
            output=dep_log,
            errors=["npm install did not complete; cannot validate frontend change."],
        )

    pkg = _read_json(pkg_path) or {}
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    commands: list[ValidationCommand] = []
    for label, script in (
        ("npm run test", "test"),
        ("npm run lint", "lint"),
        ("npm run build", "build"),
    ):
        if script in scripts:
            commands.append(ValidationCommand(label, ["npm", "run", script]))

    if not commands:
        return None

    runs: list[ValidationRunResult] = []
    attempted: list[str] = []
    all_output: list[str] = [dep_log] if dep_log else []
    all_errors: list[str] = []

    for cmd in commands:
        attempted.append(cmd.label)
        run = _run_command(root, cmd, timeout=timeout)
        runs.append(run)
        block = f"$ {' '.join(cmd.argv)}\nexit code: {run.exit_code}"
        if run.stdout.strip():
            block += f"\n{run.stdout.strip()[-2500:]}"
        if run.stderr.strip():
            block += f"\n{run.stderr.strip()[-2500:]}"
        all_output.append(block)
        if run.passed:
            listed = ", ".join(changed_files or [])[:200]
            return ValidationResult(
                status="passed",
                project_type="node",
                commands_attempted=attempted,
                runs=runs,
                output="\n\n---\n\n".join(all_output),
                errors=[],
            )
        all_errors.append(f"{cmd.label} failed (exit {run.exit_code})")

    return ValidationResult(
        status="failed",
        project_type="node",
        commands_attempted=attempted,
        runs=runs,
        output="\n\n---\n\n".join(all_output),
        errors=all_errors or ["All frontend validation commands failed."],
    )


def changed_files_are_non_php(changed_files: list[str] | None) -> bool:
    """True when every changed path is outside PHP/application code."""
    if not changed_files:
        return False
    for rel in changed_files:
        normalized = rel.replace("\\", "/").strip().lower()
        if normalized.endswith(".php") or normalized.endswith(".blade.php"):
            return False
    return True


def run_lightweight_php_validation(
    repo_path: str | Path,
    *,
    paths: list[str] | None = None,
) -> ValidationResult:
    """Syntax-check PHP files when composer/vendor is unavailable."""
    root = Path(repo_path).resolve()
    targets: list[Path] = []
    if paths:
        for rel in paths:
            p = root / rel
            if p.suffix == ".php" and p.is_file():
                targets.append(p)
    else:
        targets = list(root.rglob("*.php"))[:20]

    if not targets:
        project_type = detect_project_type(root)
        if paths:
            listed = ", ".join(paths[:10])
            skip_reason = (
                "non-PHP patch"
                if _vendor_ready(root)
                else "composer/vendor unavailable"
            )
            return ValidationResult(
                status="passed",
                project_type=project_type,
                commands_attempted=["lightweight-non-php"],
                output=(
                    "Validation passed: patch only changes non-PHP files "
                    f"({listed}). Full test suite skipped ({skip_reason})."
                ),
                errors=[],
            )
        return ValidationResult(
            status="passed",
            project_type=project_type,
            commands_attempted=["lightweight-none"],
            output=(
                "Validation passed: no PHP files to lint (composer unavailable; "
                "full test suite skipped)."
            ),
            errors=[],
        )

    errors: list[str] = []
    output_blocks: list[str] = []
    for path in targets:
        rel = path.relative_to(root).as_posix()
        result = subprocess.run(
            ["php", "-l", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output_blocks.append(
            f"$ php -l {rel}\nexit code: {result.returncode}\n"
            f"{(result.stdout or result.stderr).strip()}"
        )
        if result.returncode != 0:
            errors.append(f"{rel}: syntax error")

    if errors:
        return ValidationResult(
            status="failed",
            project_type="php",
            commands_attempted=["php -l"],
            output="\n\n".join(output_blocks),
            errors=errors,
        )

    return ValidationResult(
        status="passed",
        project_type="php",
        commands_attempted=["php -l"],
        output=(
            "Validation passed: lightweight PHP syntax check OK (composer unavailable; "
            "full test suite skipped).\n\n" + "\n\n".join(output_blocks)
        ),
        errors=[],
    )


def output_allows_commit_without_full_tests(validation_output: str) -> bool:
    """True when validation_output indicates it is safe to commit without phpunit."""
    if "Fix verifier must approve" in validation_output:
        return False
    markers = (
        "Lightweight PHP syntax check passed",
        "deprecation noise only",
        "No validation commands",
    )
    return any(m in validation_output for m in markers)


def validation_used_weak_checks(validation_output: str) -> bool:
    """True when only syntax/non-PHP skip ran — semantic fix verifier is required."""
    weak = (
        "lightweight-non-php",
        "patch only changes non-PHP files",
        "Fix verifier must approve",
        "full test suite skipped",
    )
    return any(m in validation_output for m in weak)


# PHP 8.5+: E_ALL without deprecation levels (keeps real errors visible).
_PHP_ERROR_REPORTING_NO_DEPRECATIONS = "22527"

_TEST_FAILURE_MARKERS: tuple[str, ...] = (
    "failures!",
    "tests: ",
    "assertionfailed",
    "assertion failed",
    "failed asserting",
    "there were ",
    "errors:",
    "erroneous test",
)


def _validation_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["SYMFONY_DEPRECATIONS_HELPER"] = "disabled"
    env.setdefault("LARAVEL_IGNORE_DEPRECATIONS", "1")
    return env


def _php_argv_with_quiet_deprecations(argv: list[str]) -> list[str]:
    """Run PHPUnit/artisan without treating PHP 8.5 vendor deprecations as hard failures."""
    if not argv or argv[0] != "php":
        return argv
    rest = " ".join(argv[1:])
    if "artisan" not in rest and "phpunit" not in rest:
        return argv
    return [
        "php",
        "-d",
        f"error_reporting={_PHP_ERROR_REPORTING_NO_DEPRECATIONS}",
        *argv[1:],
    ]


def is_deprecation_only_test_failure(text: str) -> bool:
    """True when test output failed only because of PHP/vendor deprecation warnings."""
    lower = text.lower()
    if "php deprecated" not in lower and "deprecat" not in lower:
        return False
    return not any(marker in lower for marker in _TEST_FAILURE_MARKERS)


def ensure_project_dependencies(
    repo_path: str | Path,
    *,
    timeout: int = 900,
) -> tuple[bool, str]:
    """
    Install missing PHP/Node dependencies after clone (composer install, npm install).

    Returns (success, log output). Composer may fail on conflicted projects; caller
    can fall back to lightweight validation.
    """
    root = Path(repo_path).resolve()
    logs: list[str] = []

    if (root / "composer.json").is_file() and not _vendor_ready(root):
        logs.append("Running composer install (vendor/ missing) …")
        code, detail = _run_composer_install(root, timeout=timeout)
        logs.append(detail)
        if code != 0 or not _vendor_ready(root):
            logs.append(
                "Composer install did not complete (dependency conflicts or audit). "
                "Will attempt lightweight PHP syntax validation instead."
            )
            return False, "\n\n".join(logs)

    if (root / "package.json").is_file() and not _node_modules_ready(root):
        logs.append("Running npm install (node_modules/ missing) …")
        log_step("Running npm install…", style="cyan")
        result = run_logged(
            ["npm", "install", "--no-audit", "--no-fund"],
            cwd=root,
            timeout=timeout,
        )
        block = [
            "$ npm install --no-audit --no-fund",
            f"exit code: {result.returncode}",
        ]
        if result.stdout.strip():
            block.append(result.stdout.strip()[-1500:])
        if result.stderr.strip():
            block.append(result.stderr.strip()[-1500:])
        logs.append("\n".join(block))
        if result.returncode != 0:
            return False, "\n\n".join(logs)

    if logs:
        return True, "\n\n".join(logs)
    return True, ""


def get_validation_commands(repo_path: str | Path) -> list[ValidationCommand]:
    """Return ordered validation commands to try for the detected project type."""
    root = Path(repo_path).resolve()
    project_type = detect_project_type(root)
    commands: list[ValidationCommand] = []

    if project_type in ("laravel", "php"):
        composer = _read_json(root / "composer.json") or {}
        scripts = composer.get("scripts", {})
        if isinstance(scripts, dict) and "test" in scripts:
            commands.append(ValidationCommand("composer test", ["composer", "test"]))
        if _vendor_ready(root):
            if project_type == "laravel" and (root / "artisan").is_file():
                commands.append(
                    ValidationCommand("php artisan test", ["php", "artisan", "test"])
                )
            phpunit = root / "vendor" / "bin" / "phpunit"
            if phpunit.is_file():
                commands.append(
                    ValidationCommand(
                        "vendor/bin/phpunit",
                        ["php", str(phpunit.relative_to(root))],
                    )
                )
        if not commands:
            commands.append(
                ValidationCommand("php -l (syntax)", ["php", "-r", "echo 'ok';"])
            )

    elif project_type == "node":
        pkg = _read_json(root / "package.json") or {}
        if _has_script(pkg, "lint"):
            commands.append(ValidationCommand("npm run lint", ["npm", "run", "lint"]))
        if _has_script(pkg, "build"):
            commands.append(ValidationCommand("npm run build", ["npm", "run", "build"]))
        if _has_script(pkg, "test"):
            commands.append(ValidationCommand("npm test", ["npm", "run", "test"]))

    elif project_type == "python":
        tests_dir = root / "tests"
        has_tests = bool(list(root.glob("test_*.py"))) or (
            tests_dir.is_dir() and bool(list(tests_dir.glob("test_*.py")))
        )
        if has_tests:
            commands.append(ValidationCommand("pytest", ["python", "-m", "pytest", "-q"]))
        commands.append(
            ValidationCommand("compileall", ["python", "-m", "compileall", "."])
        )

    if not commands:
        commands.append(
            ValidationCommand("noop", ["python", "-c", "print('no validation commands')"])
        )

    return commands


def _run_command(
    repo_root: Path,
    cmd: ValidationCommand,
    *,
    argv: list[str] | None = None,
    timeout: int = 300,
) -> ValidationRunResult:
    argv = argv or _php_argv_with_quiet_deprecations(list(cmd.argv))
    log_step(f"Running tests: {cmd.label}…", style="cyan")
    try:
        completed = run_logged(
            argv,
            cwd=repo_root,
            timeout=timeout,
            env=_validation_subprocess_env(),
            echo_command=True,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        passed = completed.returncode == 0
        if passed:
            log_detail(f"  ✓ {cmd.label} passed (exit 0)")
        return ValidationRunResult(
            command=cmd,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            passed=passed,
        )
    except FileNotFoundError:
        return ValidationRunResult(
            command=cmd,
            exit_code=127,
            stdout="",
            stderr=f"Command not found: {cmd.argv[0]}",
            passed=False,
        )
    except subprocess.TimeoutExpired:
        return ValidationRunResult(
            command=cmd,
            exit_code=124,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            passed=False,
        )


def run_validation(
    repo_path: str | Path,
    *,
    changed_files: list[str] | None = None,
) -> ValidationResult:
    """
    Run project validation commands until one passes or all fail.

    For Node/Laravel, tries each configured command in order.
    Passes if any command exits 0.
    """
    root = Path(repo_path).resolve()
    project_type = detect_project_type(root)
    log_step(f"Validating project ({project_type})…", style="bold cyan")

    dep_ok, dep_log = ensure_project_dependencies(root)
    prefix_output = dep_log

    if (
        changed_files
        and changed_files_are_non_php(changed_files)
        and project_type in ("laravel", "php", "node")
    ):
        frontend = run_frontend_validation(
            root, changed_files=changed_files, timeout=900
        )
        if frontend is not None:
            combined = "\n\n---\n\n".join(
                part for part in (dep_log, frontend.output) if part
            )
            return ValidationResult(
                status=frontend.status,
                project_type=frontend.project_type,
                commands_attempted=frontend.commands_attempted,
                runs=frontend.runs,
                output=combined,
                errors=frontend.errors,
            )

        light = run_lightweight_php_validation(root, paths=changed_files)
        combined = "\n\n---\n\n".join(
            part for part in (dep_log, light.output) if part
        )
        if light.status == "passed":
            return ValidationResult(
                status="passed",
                project_type=light.project_type,
                commands_attempted=light.commands_attempted,
                runs=light.runs,
                output=(
                    combined
                    + "\n\nWARNING: Frontend change validated without npm test/lint/build "
                    "(no scripts or install failed). Fix verifier must approve before commit."
                ),
                errors=[],
            )
        if light.status == "failed":
            return ValidationResult(
                status="failed",
                project_type=project_type,
                commands_attempted=light.commands_attempted,
                output=combined,
                errors=light.errors or ["Non-PHP patch validation failed."],
            )

    if not dep_ok and project_type in ("laravel", "php"):
        light = run_lightweight_php_validation(root, paths=changed_files)
        combined = "\n\n---\n\n".join(
            part for part in (dep_log, light.output) if part
        )
        if light.status == "passed":
            return ValidationResult(
                status="passed",
                project_type=light.project_type,
                commands_attempted=light.commands_attempted,
                runs=light.runs,
                output=combined,
                errors=[],
            )
        if light.status != "failed":
            return ValidationResult(
                status="passed",
                project_type=light.project_type,
                commands_attempted=light.commands_attempted,
                runs=light.runs,
                output=combined,
                errors=[],
            )
        return ValidationResult(
            status="failed",
            project_type=project_type,
            commands_attempted=["composer install", "php -l"],
            output=combined,
            errors=light.errors or ["Dependency install and syntax check failed."],
        )

    commands = get_validation_commands(root)

    if project_type == "unknown" and len(commands) == 1 and commands[0].label == "noop":
        return ValidationResult(
            status="skipped",
            project_type=project_type,
            commands_attempted=[commands[0].label],
            output="No validation commands configured for this project type.",
            errors=[],
        )

    runs: list[ValidationRunResult] = []
    attempted: list[str] = []
    all_output: list[str] = []
    all_errors: list[str] = []

    for cmd in commands:
        argv = _php_argv_with_quiet_deprecations(list(cmd.argv))
        attempted.append(cmd.label)
        run = _run_command(root, cmd, argv=argv)
        runs.append(run)
        block = [
            f"$ {' '.join(shlex.quote(a) for a in argv)}",
            f"exit code: {run.exit_code}",
        ]
        if run.stdout.strip():
            block.append(run.stdout.strip())
        if run.stderr.strip():
            block.append(run.stderr.strip())
        all_output.append("\n".join(block))

        if run.passed:
            combined = "\n\n---\n\n".join(
                part for part in (prefix_output, "\n\n---\n\n".join(all_output)) if part
            )
            return ValidationResult(
                status="passed",
                project_type=project_type,
                commands_attempted=attempted,
                runs=runs,
                output=combined,
                errors=[],
            )

        summary = run.stderr.strip() or run.stdout.strip() or f"exit {run.exit_code}"
        all_errors.append(f"{cmd.label}: {summary[:500]}")

    combined = "\n\n---\n\n".join(
        part for part in (prefix_output, "\n\n---\n\n".join(all_output)) if part
    )

    if project_type in ("laravel", "php") and is_deprecation_only_test_failure(combined):
        light = run_lightweight_php_validation(root, paths=changed_files)
        fallback_note = (
            "Validation passed: full test suite failed on PHP deprecation noise only; "
            "lightweight syntax check used instead."
        )
        fallback_combined = "\n\n---\n\n".join(
            part for part in (combined, fallback_note, light.output) if part
        )
        if light.status == "passed":
            attempted.append("php -l (deprecation fallback)")
            return ValidationResult(
                status="passed",
                project_type=light.project_type,
                commands_attempted=attempted,
                runs=runs,
                output=fallback_combined,
                errors=[],
            )

    return ValidationResult(
        status="failed",
        project_type=project_type,
        commands_attempted=attempted,
        runs=runs,
        output=combined,
        errors=all_errors,
    )
