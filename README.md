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
START → Planner → Researcher → END
```

- **Planner**: git summary, file listing, keyword search → investigation plan
- **Researcher**: reads planned files → root cause + recommended fix
- **Tools**: `FileTool`, `SearchTool`, `GitTool` (all read-only)

No file writes, patches, commits, or test execution in this phase.

Step 1 prints a plain-text **AI CODING AGENT REPORT** with task context, files investigated, root cause, recommended fix, confidence, and status `READY FOR PATCH GENERATION` when analysis is strong enough to proceed to patching (a future phase).

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
