"""Tests for hunk header line-count repair."""

from __future__ import annotations

from pathlib import Path

from tools.patch_format import prepare_patch_for_apply, recount_hunk_headers

# Snippet from BVW-1536 run: header claimed +72 but only 66 + lines exist.
MISMATCHED_HUNK_PATCH = """--- a/resources/js/app.js
+++ b/resources/js/app.js
@@ -41,3 +41,72 @@ const options = {
     defaultPosition: 1,
     interval: 7000,
 };
+
+function initCruiseLinesAutoplay() {
+return;
+}
"""


def test_recount_hunk_headers_fixes_addition_count() -> None:
    fixed = recount_hunk_headers(MISMATCHED_HUNK_PATCH)
    assert "+41,72" not in fixed
    assert "+41,7" in fixed
    assert "+41,72" not in fixed


def test_prepare_strips_ab_prefixes() -> None:
    prepared = prepare_patch_for_apply(MISMATCHED_HUNK_PATCH, Path("/tmp"))
    assert prepared.startswith("--- resources/")
    assert "+++ resources/" in prepared
    assert "--- a/" not in prepared
