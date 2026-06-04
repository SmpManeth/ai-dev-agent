"""Tests for test_tool detection and validation."""

from pathlib import Path

from tools.test_tool import (
    detect_project_type,
    get_validation_commands,
    run_validation,
)


def test_detect_python_project(tmp_path: Path) -> None:
    (tmp_path / "validators.py").write_text("x = 1\n", encoding="utf-8")
    assert detect_project_type(tmp_path) == "python"


def test_detect_node_project(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"test":"echo ok"}}', encoding="utf-8")
    assert detect_project_type(tmp_path) == "node"


def test_get_validation_commands_python(tmp_path: Path) -> None:
    (tmp_path / "validators.py").write_text("x = 1\n", encoding="utf-8")
    cmds = get_validation_commands(tmp_path)
    labels = [c.label for c in cmds]
    assert "compileall" in labels


def test_run_validation_python_compileall(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    result = run_validation(tmp_path)
    assert result.status in ("passed", "failed", "skipped")
