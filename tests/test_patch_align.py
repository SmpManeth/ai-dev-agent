"""Tests for patch realignment and block apply fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.patch_align import find_block_start, realign_diff_to_files, rebuild_single_file_diff
from tools.patch_format import repair_diff_if_needed
from tools.patch_tool import _apply_block_replacement_fallback, validate_patch


BLADE_SNIPPET = """<script>
 document.addEventListener('DOMContentLoaded', function() {
 const swiper = new Swiper(".cruiseCategorySwiper", {
 slidesPerView: 1,
 spaceBetween: 20,
 loop: false,

 navigation: {
 nextEl: '.swiper-button-next-custom',
 prevEl: '.swiper-button-prev-custom',
 },
 });
 });
</script>
"""


def test_find_block_start_matches_whitespace() -> None:
    lines = BLADE_SNIPPET.splitlines()
    block = [" loop: false,", ""]
    assert find_block_start(lines, block) == 5


def test_rebuild_single_file_diff_multiline_insert() -> None:
    removed = [" loop: false,", ""]
    added = [
        " loop: true,",
        " autoplay: { delay: 7000, disableOnInteraction: false },",
        "",
    ]
    diff = rebuild_single_file_diff("cruise.blade.php", BLADE_SNIPPET, removed, added)
    assert diff is not None
    assert "@@ -" in diff
    assert "+ autoplay:" in diff


def test_repair_diff_realigns_bad_hunk_line_numbers() -> None:
    bad = """--- cruise.blade.php
+++ cruise.blade.php
@@ -530,2 +530,4 @@
- loop: false,
+ loop: true,
+ autoplay: { delay: 7000, disableOnInteraction: false },
"""
    fixed = repair_diff_if_needed(bad, {"cruise.blade.php": BLADE_SNIPPET})
    assert "530" not in fixed or find_block_start(
        BLADE_SNIPPET.splitlines(), [" loop: false,"]
    ) is not None


def test_validate_patch_warns_on_misaligned_context(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "cruise.blade.php"
    target.write_text(BLADE_SNIPPET, encoding="utf-8")
    patch = tmp_path / "bad.patch"
    patch.write_text(
        """--- cruise.blade.php
+++ cruise.blade.php
@@ -530,1 +530,3 @@
- loop: false,
+ loop: true,
+ autoplay: { delay: 7000, disableOnInteraction: false },
""",
        encoding="utf-8",
    )

    import subprocess

    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "t@t.com"],
        ["git", "config", "user.name", "T"],
        ["git", "add", "."],
        ["git", "commit", "-m", "init"],
    ):
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        if r.returncode != 0 and cmd[1] != "init":
            pytest.skip("git unavailable")

    result = validate_patch(repo, patch, risk_level="low")
    assert result.ok
    assert any("fallback" in w.lower() for w in result.warnings)


def test_block_replacement_fallback(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "cruise.blade.php"
    target.write_text(BLADE_SNIPPET, encoding="utf-8")
    diff = """--- cruise.blade.php
+++ cruise.blade.php
@@ -1,1 +1,3 @@
- loop: false,
+ loop: true,
+ autoplay: { delay: 7000, disableOnInteraction: false },
"""
    assert _apply_block_replacement_fallback(repo, diff)
    text = target.read_text(encoding="utf-8")
    assert "loop: true" in text
    assert "autoplay" in text
    assert "loop: false" not in text
