# Production deployment

Host **Python agent + Laravel dashboard** on one Linux server. The agent is CLI-driven; the dashboard provides UI and cron scheduling.

## Components

| Component | Path | Role |
|-----------|------|------|
| Python venv | `/opt/ai-dev-agent/.venv` | Runs `main.py` |
| Root `.env` | `/opt/ai-dev-agent/.env` | `OPENAI_*`, `GITHUB_*`, `JIRA_*` |
| Workspaces | `/opt/ai-dev-agent/workspaces/` | Cloned target repos |
| Laravel | `/opt/ai-dev-agent/dashboard/` | UI + scheduler |
| Dashboard `.env` | `dashboard/.env` | `AI_AGENT_PROJECT_PATH`, `AI_AGENT_PYTHON_PATH` |

## Server requirements

- Linux, 2+ vCPU, 4–8 GB RAM recommended
- Python 3.11+, PHP 8.2+, Composer, Git
- Node/npm and PHP on server if target repos need frontend/PHP validation
- Optional: Docker for sandbox (`docs/PRODUCTION_HARDENING.md`)
- Outbound HTTPS: OpenAI, GitHub, Jira

Run as dedicated user `aiagent` (not root).

## Install

```bash
git clone <repo> /opt/ai-dev-agent
cd /opt/ai-dev-agent
uv sync --extra dev   # or python3 -m venv .venv && pip install -e .

cp .env.example .env    # configure keys
chmod 600 .env

cd dashboard
composer install --no-dev --optimize-autoloader
cp .env.example .env
php artisan key:generate
php artisan migrate --force
```

### Dashboard `.env` (production)

```env
APP_ENV=production
APP_DEBUG=false
APP_URL=https://ai-agent.example.com

AI_AGENT_PYTHON_PATH="/opt/ai-dev-agent/.venv/bin/python"
AI_AGENT_PROJECT_PATH="/opt/ai-dev-agent"

AI_AGENT_SCHEDULE_ENABLED=true
AI_AGENT_SCHEDULE_INTERVAL_MINUTES=15
AI_AGENT_JIRA_BATCH_MAX_TASKS=1
AI_AGENT_TIMEOUT=7200
```

Use MySQL/PostgreSQL instead of SQLite for multi-user production if needed.

## Nginx (dashboard)

Root: `dashboard/public`. Standard Laravel PHP-FPM config. Then:

```bash
php artisan config:cache && php artisan route:cache && php artisan view:cache
```

## Cron (required for automatic Jira batch)

```cron
* * * * * cd /opt/ai-dev-agent/dashboard && php artisan schedule:run >> storage/logs/cron.log 2>&1
```

Manual test:

```bash
php artisan ai-agent:run-jira-batch --force
```

## Security before go-live

1. **Authenticate** `/ai-agent` (VPN, IP allowlist, or Laravel auth) — routes are open by default.
2. Enable hardening: `agent_enabled`, repo whitelist — see `PRODUCTION_HARDENING.md`.
3. `chmod 600` on both `.env` files.
4. HTTPS only; `APP_DEBUG=false`.
5. Draft PRs only — no auto-merge in agent code.

## Minimal deployment (no dashboard)

```cron
*/15 * * * * cd /opt/ai-dev-agent && .venv/bin/python main.py \
  --from-jira --apply-patch --commit --create-pr --max-tasks=1 \
  >> /var/log/ai-dev-agent/batch.log 2>&1
```

## Cron-only alternative script

`scripts/run_jira_batch.sh` — same flags; set `AI_AGENT_DEFAULT_REPO_PATH` if not using auto-sync.

## Monitoring

- `dashboard/storage/logs/scheduler.log`, `storage/logs/cron.log`
- `outputs/audit/*.jsonl`, `outputs/cost/*.json` (if enabled)
- Disk usage under `workspaces/`
