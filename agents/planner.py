"""Planner agent: repository reconnaissance and investigation planning."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import get_settings, load_prompt
from models.state import AgentState, PlannerResult
from tools.file_tool import FileTool
from tools.git_tool import GitTool
from tools.search_tool import SearchTool


def _extract_keywords(task: str) -> list[str]:
    """Derive search terms from the bug description."""
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "of",
        "is",
        "are",
        "be",
        "fix",
        "bug",
        "issue",
        "error",
        "with",
        "when",
        "that",
        "this",
        "not",
        "should",
        "message",
        "validation",
    }
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", task)
    keywords: list[str] = []
    for token in tokens:
        lower = token.lower()
        if lower not in stop and lower not in keywords:
            keywords.append(lower)
    return keywords[:8] or [task[:40]]


class PlannerAgent:
    """Inspects the repo and produces an investigation plan."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self._file_tool = FileTool(repo_path)
        self._search_tool = SearchTool(repo_path)
        self._git_tool = GitTool(repo_path)
        self._settings = get_settings()

    def _build_llm(self) -> ChatOpenAI:
        if not self._settings.has_llm:
            raise RuntimeError(
                "OPENAI_API_KEY is required. Set it in the environment or .env file."
            )
        return ChatOpenAI(
            model=self._settings.openai_model,
            api_key=self._settings.openai_api_key,
            temperature=0.1,
        )

    def _gather_context(self, task: str) -> tuple[str, list[str], str]:
        """Collect git summary, file listing, and search hits."""
        summary = self._git_tool.get_repo_summary()
        repo_summary_text = summary.to_text()

        all_files = self._file_tool.list_files()
        # Prioritize likely source files in preview
        source_ext = {".py", ".php", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb"}
        prioritized = [f for f in all_files if any(f.endswith(ext) for ext in source_ext)]
        preview_files = prioritized[:80] if prioritized else all_files[:80]
        file_list_text = "\n".join(preview_files)
        if len(all_files) > len(preview_files):
            file_list_text += f"\n... ({len(all_files)} total files in repo)"

        search_sections: list[str] = []
        for keyword in _extract_keywords(task):
            matches = self._search_tool.search_code(None, keyword)
            if matches:
                search_sections.append(
                    f"### Search: '{keyword}'\n{self._search_tool.format_matches(matches)}"
                )
        search_text = "\n\n".join(search_sections) if search_sections else "(no keyword hits)"

        return repo_summary_text, all_files, file_list_text + "\n\n" + search_text

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute planner logic and return state updates."""
        repo_summary_text, all_files, search_context = self._gather_context(
            state.task_description
        )

        system = load_prompt("planner_prompt.txt")
        user_content = f"""## Bug description
{state.task_description}

## Repository summary
{repo_summary_text}

## File listing (sample)
{search_context}

Respond with JSON matching the schema: understanding, files_to_investigate, plan.
"""

        llm = self._build_llm()
        structured = llm.with_structured_output(PlannerResult)
        result: PlannerResult = structured.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user_content),
            ]
        )

        # Resolve file paths against actual repo files
        valid_files = set(all_files)
        resolved: list[str] = []
        for path in result.files_to_investigate:
            normalized = path.lstrip("./")
            if normalized in valid_files:
                resolved.append(normalized)
            elif self._file_tool.file_exists(normalized):
                resolved.append(normalized)

        if not resolved:
            # Fallback: top search hits
            for keyword in _extract_keywords(state.task_description):
                for match in self._search_tool.search_code(None, keyword)[:3]:
                    if match.file_path not in resolved:
                        resolved.append(match.file_path)

        result.files_to_investigate = resolved[:15]

        reasoning = (
            f"Planner analyzed {len(all_files)} files. "
            f"Identified {len(result.files_to_investigate)} files to investigate."
        )

        return {
            "current_step": "planned",
            "repo_summary": repo_summary_text,
            "files_found": all_files,
            "planner_result": result.model_dump(),
            "understanding": result.understanding,
            "plan": result.plan,
            "reasoning": reasoning,
        }


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for the planner agent."""
    agent_state = AgentState.from_graph_dict(state)
    agent = PlannerAgent(agent_state.repo_path)
    return agent.run(agent_state)
