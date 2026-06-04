"""BVW-1535: delete Clear filters block from cruise.blade.php."""

from __future__ import annotations

from pathlib import Path

from tools.patch_align import find_containing_window, realign_diff_fuzzy
from tools.patch_format import prepare_patch_for_apply
from tools.patch_tool import _apply_block_deletion_fallback, apply_patch

REPO = (
    Path(__file__).resolve().parents[1]
    / "workspaces"
    / "Blue-Lotus-Vacations"
    / "Blvs-Web-Site"
)
BLADE = "resources/views/pages/cruise.blade.php"

CLEAR_FILTER_PATCH = """--- a/resources/views/pages/cruise.blade.php
+++ b/resources/views/pages/cruise.blade.php
@@ -58,14 +58,5 @@
  </div>
  </form>

-{{-- Clear filters --}}
-@if(($q ?? '') !== '' || ($categoryId ?? null))
-<div class="mt-3">
-<a href="{{ route('cruisePage.search') }}"
-class="inline-flex items-center text-sm text-white/90 underline hover:opacity-80">
-Clear filters
-</a>
-</div>
-@endif
  </div>
  </div>
"""


def test_find_clear_filters_window() -> None:
    if not (REPO / BLADE).is_file():
        return
    content = (REPO / BLADE).read_text(encoding="utf-8")
    lines = content.splitlines()
    removed = [
        "{{-- Clear filters --}}",
        "@if(($q ?? '') !== '' || ($categoryId ?? null))",
    ]
    window = find_containing_window(lines, removed)
    assert window is not None


def test_apply_clear_filters_deletion(tmp_path: Path) -> None:
    if not (REPO / BLADE).is_file():
        return
    repo = tmp_path / "repo"
    blade = repo / BLADE
    blade.parent.mkdir(parents=True, exist_ok=True)
    blade.write_text((REPO / BLADE).read_text(encoding="utf-8"), encoding="utf-8")
    assert "Clear filters" in blade.read_text(encoding="utf-8")

    patch = tmp_path / "x.patch"
    patch.write_text(CLEAR_FILTER_PATCH, encoding="utf-8")
    apply_patch(repo, patch)
    after = blade.read_text(encoding="utf-8")
    assert "Clear filters" not in after
    assert "{{-- Clear filters --}}" not in after
