#!/usr/bin/env bash
# Standalone cron entry (no Laravel). Runs one Jira batch cycle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

MAX_TASKS="${AI_AGENT_JIRA_BATCH_MAX_TASKS:-1}"
REPO_ARGS=()
if [[ -n "${AI_AGENT_DEFAULT_REPO_PATH:-}" ]]; then
  REPO_ARGS=(--repo "$AI_AGENT_DEFAULT_REPO_PATH")
fi

exec python3 main.py --from-jira "${REPO_ARGS[@]}" \
  --apply-patch --commit --create-pr \
  --max-tasks="$MAX_TASKS"
