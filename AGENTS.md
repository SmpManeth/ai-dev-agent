# AI Dev Agent — guide for AI assistants

Read this file first when working in this repository.

## What this project is

Autonomous **bug-fix pipeline**: Jira (`ai-fix` label) → plan → research → patch → apply → validate → fix verify → commit → **draft PR** → Jira comment. Target code lives in **`workspaces/{owner}/{repo}/`** (cloned customer repos), not in this repo’s root.

## Repository map

| Path | Purpose |
|------|---------|
| `main.py` | CLI entry (`--from-jira`, `--apply-patch`, `--commit`, `--create-pr`) |
| `agents/` | LangGraph nodes (planner, researcher, patcher, patch_applier, test_runner, fix_verifier, self_fix, git_committer, github_pr) |
| `workflows/bug_fix_graph.py` | Pipeline routing and retries |
| `prompts/` | Agent prompts; loaded via `config.load_agent_prompt()` |
| `prompts/shared_rules.txt` | Shared rules appended to several agents |
| `tools/` | patch_tool, patch_format, patch_align, test_tool, diff_guard, security_policy, etc. |
| `dashboard/` | Laravel control panel + scheduler (spawns Python) |
| `workspaces/` | Git clones (gitignored) |
| `outputs/` | `latest.patch`, `latest_summary.md`, audit/cost logs |
| `docs/` | Human + AI documentation |

## Commands (canonical)

```bash
# One Jira issue per run (production default)
python main.py --from-jira --apply-patch --commit --create-pr --max-tasks=1

# Full test suite (phpunit / npm test) — optional, slower
python main.py --from-jira --apply-patch --run-tests --commit --create-pr --max-tasks=1

# Dashboard batch (same as above, via Laravel)
cd dashboard && php artisan ai-agent:run-jira-batch --force
```

**Do not** auto-enable `--run-tests` for batch unless the user asks. Default validation is **lightweight** (`php -l` for Blade/PHP; `npm run build` only when JS/CSS changed).

## Critical rules for code changes

1. **Minimize scope** — fix the reported bug only; match existing style.
2. **Never commit/push** unless the user explicitly asks.
3. **Two `.env` files**: root Python `.env` (API keys, GitHub, Jira) and `dashboard/.env` (`AI_AGENT_PROJECT_PATH`, `AI_AGENT_PYTHON_PATH`).
4. **Blade/Swiper bugs** — edit the existing `new Swiper(...)` block in the **correct** `.blade.php`; do not invent DOM IDs in `app.js`. See `docs/TROUBLESHOOTING.md`.
5. **Patch apply** — minus (`-`) lines must match disk (leading spaces matter). Deletion-only hunks are supported; see `tools/patch_format.py` and `tools/patch_align.py`.
6. **Dashboard is unauthenticated** by default — mention auth/VPN before production exposure.

## When debugging failures

| Symptom | Read |
|---------|------|
| Patch does not apply / line 57 vs 679 | `docs/TROUBLESHOOTING.md` § Patch apply |
| Commit rejected / test_skipped | `docs/TROUBLESHOOTING.md` § Validation & commit |
| Wrong file (app.js vs Blade) | `tools/diff_guard.py`, `prompts/patcher_prompt.txt` |
| Production hosting | `docs/PRODUCTION_DEPLOYMENT.md` |
| Kill switch, sandbox, audit | `docs/PRODUCTION_HARDENING.md` |

## Docs index

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — pipeline graph, state, agents
- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) — server, cron, Nginx
- [docs/PRODUCTION_HARDENING.md](docs/PRODUCTION_HARDENING.md) — security policy
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — common failures
- [docs/JIRA_AND_GIT.md](docs/JIRA_AND_GIT.md) — Jira batch, branches, PRs
- [dashboard/README.md](dashboard/README.md) — Laravel setup

## Tests

```bash
uv run pytest
```

Prefer targeted tests (`tests/test_patch_align.py`, `tests/test_clear_filters_patch.py`) over full suite when validating patch tooling changes.
