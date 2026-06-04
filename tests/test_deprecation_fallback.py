"""PHP 8.5 deprecation noise should not block agent commits."""

from __future__ import annotations

from pathlib import Path

from tools.test_tool import (
    ValidationCommand,
    ValidationRunResult,
    run_validation,
    is_deprecation_only_test_failure,
)


def test_detects_deprecation_noise_without_real_failures() -> None:
    text = """
    exit code: 2
    PHP Deprecated: Method ReflectionMethod::setAccessible() is deprecated since 8.5
    """
    assert is_deprecation_only_test_failure(text) is True


def test_rejects_deprecation_noise_when_tests_failed() -> None:
    text = """
    PHP Deprecated: something
    FAILURES!
    Tests: 1, Assertions: 0, Failures: 1.
    Failed asserting that true is false.
    """
    assert is_deprecation_only_test_failure(text) is False


def test_run_validation_fallback_after_artisan_deprecation_exit(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^10.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "autoload.php").write_text("", encoding="utf-8")
    php_file = tmp_path / "app" / "Example.php"
    php_file.parent.mkdir(parents=True)
    php_file.write_text("<?php\n// ok\n", encoding="utf-8")

    monkeypatch.setattr(
        "tools.test_tool.ensure_project_dependencies",
        lambda *a, **k: (True, ""),
    )

    def fake_run(repo_root, cmd, *, argv=None, timeout=300):
        _ = repo_root, argv, timeout
        if "artisan" in " ".join(cmd.argv):
            return ValidationRunResult(
                command=cmd,
                exit_code=2,
                stdout="",
                stderr="PHP Deprecated: Method ReflectionMethod::setAccessible() is deprecated",
                passed=False,
            )
        return ValidationRunResult(
            command=cmd,
            exit_code=0,
            stdout="ok",
            stderr="",
            passed=True,
        )

    monkeypatch.setattr("tools.test_tool._run_command", fake_run)
    monkeypatch.setattr(
        "tools.test_tool.get_validation_commands",
        lambda _root: [
            ValidationCommand("php artisan test", ["php", "artisan", "test"]),
        ],
    )

    result = run_validation(tmp_path, changed_files=["app/Example.php"])
    assert result.status == "passed"
    assert "deprecation noise only" in result.output
