# Architecture

## Pipeline (LangGraph)

```
START → planner → researcher → patcher → patch_applier
  → test_runner → fix_verifier ↔ self_fix (on failure)
  → git_committer → github_pr → jira_updater → END
```

Defined in `workflows/bug_fix_graph.py`.

### Routing highlights

- After **patch_applier**: always **test_runner** if patch applied (not gated on `--run-tests`).
- **test_runner**: `full_test_suite=False` by default; `--run-tests` enables phpunit/artisan/npm test.
- After tests pass/skip: **fix_verifier** (semantic check before commit).
- **self_fix**: revert → optional re-research → patcher → patch_applier again (max retries from policy).

## Agents

| Agent | Output |
|-------|--------|
| Planner | `files_to_investigate`, plan steps |
| Researcher | root cause, recommended fix, confidence |
| Patcher | `unified_diff`, risk_level (uses `repair_diff_if_needed` + `realign_diff_fuzzy`) |
| Patch applier | applies `outputs/latest.patch` via git apply + fallbacks |
| Test runner | `validation_status`, `validation_output` |
| Fix verifier | `fix_verification_status` |
| Self fix | increments `retry_count`, feeds apply errors to patcher |
| Git committer | branch `ai-fix/{JIRA-KEY}`, local commit |
| GitHub PR | draft PR, force-with-lease push |
| Jira updater | comment + status |

## Patch apply stack

1. `prepare_patch_for_apply()` — normalize, strip `a/` prefixes, repair/realign hunks
2. `git apply` → `patch -p0` → block-deletion → Swiper autoplay → block-replacement → line-replacement → insertion

Key modules: `tools/patch_format.py`, `tools/patch_align.py`, `tools/patch_tool.py`, `tools/diff_guard.py`.

## State

`models/state.py` — `AgentState` fields include `files_read`, `unified_diff`, `patch_apply_error`, `validation_errors`, `fix_verification_status`, `retry_count`.

## Laravel dashboard

- Spawns Python: `AiAgentBatchService`, `AiAgentProcessService`
- Scheduler: `routes/console.php` → `ai-agent:run-jira-batch`
- SQLite (default) or MySQL for `ai_agent_tasks`, logs, audit events
- Hardening JSON: `dashboard/storage/app/ai-agent-hardening.json`

## External dependencies

- OpenAI (all agents)
- GitHub (clone, push, draft PR)
- Jira (fetch `ai-fix` issues, comment, transition)
