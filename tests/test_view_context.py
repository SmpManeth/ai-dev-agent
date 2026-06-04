from pathlib import Path

from tools.view_context import find_views_for_task


def test_finds_cruise_category_view(tmp_path: Path):
    views = tmp_path / "resources" / "views" / "pages"
    views.mkdir(parents=True)
    blade = views / "cruise_category.blade.php"
    blade.write_text(
        "<h2>Discover the World's Leading Cruise Lines</h2>\n"
        '<div class="swiper cruiseCategorySwiper"></div>\n',
        encoding="utf-8",
    )
    found = find_views_for_task(
        tmp_path,
        'Slider "Discover the World\'s Leading Cruise Lines" does not auto-scroll',
    )
    assert "resources/views/pages/cruise_category.blade.php" in found
