"""Safe local patch apply and revert (no commits, no push)."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tools.agent_console import log_detail
from tools.patch_format import prepare_patch_for_apply
from tools.subprocess_log import run_logged
from tools.patch_guard import (
    extract_diff_paths,
    is_forbidden_path,
    paths_are_documentation_only,
)

MAX_CHANGED_FILES = 5
MAX_DELETION_LINES = 50
MIN_ADD_RATIO_FOR_LARGE_DELETE = 0.25

# Added lines in a patch must not contain risky shell patterns
_SHELL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*#!/bin/(?:ba)?sh", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bcurl\b.*\|\s*(?:ba)?sh"),
    re.compile(r"\bwget\b.*\|\s*(?:ba)?sh"),
    re.compile(r"\beval\s*\("),
    re.compile(r"`[^`]+`"),
    re.compile(r"\bsudo\s+"),
)


@dataclass(frozen=True)
class PatchValidationResult:
    """Outcome of pre-apply patch validation."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    affected_paths: list[str] = field(default_factory=list)

    @property
    def status_text(self) -> str:
        return "PASSED" if self.ok else "REJECTED"


def _read_patch_text(patch_path: Path) -> str:
    text = patch_path.read_text(encoding="utf-8").strip()
    if text.startswith("# No patch generated"):
        return ""
    return text


def _count_diff_stats(diff: str) -> tuple[int, int]:
    """Return (deletion_lines, addition_lines) excluding diff headers."""
    deletions = 0
    additions = 0
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-") and not line.startswith("---"):
            deletions += 1
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
    return deletions, additions


def _has_risky_shell_commands(diff: str) -> bool:
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        for pattern in _SHELL_PATTERNS:
            if pattern.search(content):
                return True
    return False


def _has_large_deletions(diff: str) -> bool:
    deletions, additions = _count_diff_stats(diff)
    if deletions <= MAX_DELETION_LINES:
        return False
    if additions == 0:
        return True
    return additions < deletions * MIN_ADD_RATIO_FOR_LARGE_DELETE


def validate_patch(
    repo_path: str | Path,
    patch_path: str | Path,
    *,
    risk_level: str = "high",
) -> PatchValidationResult:
    """
    Validate a patch file before applying it to the repository.

    Raises no exceptions; returns PatchValidationResult with errors populated.
    """
    _ = Path(repo_path).resolve()  # ensure repo exists
    path = Path(patch_path).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        return PatchValidationResult(ok=False, errors=[f"Patch file not found: {path}"])

    diff = _read_patch_text(path)
    if not diff:
        return PatchValidationResult(ok=False, errors=["Patch file is empty or placeholder."])

    if risk_level.strip().lower() == "high":
        errors.append("Step 2 risk_level is high; apply blocked.")

    affected = extract_diff_paths(diff)
    if not affected:
        errors.append("Could not parse any file paths from the patch.")

    if len(affected) > MAX_CHANGED_FILES:
        errors.append(
            f"Patch modifies {len(affected)} files (max {MAX_CHANGED_FILES} allowed)."
        )

    for file_path in affected:
        if is_forbidden_path(file_path):
            errors.append(f"Forbidden path in patch: {file_path}")

    if _has_large_deletions(diff) and not paths_are_documentation_only(affected):
        errors.append(
            f"Patch removes more than {MAX_DELETION_LINES} lines without sufficient additions."
        )

    if _has_risky_shell_commands(diff):
        errors.append("Patch contains risky shell commands in added lines.")

    if errors:
        return PatchValidationResult(ok=False, errors=errors, affected_paths=affected)

    repo_root = Path(repo_path).resolve()
    prepared = prepare_patch_for_apply(diff, repo_root)
    affected = extract_diff_paths(prepared) or affected

    # Dry-run apply when git is available (non-blocking warning only)
    if _is_git_repo(repo_root):
        check_err = _git_apply_check(repo_root, prepared)
        if check_err:
            removed, added = _extract_replacement_lines(prepared)
            err_lower = check_err.lower()
            can_fallback = (
                (len(removed) == len(added) and removed)
                or (removed and not added)
                or "already exists" in err_lower
                or "corrupt patch" in err_lower
                or "no valid patches" in err_lower
                or "patch does not apply" in err_lower
                or "patch failed" in err_lower
                or (added and not removed)
                or (removed and added)
            )
            if can_fallback:
                warnings.append(
                    f"git apply --check failed ({check_err[:80]}); "
                    "fallback apply will be attempted."
                )
            else:
                errors.append(f"Patch does not apply cleanly: {check_err}")
                return PatchValidationResult(
                    ok=False, errors=errors, affected_paths=affected
                )

    return PatchValidationResult(ok=True, warnings=warnings, affected_paths=affected)


def _git_apply_check(repo_root: Path, diff: str) -> str:
    """Return error string if git apply --check fails, else empty string."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".patch",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(diff)
        tmp_path = tmp.name
    try:
        check = _run_git(repo_root, "apply", "--check", "-p0", tmp_path)
        if check.returncode != 0:
            return check.stderr.strip() or check.stdout.strip()
        return ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git_toplevel(repo_root: Path) -> Path | None:
    result = _run_git(repo_root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _is_git_repo(repo_root: Path) -> bool:
    """True only when repo_root is the git work tree root (not a subdirectory)."""
    top = _git_toplevel(repo_root)
    return top is not None and top == repo_root.resolve()


def _cleanup_orig_files(repo_root: Path) -> None:
    for pattern in ("*.orig", "*.rej"):
        for artifact in repo_root.rglob(pattern):
            try:
                artifact.unlink()
            except OSError:
                pass


def _extract_replacement_lines(diff: str) -> tuple[list[str], list[str]]:
    """Return (removed_lines, added_lines) from diff hunks (no headers)."""
    removed: list[str] = []
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return removed, added


def _apply_block_deletion_fallback(repo_root: Path, diff: str) -> bool:
    """Delete a contiguous block of lines when the patch is removal-only."""
    removed, added = _extract_replacement_lines(diff)
    if not removed or added:
        return False

    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return False

    target = repo_root / paths[0]
    if not target.is_file():
        return False

    text = target.read_text(encoding="utf-8")
    file_lines = text.splitlines(keepends=True)
    plain = [ln.rstrip("\n\r") for ln in file_lines]

    from tools.patch_align import find_block_start, find_containing_window

    window = find_containing_window(plain, removed)
    if window:
        start, end = window
    else:
        start = find_block_start(plain, removed)
        if start is None:
            return False
        end = start + len([r for r in removed if r.strip()])

    merged = file_lines[:start] + file_lines[end:]
    new_text = "".join(merged)
    if new_text == text:
        return False
    target.write_text(new_text, encoding="utf-8")
    return True


def _apply_block_replacement_fallback(repo_root: Path, diff: str) -> bool:
    """Replace a contiguous removed block with added lines (1:N line changes)."""
    removed, added = _extract_replacement_lines(diff)
    if not removed or not added:
        return False

    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return False

    target = repo_root / paths[0]
    if not target.is_file():
        return False

    text = target.read_text(encoding="utf-8")
    file_lines = text.splitlines(keepends=True)
    if not file_lines and text:
        file_lines = [text]

    from tools.patch_align import find_block_start

    start = find_block_start([ln.rstrip("\n\r") for ln in file_lines], removed)
    if start is None:
        return False

    end = start + len(removed)
    new_lines = [ln if ln.endswith("\n") else ln + "\n" for ln in added]
    merged = file_lines[:start] + new_lines + file_lines[end:]
    new_text = "".join(merged)
    if new_text == text:
        return False

    target.write_text(new_text, encoding="utf-8")
    return True


def _apply_line_replacement_fallback(repo_root: Path, diff: str) -> bool:
    """
    Apply a minimal patch by replacing exact removed lines in target files.

    Used when git apply / patch reject LLM diffs with slightly wrong context.
    """
    removed, added = _extract_replacement_lines(diff)
    if not removed or len(removed) != len(added):
        if removed and added and _apply_block_replacement_fallback(repo_root, diff):
            return True
        return False

    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return False

    target = repo_root / paths[0]
    if not target.is_file():
        return False

    text = target.read_text(encoding="utf-8")
    new_text = text
    for old_line, new_line in zip(removed, added, strict=True):
        if old_line in new_text:
            new_text = new_text.replace(old_line, new_line, 1)
        elif old_line.strip() in new_text:
            new_text = new_text.replace(old_line.strip(), new_line, 1)
        else:
            return False

    if new_text == text:
        return False

    target.write_text(new_text, encoding="utf-8")
    return True


def _apply_insertion_fallback(repo_root: Path, diff: str) -> bool:
    """
    Apply pure additions (+ lines only) to a single existing file.

    Inserts new lines after the first hunk context line found in the file.
    """
    paths = extract_diff_paths(diff)
    if len(paths) != 1:
        return False

    target = repo_root / paths[0]
    if not target.is_file():
        return False

    additions: list[str] = []
    context_before: list[str] = []
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if line.startswith("---") or line.startswith("+++"):
            in_hunk = False
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])
        elif line.startswith(" "):
            context_before.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            return False

    if not additions:
        return False

    text = target.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines and not text:
        lines = [""]

    anchor = context_before[-1] if context_before else None
    insert_at = len(lines)
    if anchor:
        for i, existing in enumerate(lines):
            if existing.rstrip("\n\r") == anchor.rstrip("\n\r"):
                insert_at = i + 1
                break

    new_lines = [ln if ln.endswith("\n") else ln + "\n" for ln in additions]
    merged = lines[:insert_at] + new_lines + lines[insert_at:]
    target.write_text("".join(merged), encoding="utf-8")
    return True


def apply_patch(repo_path: str | Path, patch_path: str | Path) -> None:
    """
    Apply patch to the repository working tree.

    Tries `git apply`, then `patch -p0`, then exact line-replacement fallback.
    """
    repo_root = Path(repo_path).resolve()
    patch_file = Path(patch_path).resolve()
    raw_diff = _read_patch_text(patch_file)
    if not raw_diff:
        raise ValueError("Cannot apply empty patch.")

    paths = extract_diff_paths(raw_diff)
    log_detail(f"  Files in patch: {', '.join(paths) if paths else '(unknown)'}")
    log_detail("  Preparing patch for target repo…")
    diff = prepare_patch_for_apply(raw_diff, repo_root)
    if diff != raw_diff:
        log_detail("  Repaired patch format (hunk counts / line prefixes)")
    patch_file.write_text(diff, encoding="utf-8")

    errors: list[str] = []

    if _is_git_repo(repo_root):
        log_detail("  Trying git apply --check …")
        check = _run_git(repo_root, "apply", "--check", "-p0", str(patch_file))
        if check.returncode == 0:
            log_detail("  Trying git apply …")
            apply = _run_git(repo_root, "apply", "-p0", str(patch_file))
            if apply.returncode == 0:
                log_detail("  ✓ Applied via git apply")
                _cleanup_orig_files(repo_root)
                return
            errors.append(apply.stderr.strip() or apply.stdout.strip())
        else:
            errors.append(check.stderr.strip() or check.stdout.strip())
            if errors[-1]:
                log_detail(f"  git apply --check failed: {errors[-1][:200]}")

    log_detail("  Trying patch -p0 …")
    result = run_logged(
        ["patch", "-p0", "--forward", "-i", str(patch_file)],
        cwd=repo_root,
        timeout=120,
        echo_command=True,
    )
    if result.returncode == 0:
        log_detail("  ✓ Applied via patch command")
        _cleanup_orig_files(repo_root)
        return
    errors.append(result.stderr.strip() or result.stdout.strip())

    log_detail("  Trying block-deletion fallback …")
    if _apply_block_deletion_fallback(repo_root, diff):
        log_detail("  ✓ Applied via block-deletion fallback")
        _cleanup_orig_files(repo_root)
        return

    log_detail("  Trying Swiper autoplay fallback …")
    from tools.patch_align import apply_swiper_autoplay_fallback

    if apply_swiper_autoplay_fallback(repo_root, diff):
        log_detail("  ✓ Applied via Swiper autoplay fallback")
        _cleanup_orig_files(repo_root)
        return

    log_detail("  Trying block-replacement fallback …")
    if _apply_block_replacement_fallback(repo_root, diff):
        log_detail("  ✓ Applied via block-replacement fallback")
        _cleanup_orig_files(repo_root)
        return

    log_detail("  Trying line-replacement fallback …")
    if _apply_line_replacement_fallback(repo_root, diff):
        log_detail("  ✓ Applied via line-replacement fallback")
        _cleanup_orig_files(repo_root)
        return

    log_detail("  Trying insertion fallback …")
    if _apply_insertion_fallback(repo_root, diff):
        log_detail("  ✓ Applied via insertion fallback")
        _cleanup_orig_files(repo_root)
        return

    detail = "; ".join(e for e in errors if e) or "unknown error"
    raise RuntimeError(f"All apply strategies failed: {detail}")


def get_changed_files(
    repo_path: str | Path,
    *,
    candidates: list[str] | None = None,
) -> list[str]:
    """Return repository-relative paths with uncommitted changes."""
    repo_root = Path(repo_path).resolve()

    if _is_git_repo(repo_root):
        result = _run_git(repo_root, "diff", "--name-only")
        if result.returncode != 0:
            return []
        names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if names:
            return names
        staged = _run_git(repo_root, "diff", "--cached", "--name-only")
        return [line.strip() for line in staged.stdout.splitlines() if line.strip()]

    if candidates:
        return [c for c in candidates if (repo_root / c).is_file()]

    return []


def get_git_diff(
    repo_path: str | Path,
    *,
    paths: list[str] | None = None,
) -> str:
    """Return unified diff of current uncommitted changes."""
    repo_root = Path(repo_path).resolve()

    if _is_git_repo(repo_root):
        args = ["diff"]
        if paths:
            args.extend(paths)
        result = _run_git(repo_root, *args)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        staged = _run_git(repo_root, "diff", "--cached", *(paths or []))
        return staged.stdout if staged.returncode == 0 else ""

    if paths:
        parts: list[str] = []
        for rel in paths:
            target = repo_root / rel
            if target.is_file():
                parts.append(f"--- {rel}\n+++ {rel}\n(modified locally — not a git repo root)\n")
        return "\n".join(parts)

    return ""


def revert_patch(repo_path: str | Path, *, files: list[str] | None = None) -> list[str]:
    """
    Revert uncommitted changes from the last apply.

    Returns list of paths restored (relative to repo_path when possible).
    """
    repo_root = Path(repo_path).resolve()
    targets = list(files) if files else get_changed_files(repo_root)

    git_root = _git_toplevel(repo_root)
    if not targets and git_root is not None:
        result = _run_git(git_root, "diff", "--name-only")
        prefix = ""
        try:
            prefix = repo_root.relative_to(git_root).as_posix()
        except ValueError:
            pass
        for name in result.stdout.splitlines():
            name = name.strip()
            if not name:
                continue
            if prefix and name.startswith(f"{prefix}/"):
                targets.append(name[len(prefix) + 1 :])
            elif not prefix:
                targets.append(name)

    if not targets:
        return []

    git_root = git_root or _git_toplevel(repo_root)
    if git_root is None:
        raise RuntimeError(
            "Revert requires a git repository. Restore files manually for non-git repos."
        )

    restored: list[str] = []
    for rel in targets:
        abs_file = (repo_root / rel).resolve()
        try:
            git_rel = abs_file.relative_to(git_root).as_posix()
        except ValueError:
            continue
        result = _run_git(git_root, "restore", "--staged", "--worktree", git_rel)
        if result.returncode == 0:
            restored.append(rel)

    if not restored:
        raise RuntimeError("No files could be reverted via git restore.")

    return restored
