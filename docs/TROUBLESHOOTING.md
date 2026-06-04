# Troubleshooting

Guide for common pipeline failures (especially Blue-Lotus `Blvs-Web-Site` / Laravel Blade).

## Patch apply

### `patch does not apply` at wrong line (e.g. 57 vs 679)

**Cause:** LLM emitted `@@` headers for the wrong section. Large Blade files: Swiper init is often at the **bottom** (`new Swiper(...)` ~line 600+), not near the hero/search form (~line 50).

**Fixes in codebase:**

- `tools/patch_align.py` — `realign_diff_fuzzy`, `find_containing_window`, Swiper autoplay fallback
- `tools/patch_format.py` — `repair_diff_if_needed`; empty hunk lines must be ` ` not `+`
- `tools/patch_tool.py` — block-deletion, block-replacement, Swiper fallbacks after `git apply` fails
- Patcher reads disk via `_disk_files_for_repair` and `excerpt_for_patch` in `agents/patcher.py`

**Prompt guidance:** `prompts/patcher_prompt.txt` — edit `new Swiper` at bottom; copy `-` lines verbatim.

### `Ignoring previously applied (or reversed) patch`

Often means `-` lines do not exist on disk (wrong context) or a prior partial apply left the file changed. Workspace reset between issues should run `git reset` to `origin/develop` — check batch cleanup logs.

### `No valid patches in input`

Corrupt or empty diff; often from bad normalization (e.g. blank lines turned into `+` lines — fixed in `fix_hunk_body_prefixes`).

### Deletion-only patches (e.g. remove Clear filters block)

BVW-1535-style: only `-` lines, no `+`. Requires:

- Empty lines in hunks → space prefix, not `+`
- `rebuild_single_file_diff` with `added=[]`
- `_apply_block_deletion_fallback` in `patch_tool.py`

Leading spaces on Blade lines matter: file has ` {{-- Clear filters --}}`, diff must realign to disk.

## Validation & commit

### `Test run disabled (--run-tests not set)` then commit rejected

**Fixed:** `test_runner` always runs lightweight validation after apply; `--run-tests` only selects full suite. Commit allowed when validation passed or fix_verifier passed.

### `Fix verification must pass before commit`

Lightweight validation ran; `fix_verifier` must return `passed`. Check `outputs/latest_summary.md` and fix_verifier errors in state.

## Wrong fix quality

### Swiper autoplay patched in `app.js` with invented IDs

**Guards:** `tools/diff_guard.py` — `find_wrong_layer_patch`, `find_invented_dom_hooks`.  
**Correct pattern:** In Blade, inside existing init:

```javascript
loop: true,
autoplay: { delay: 7000, disableOnInteraction: false },
```

near `loop: false` for `.mySwiper` or `.cruiseCategorySwiper` in the correct file (`cruise.blade.php` vs `cruise_category.blade.php`).

### Research points to wrong page

Match Jira steps to file:

| Page / bug | Typical file |
|------------|----------------|
| Cruises search / clear filter | `resources/views/pages/cruise.blade.php` |
| Cruise category slider | `resources/views/pages/cruise_category.blade.php` |

Use `tools/view_context.py` / planner keywords from bug copy.

## Git noise in logs

`fatal: Needed a single revision` for `ai-fix/BVW-XXXX` — branch does not exist yet; expected on first run before branch is created.

## Self-fix loops exhausted

Check `patch_apply_error` in summary — should be passed to patcher on retry. If same wrong line repeats, improve research file list or add guard errors from `diff_guard`.

## Reproduce patch apply locally

```bash
python -c "
from pathlib import Path
from tools.patch_format import prepare_patch_for_apply
from tools.patch_tool import apply_patch
repo = Path('workspaces/.../Blvs-Web-Site')
diff = Path('outputs/latest.patch').read_text()
prepared = prepare_patch_for_apply(diff, repo)
Path('/tmp/t.patch').write_text(prepared)
apply_patch(repo, '/tmp/t.patch')
"
```

## Tests to run after patch-tool changes

```bash
uv run pytest tests/test_patch_align.py tests/test_clear_filters_patch.py tests/test_lightweight_validation.py -q
```
