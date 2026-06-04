# Jira batch and Git workflow

## Jira selection

- Label: `JIRA_LABEL` (default `ai-fix`)
- Project: `JIRA_PROJECT_KEY`
- Credentials: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in **root** `.env`

Each scheduler cycle processes **`--max-tasks=1`** by default (one issue end-to-end).

## Branch and PR

- Branch: `ai-fix/{ISSUE-KEY}` (e.g. `ai-fix/BVW-1535`)
- Base: `GITHUB_BASE_BRANCH` (e.g. `develop`)
- PR: **draft only**; agent does not merge
- Push: `force-with-lease` then `--force` fallback if lease stale (`agents/github_pr.py`)

## Workspace sync

When `AI_AGENT_AUTO_SYNC_REPO=true`:

- Clone to `workspaces/{GITHUB_OWNER}/{GITHUB_REPO}` if missing
- `git fetch` + hard reset to `origin/{GITHUB_BASE_BRANCH}` before each issue
- On failure/cleanup: reset worktree, clear `outputs/latest.patch`

Override path: `AI_AGENT_WORKSPACE_ROOT` or `--repo` / `GITHUB_OWNER`+`GITHUB_REPO`.

## CLI flags

| Flag | Meaning |
|------|---------|
| `--from-jira` | Batch eligible issues |
| `--apply-patch` | Apply patch to workspace (auto-enabled with commit/PR) |
| `--run-tests` | Full phpunit/artisan/npm test (optional) |
| `--commit` | Local commit on ai-fix branch |
| `--create-pr` | Push + draft PR |
| `--max-tasks=N` | Issues per invocation |
| `--dry-run` | List issues only |
| `--jira-issue KEY` | Single issue (requires `--create-pr` in main.py) |

## Laravel equivalents

| Action | Command / UI |
|--------|----------------|
| Batch | `php artisan ai-agent:run-jira-batch` or **Run Jira ai-fix Batch Now** |
| Single task | Task detail → **Run Agent** |
| Approval gate | `AI_AGENT_REQUIRES_APPROVAL=true` |

## Batch output

- JSON path passed as `--batch-json` for dashboard sync
- Progress files: `dashboard/storage/app/agent-progress/` (or `--progress-dir`)
- Human summary: `outputs/latest_summary.md`

## On failure

- Jira comment may note agent could not complete (see batch handler)
- Workspace reset for next issue
- Issue remains for next cron cycle unless skipped (open PR / existing branch)

## Skip conditions

Issues skipped when open PR exists or branch already has work — see `batch_jira.py` and Jira sync logic.
