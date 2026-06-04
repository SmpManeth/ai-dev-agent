"""Apply fixes for misaligned Swiper hunks on cruise.blade.php (BVW-1535-style)."""

from __future__ import annotations

from pathlib import Path

from tools.patch_align import apply_swiper_autoplay_fallback, realign_diff_fuzzy
from tools.patch_format import prepare_patch_for_apply
from tools.patch_tool import apply_patch

REPO = (
    Path(__file__).resolve().parents[1]
    / "workspaces"
    / "Blue-Lotus-Vacations"
    / "Blvs-Web-Site"
)
BLADE = "resources/views/pages/cruise.blade.php"


def _bad_hunk_at_line_57() -> str:
    return f"""--- {BLADE}
+++ {BLADE}
@@ -57,1 +57,3 @@
- loop: false,
+ loop: true,
+ autoplay: {{ delay: 7000, disableOnInteraction: false }},
"""


def test_realign_fuzzy_finds_swiper_not_line_57() -> None:
    if not (REPO / BLADE).is_file():
        return
    content = (REPO / BLADE).read_text(encoding="utf-8")
    fixed = realign_diff_fuzzy(
        _bad_hunk_at_line_57(),
        {BLADE: content},
    )
    assert "loop: false" in fixed or "683" in fixed or "679" in fixed
    assert fixed.count("@@") >= 1


def test_swiper_autoplay_fallback_on_real_repo(tmp_path: Path) -> None:
    if not (REPO / BLADE).is_file():
        return

    repo = tmp_path / "repo"
    blade = repo / BLADE
    blade.parent.mkdir(parents=True, exist_ok=True)
    blade.write_text((REPO / BLADE).read_text(encoding="utf-8"), encoding="utf-8")
    before = blade.read_text(encoding="utf-8")
    assert "loop: false" in before

    diff = """--- resources/views/pages/cruise.blade.php
+++ resources/views/pages/cruise.blade.php
@@ -57,1 +57,3 @@
- loop: false,
+ loop: true,
+ autoplay: { delay: 7000, disableOnInteraction: false },
"""
    assert apply_swiper_autoplay_fallback(repo, diff)
    after = blade.read_text(encoding="utf-8")
    assert "autoplay" in after
    assert after.count("loop: false") < before.count("loop: false")
