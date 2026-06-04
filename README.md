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
START → Planner → Researcher → Patcher → PatchApplier → [TestRunner ↔ SelfFix] → [GitCommitter] → [GitHubPr] → [JiraUpdater] → END
```

- **Planner**: git summary, file listing, keyword search → investigation plan
- **Researcher**: reads planned files → root cause + recommended fix + confidence
- **Patcher**: generates a proposed unified diff → saves to `outputs/` (does not modify the target repo)
- **PatchApplier** (optional): validates and applies patch when `--apply-patch` is passed
- **Tools**: `FileTool`, `SearchTool`, `GitTool`, `PatchTool`

By default the target repository is not modified. With `--apply-patch`, the patch is applied locally but **not committed or pushed**.

```bash
python main.py --repo ./test-project --task "Fix username validation message" --apply-patch
python main.py --repo ./test-project --task "Fix username validation message" --apply-patch --run-tests
python main.py --repo ./test-project --revert-patch   # undo uncommitted apply
```

Step 4 runs validation (pytest, npm, composer, etc.) and up to **3** self-fix retries if tests fail.

```bash
python main.py --repo ./test-project --task "Fix username validation message" \
  --apply-patch --run-tests --commit \
  --branch-name ai-fix/username-validation-message
```

Step 5 creates a **local branch and commit only** (no push, no PR).

```bash
python main.py --repo . --task "Fix bug" --apply-patch --run-tests --commit --create-pr
```

Step 6 pushes the branch and opens a **draft PR** (requires `GITHUB_TOKEN` in `.env`). Does not merge or approve.

```bash
# Primary workflow: auto clone/pull repo + batch Jira ai-fix issues
python main.py --from-jira \
  --apply-patch --run-tests --commit --create-pr --max-tasks=1

# Repo is cloned to ./workspaces/{GITHUB_OWNER}/{GITHUB_REPO} when missing,
# then pulled to GITHUB_BASE_BRANCH before each run (GITHUB_TOKEN in .env).

# Dry run: list issues without modifying files
python main.py --from-jira --repo /path/to/your-repo --dry-run

# Optional: single issue for testing
python main.py --jira-issue AI-123 --repo ./test-project \
  --apply-patch --run-tests --commit --create-pr
```

Step 7 connects to Jira (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`, `JIRA_LABEL=ai-fix`), processes issues **one by one** (continues on failure), uses branch `ai-fix/{ISSUE-KEY}`, creates **draft PRs only**, comments PR URL on Jira, and moves to **In Review** when available. Skips issues that already have an open PR or existing branch.

Laravel dashboard: see `dashboard/README.md` — control panel with scheduler status, connection checks, and **Run Jira ai-fix Batch Now** (same as `main.py --from-jira`).

Patch artifacts are written under `ai-dev-agent/outputs/`:

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
