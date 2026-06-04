from pathlib import Path

from tools.investigation_paths import expand_investigation_paths


def test_expand_investigation_paths_includes_planned(tmp_path: Path):
    (tmp_path / "resources" / "js").mkdir(parents=True)
    app_js = tmp_path / "resources" / "js" / "app.js"
    app_js.write_text("console.log('x');\n", encoding="utf-8")
    routes = tmp_path / "routes" / "web.php"
    routes.parent.mkdir(parents=True)
    routes.write_text("<?php\n", encoding="utf-8")

    expanded = expand_investigation_paths(
        tmp_path,
        ["resources/js/app.js"],
        "error in app.js route handler",
        max_files=8,
    )
    assert "resources/js/app.js" in expanded
