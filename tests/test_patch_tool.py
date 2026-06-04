"""Tests for patch_tool validation and apply."""

from pathlib import Path

import pytest

from tools.patch_tool import (
    PatchValidationResult,
    apply_patch,
    get_changed_files,
    get_git_diff,
    revert_patch,
    validate_patch,
)

SAMPLE_PATCH = """--- validators.py
+++ validators.py
@@ -8,1 +8,1 @@
-USERNAME_ERROR = "Invalid email format. Use 3-20 alphanumeric characters."
+USERNAME_ERROR = "Invalid username format. Use 3-20 alphanumeric characters."
"""


def test_validate_patch_rejects_missing_file(tmp_path: Path) -> None:
    result = validate_patch(tmp_path, tmp_path / "missing.patch", risk_level="low")
    assert not result.ok
    assert any("not found" in e for e in result.errors)


def test_validate_patch_rejects_empty(tmp_path: Path) -> None:
    patch = tmp_path / "empty.patch"
    patch.write_text("# No patch generated\n", encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert not result.ok


def test_validate_patch_rejects_high_risk(tmp_path: Path) -> None:
    patch = tmp_path / "ok.patch"
    patch.write_text(SAMPLE_PATCH, encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="high")
    assert not result.ok
    assert any("risk_level" in e for e in result.errors)


def test_validate_patch_rejects_env(tmp_path: Path) -> None:
    patch = tmp_path / "bad.patch"
    patch.write_text("""--- .env
+++ .env
@@ -1 +1 @@
-x=1
+x=2
""", encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert not result.ok
    assert any("Forbidden" in e for e in result.errors)


def test_validate_patch_rejects_composer(tmp_path: Path) -> None:
    patch = tmp_path / "bad.patch"
    patch.write_text("""--- composer.json
+++ composer.json
@@ -1 +1 @@
-{}
+{"x":1}
""", encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert not result.ok


def test_validate_patch_allows_large_readme_rewrite(tmp_path: Path) -> None:
    patch = tmp_path / "readme.patch"
    removed = "\n".join(f"-line {i}" for i in range(60))
    added = "\n".join(f"+new {i}" for i in range(5))
    patch.write_text(
        f"""--- README.md
+++ README.md
@@ -1,60 +1,5 @@
{removed}
{added}
""",
        encoding="utf-8",
    )
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert result.ok, result.errors


def test_validate_patch_rejects_large_code_deletion(tmp_path: Path) -> None:
    patch = tmp_path / "code.patch"
    removed = "\n".join(f"-    $x = {i};" for i in range(60))
    patch.write_text(
        f"""--- app/Example.php
+++ app/Example.php
@@ -1,60 +1,0 @@
{removed}
""",
        encoding="utf-8",
    )
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert not result.ok
    assert any("50 lines" in e for e in result.errors)


def test_validate_patch_rejects_shell(tmp_path: Path) -> None:
    patch = tmp_path / "bad.patch"
    patch.write_text("""--- run.sh
+++ run.sh
@@ -1,0 +1,1 @@
+#!/bin/bash
+rm -rf /
""", encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert not result.ok
    assert any("shell" in e.lower() for e in result.errors)


def test_validate_patch_passes_sample(tmp_path: Path) -> None:
    patch = tmp_path / "ok.patch"
    patch.write_text(SAMPLE_PATCH, encoding="utf-8")
    result = validate_patch(tmp_path, patch, risk_level="low")
    assert result.ok
    assert "validators.py" in result.affected_paths


def test_apply_and_revert_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "validators.py"
    target.write_text(
        'USERNAME_ERROR = "Invalid email format. Use 3-20 alphanumeric characters."\n',
        encoding="utf-8",
    )
    patch = tmp_path / "fix.patch"
    patch.write_text(SAMPLE_PATCH, encoding="utf-8")

    subprocess_init = __import__("subprocess").run
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "add", "."],
        ["git", "commit", "-m", "init"],
    ):
        r = subprocess_init(cmd, cwd=repo, capture_output=True, text=True)
        if r.returncode != 0 and cmd[1] != "init":
            pytest.skip(f"git not available: {r.stderr}")

    validation = validate_patch(repo, patch, risk_level="low")
    assert validation.ok

    apply_patch(repo, patch)
    assert "username" in target.read_text(encoding="utf-8")
    assert "validators.py" in get_changed_files(repo)
    assert get_git_diff(repo)

    revert_patch(repo)
    assert "email" in target.read_text(encoding="utf-8")
