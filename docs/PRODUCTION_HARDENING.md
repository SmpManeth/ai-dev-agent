# Production Hardening (Step 9)

## Features

| # | Feature | Implementation |
|---|---------|----------------|
| 1 | Docker sandbox | `tools/sandbox_runner.py`, `docker/Dockerfile.sandbox` |
| 2 | Command allow/block | `tools/command_guard.py` + `run_logged()` |
| 3 | Secret masking | `tools/secret_mask.py`, Laravel `AiAgentLogService` |
| 4 | Max execution timeout | `max_runtime_minutes` in policy; SIGALRM + subprocess timeout |
| 5 | Max retry limit | `max_retries` in policy → `bug_fix_graph.py` |
| 6 | Repo whitelist | `allowed_repositories` in policy |
| 7 | File restrictions | `patch_guard.py` + policy `blocked_file_patterns` |
| 8 | Token/cost tracking | `tools/cost_tracker.py`, `outputs/cost/*.json` |
| 9 | Task audit log | `outputs/audit/*.jsonl`, `ai_agent_audit_events` table |
| 10 | Kill switch | `agent_enabled` + middleware + Python `assert_agent_enabled()` |

## Settings UI

**Dashboard → Settings → Production hardening** (`/ai-agent/settings?section=production`)

Saves to `dashboard/storage/app/ai-agent-hardening.json`.

## Test sandbox safety

```bash
# Build image
cd docker && docker build -f Dockerfile.sandbox -t ai-dev-agent-sandbox:latest .

# Enable in UI or copy defaults to storage
# Set agent_enabled=true, sandbox_enabled=true

# Blocked command (should fail)
AI_AGENT_HARDENING_CONFIG=dashboard/storage/app/ai-agent-hardening.json \
  python -c "from tools.command_guard import assert_command_allowed; assert_command_allowed(['sudo','id'])"

# Kill switch
# Disable agent in UI, then:
python main.py --repo ./test-project --task "test"  # exits with kill switch message
```

## Known limitations

- LLM planner/researcher/patcher still run on the **host** (not inside Docker).
- Full workflow isolation would require wrapping `main.py` in a container with only workspace + API keys injected at runtime.
- `repo_sync` git calls bypass `run_logged` (still host git).
- SIGALRM timeout is Unix-only; other platforms rely on subprocess timeouts.
- Token counts depend on LangChain returning `response_metadata` (best-effort).
- Dashboard routes remain **unauthenticated** — add auth before production exposure.
