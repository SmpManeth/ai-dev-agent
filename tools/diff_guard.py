"""Programmatic checks on proposed diffs (catch hallucinations before apply)."""

from __future__ import annotations

import re

from tools.patch_guard import extract_diff_paths

# Added lines in JS that reference DOM hooks
_ID_PATTERN = re.compile(
    r"getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)
_QUERY_PATTERN = re.compile(
    r"querySelector(?:All)?\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)


def _added_lines(unified_diff: str) -> str:
    return "\n".join(
        line[1:]
        for line in unified_diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _corpus(files_read: dict[str, str]) -> str:
    parts = list(files_read.keys())
    for content in files_read.values():
        if not content.startswith("(unable to read"):
            parts.append(content)
    return "\n".join(parts)


def _hook_in_corpus(hook: str, corpus: str) -> bool:
    hook = hook.strip()
    if not hook:
        return True
    if hook in corpus:
        return True
    # #id or .class
    if hook.startswith(("#", ".")) and hook[1:] in corpus:
        return True
    return False


def find_invented_dom_hooks(unified_diff: str, files_read: dict[str, str]) -> list[str]:
    """Return errors for DOM hooks added in the diff but absent from source files."""
    added = _added_lines(unified_diff)
    if not added.strip():
        return []
    corpus = _corpus(files_read)
    errors: list[str] = []

    for pattern in (_ID_PATTERN, _QUERY_PATTERN):
        for match in pattern.finditer(added):
            hook = match.group(1).strip()
            if not _hook_in_corpus(hook, corpus):
                errors.append(
                    f"Invented DOM hook '{hook}' — not found in files read (do not guess selectors)"
                )
    return errors


def _blade_has_swiper(corpus: str) -> bool:
    lower = corpus.lower()
    return "new swiper" in lower or "cruisecategoryswiper" in lower or (
        "swiper" in lower and ".blade.php" in lower
    )


def find_wrong_layer_patch(
    unified_diff: str,
    files_read: dict[str, str],
    *,
    task_description: str = "",
) -> list[str]:
    """
    Fail when patch only touches global app.js but sources show Swiper in Blade
    for a slider/autoplay-style UI bug.
    """
    paths = extract_diff_paths(unified_diff)
    if not paths:
        return []

    normalized = [p.replace("\\", "/").lower() for p in paths]
    only_app_js = all(
        p.endswith("app.js") or p.endswith("/js/app.js") for p in normalized
    )
    if not only_app_js:
        return []

    corpus = _corpus(files_read)
    if not _blade_has_swiper(corpus):
        return []

    task_lower = task_description.lower()
    ui_hints = (
        "slider",
        "carousel",
        "scroll",
        "autoplay",
        "auto-scroll",
        "swiper",
        "slide",
    )
    if not any(h in task_lower for h in ui_hints):
        return []

    blade_paths = [k for k in files_read if k.endswith(".blade.php")]
    if not blade_paths:
        return []

    return [
        "Patch only modifies app.js but files read include Blade templates with "
        "Swiper — fix the existing Swiper init in the Blade file, not global app.js"
    ]


def validate_proposed_diff(
    unified_diff: str,
    files_read: dict[str, str],
    *,
    task_description: str = "",
) -> list[str]:
    """Aggregate programmatic patch validation errors."""
    if not unified_diff.strip():
        return []
    errors: list[str] = []
    errors.extend(find_invented_dom_hooks(unified_diff, files_read))
    errors.extend(
        find_wrong_layer_patch(
            unified_diff,
            files_read,
            task_description=task_description,
        )
    )
    return errors
