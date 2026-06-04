# AI Agent Control Panel (Laravel)

Laravel UI to **monitor and trigger** the Python autonomous agent at the repo root. Python runs the pipeline; this app stores tasks, logs, and scheduler state.

## Setup

```bash
cd dashboard
composer install
cp .env.example .env
php artisan key:generate
```

Configure `dashboard/.env`:

```env
AI_AGENT_PYTHON_PATH="/path/to/ai-dev-agent/.venv/bin/python"
AI_AGENT_PROJECT_PATH="/absolute/path/to/ai-dev-agent"
GITHUB_OWNER=your-org
GITHUB_REPO=your-repo
JIRA_BASE_URL=https://your-domain.atlassian.net
AI_AGENT_SCHEDULE_ENABLED=true
AI_AGENT_REQUIRES_APPROVAL=false
```

Configure the **Python** `.env` at the repo root (`OPENAI_*`, `JIRA_*`, `GITHUB_*`) — the agent reads credentials there.

```bash
php artisan migrate
php artisan serve
```

Open http://127.0.0.1:8000/ai-agent/tasks — the **Connection** panel shows whether paths and config are ready.

## How tasks appear

Tasks are **not** seeded. They are created when:

1. **Scheduled batch** — `php artisan ai-agent:run-jira-batch` (every N minutes if cron is set), or
2. **Manual batch** — **Run Jira ai-fix Batch Now** on the tasks page.

Each Jira issue with label `ai-fix` becomes one row (`jira_issue_key`, PR link, status, logs).

## System cron (automatic mode)

```bash
* * * * * cd /path/to/ai-dev-agent/dashboard && php artisan schedule:run >> storage/logs/cron.log 2>&1
```

Test once:

```bash
php artisan ai-agent:run-jira-batch --force
```

## Manual single-task run (optional)

Open a task from the list → **Run Agent** (re-run a failed ticket or an approved high-risk task). Requires `AI_AGENT_REQUIRES_APPROVAL=true` for pending tasks to need **Approve** first.

## Architecture

| Layer | Role |
|-------|------|
| `AiAgentBatchService` | `sync_repo.py` + `main.py --from-jira` → `batch-json` → DB |
| `AiAgentProcessService` | `main.py --jira-issue` for one task |
| SQLite | `ai_agent_tasks`, `ai_agent_logs` |

## Safety

- High-risk keywords require approval before run
- Draft PRs only; no auto-merge
- Secrets redacted in stored logs
