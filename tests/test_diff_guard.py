from tools.diff_guard import (
    find_invented_dom_hooks,
    find_wrong_layer_patch,
    validate_proposed_diff,
)


def test_rejects_invented_get_element_by_id():
    files = {"resources/js/app.js": "console.log('x');\n"}
    diff = """--- a/resources/js/app.js
+++ b/resources/js/app.js
@@ -1 +1,5 @@
+document.getElementById("discoverWorldCruiseSlider");
"""
    errors = find_invented_dom_hooks(diff, files)
    assert any("discoverWorldCruiseSlider" in e for e in errors)


def test_rejects_app_js_only_when_blade_has_swiper():
    files = {
        "resources/views/pages/cruise_category.blade.php": (
            '<div class="swiper cruiseCategorySwiper"></div>\n'
            "const swiper = new Swiper('.cruiseCategorySwiper', { loop: false });\n"
        ),
        "resources/js/app.js": "import './bootstrap';\n",
    }
    diff = """--- a/resources/js/app.js
+++ b/resources/js/app.js
@@ -1 +1,3 @@
+setInterval(() => {}, 7000);
"""
    errors = find_wrong_layer_patch(
        diff,
        files,
        task_description="Slider does not auto-scroll",
    )
    assert len(errors) >= 1


def test_allows_blade_swiper_autoplay_fix():
    files = {
        "resources/views/pages/cruise_category.blade.php": (
            "new Swiper('.cruiseCategorySwiper', { loop: false });\n"
        ),
    }
    diff = """--- a/resources/views/pages/cruise_category.blade.php
+++ b/resources/views/pages/cruise_category.blade.php
@@ -1,3 +1,8 @@
 loop: false,
+loop: true,
+autoplay: { delay: 7000 },
"""
    assert validate_proposed_diff(
        diff,
        files,
        task_description="Slider autoplay",
    ) == []
