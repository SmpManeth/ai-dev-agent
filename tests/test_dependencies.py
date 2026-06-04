"""Tests for dependency bootstrap before validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.test_tool import ensure_project_dependencies, get_validation_commands


def test_get_validation_commands_skips_artisan_without_vendor(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text(
        '{"require":{"laravel/framework":"^11.0"},"scripts":{"test":"phpunit"}}',
        encoding="utf-8",
    )
    (tmp_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    labels = [c.label for c in get_validation_commands(tmp_path)]
    assert "php artisan test" not in labels


@patch("tools.test_tool.subprocess.run")
def test_ensure_composer_install_when_vendor_missing(mock_run, tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text("{}", encoding="utf-8")

    def side_effect(argv, **kwargs):
        if argv[:2] == ["composer", "install"]:
            (tmp_path / "vendor").mkdir(exist_ok=True)
            (tmp_path / "vendor" / "autoload.php").write_text("", encoding="utf-8")
            return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    mock_run.side_effect = side_effect
    ok, log = ensure_project_dependencies(tmp_path)
    assert ok
    assert "composer install" in log
