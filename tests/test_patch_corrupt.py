"""Tests for corrupt LLM patch repair."""

from __future__ import annotations

from pathlib import Path

from tools.patch_format import prepare_patch_for_apply
from tools.patch_tool import validate_patch


CORRUPT_README_PATCH = """--- README.md
+++ README.md
@@ -1,6 +1,7 @@
# Blvs-Web-Site

Blue Lotus Vacations web application (Laravel).
+
Hello! Welcome to the Blue Lotus Vacations web application.
"""


def test_prepare_patch_fixes_missing_context_prefixes(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Blvs-Web-Site\n\nBlue Lotus Vacations web application (Laravel).\n",
        encoding="utf-8",
    )
    prepared = prepare_patch_for_apply(CORRUPT_README_PATCH, tmp_path)
    body = prepared.splitlines()
    assert body[3].startswith(" ")
    assert any(l.startswith("+Hello!") for l in body)


def test_validate_allows_fallback_for_corrupt_patch(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Blvs-Web-Site\n\nBlue Lotus Vacations web application (Laravel).\n",
        encoding="utf-8",
    )
    patch_file = tmp_path / "test.patch"
    patch_file.write_text(CORRUPT_README_PATCH, encoding="utf-8")
    subprocess_init = tmp_path / ".git"
    # validate_patch needs git repo - skip if no git
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.com"},
    )

    result = validate_patch(tmp_path, patch_file, risk_level="low")
    assert result.ok, result.errors
