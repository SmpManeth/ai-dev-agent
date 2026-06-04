"""Tests for patch safety guards."""

from tools.patch_guard import (
    diff_only_touches_files,
    extract_diff_paths,
    filter_allowed_files,
    is_forbidden_path,
    normalize_risk_level,
)


def test_is_forbidden_path_env() -> None:
    assert is_forbidden_path(".env")
    assert is_forbidden_path("config/.env.production")


def test_is_forbidden_path_auth() -> None:
    assert is_forbidden_path("app/Http/Middleware/Authentication.php")


def test_filter_allowed_files() -> None:
    allowed, blocked = filter_allowed_files(["validators.py", ".env"])
    assert allowed == ["validators.py"]
    assert blocked == [".env"]


def test_extract_diff_paths() -> None:
    diff = """--- a/validators.py
+++ b/validators.py
@@ -1,3 +1,3 @@
-old
+new
"""
    paths = extract_diff_paths(diff)
    assert "validators.py" in paths


def test_diff_only_touches_files() -> None:
    diff = """--- a/validators.py
+++ b/validators.py
@@ -1,1 +1,1 @@
-x
+y
"""
    assert diff_only_touches_files(diff, {"validators.py"})


def test_normalize_risk_level() -> None:
    assert normalize_risk_level("LOW") == "low"
    assert normalize_risk_level("unknown") == "high"
