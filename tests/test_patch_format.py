"""Tests for patch normalization."""

from __future__ import annotations

from pathlib import Path

from tools.patch_format import (
    fix_dev_null_headers,
    fix_hunk_body_prefixes,
    prepare_patch_for_apply,
)


def test_fix_hunk_body_prefixes_adds_context_space() -> None:
    diff = "@@ -1,1 +1,2 @@\n# title\n+added\n"
    fixed = fix_hunk_body_prefixes(diff)
    assert fixed.splitlines()[1].startswith(" ")


def test_fix_dev_null_headers_for_existing_file(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# existing\n", encoding="utf-8")
    diff = "--- /dev/null\n+++ README.md\n@@ -0,0 +1,1 @@\n+# hello\n"
    fixed = fix_dev_null_headers(diff, tmp_path)
    assert "--- a/README.md" in fixed
    assert "+++ b/README.md" in fixed
    assert "/dev/null" not in fixed


def test_prepare_patch_rebuilds_one_line_edit(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("old line\n", encoding="utf-8")
    diff = (
        "--- /dev/null\n+++ app.py\n@@ -0,0 +1,1 @@\n+new line\n"
    )
    prepared = prepare_patch_for_apply(diff, tmp_path)
    assert "app.py" in prepared
