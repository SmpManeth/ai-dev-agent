#!/usr/bin/env bash
# Install a user crontab line to run the Laravel scheduler every minute.
set -euo pipefail

DASHBOARD="$(cd "$(dirname "$0")/../dashboard" && pwd)"
PHP_BIN="${PHP_BIN:-php}"

LINE="* * * * * cd \"$DASHBOARD\" && $PHP_BIN artisan schedule:run >> storage/logs/cron.log 2>&1"

echo "Add this line to your crontab (crontab -e):"
echo ""
echo "$LINE"
echo ""
echo "Ensure AI_AGENT_SCHEDULE_ENABLED=true in dashboard/.env"
