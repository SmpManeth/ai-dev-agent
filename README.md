# AI Dev Agent

Local autonomous coding agent focused on **bug investigation** (Phase 1: read + plan only).

## Quick start

```bash
cd ai-dev-agent
uv sync --extra dev
cp .env.example .env   # add your OPENAI_API_KEY

uv run python main.py \
  --repo ./test-project \
  --task "Fix username validation message"
```

## Architecture

```
START → Planner → Researcher → Patcher → END
```

- **Planner**: git summary, file listing, keyword search → investigation plan
- **Researcher**: reads planned files → root cause + recommended fix + confidence
- **Patcher**: generates a proposed unified diff → saves to `outputs/` (does not modify the target repo)
- **Tools**: `FileTool`, `SearchTool`, `GitTool` (all read-only on the target repository)

The target repository is never modified. Patch artifacts are written under `ai-dev-agent/outputs/`:

| File | Description |
|------|-------------|
| `outputs/latest.patch` | Unified diff proposal |
| `outputs/latest_summary.md` | Human-readable patch summary |

Patches are skipped when research confidence is below 60%, risk is `high`, or paths touch forbidden areas (auth, payment, `.env`, migrations, etc.).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required for LLM agents |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model |
| `MAX_FILE_READ_BYTES` | `100000` | Per-file read cap |
| `MAX_FILES_TO_LIST` | `500` | Listing cap |
| `MAX_SEARCH_RESULTS` | `50` | Search hit cap |

## Tests

```bash
uv run pytest
```

Tool tests do not require an API key.
