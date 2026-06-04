"""Lightweight validation when composer is broken."""

from __future__ import annotations

from pathlib import Path

from tools.test_tool import run_lightweight_php_validation, run_validation


def test_readme_only_patch_passes_without_composer(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^10.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
    result = run_lightweight_php_validation(tmp_path, paths=["README.md"])
    assert result.status == "passed"
    assert "non-PHP" in result.output


def test_run_validation_passes_when_composer_fails_readme_patch(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^10.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")

    monkeypatch.setattr(
        "tools.test_tool.ensure_project_dependencies",
        lambda *a, **k: (False, "composer failed"),
    )

    result = run_validation(tmp_path, changed_files=["README.md"])
    assert result.status == "passed"


def test_run_validation_skips_artisan_for_readme_when_vendor_ready(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^10.0"},"scripts":{"test":["@php artisan test"]}}',
        encoding="utf-8",
    )
    (tmp_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "autoload.php").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")

    monkeypatch.setattr(
        "tools.test_tool.ensure_project_dependencies",
        lambda *a, **k: (True, "deps ok"),
    )

    def fail_if_artisan(*args, **kwargs):
        raise AssertionError("php artisan test should not run for README-only patches")

    monkeypatch.setattr("tools.test_tool._run_command", fail_if_artisan)

    result = run_validation(tmp_path, changed_files=["README.md"])
    assert result.status == "passed"
    assert "non-PHP" in result.output
