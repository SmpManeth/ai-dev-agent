"""Researcher agent: deep file inspection and root-cause analysis."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import get_settings, load_prompt
from models.state import AgentState, PlannerResult, ProposedChange, ResearchResult
from tools.file_tool import FileTool
from tools.search_tool import SearchTool


def _truncate(content: str, max_chars: int = 12_000) -> str:
    if len(content) <= max_chars:
        return content
    half = max_chars // 2
    return content[:half] + "\n\n... [truncated] ...\n\n" + content[-half:]


class ResearcherAgent:
    """Reads planned files and produces root-cause analysis."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self._file_tool = FileTool(repo_path)
        self._search_tool = SearchTool(repo_path)
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

    def _read_planned_files(self, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        for path in paths:
            try:
                contents[path] = self._file_tool.read_file(path)
            except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
                contents[path] = f"(unable to read: {exc})"
        return contents

    def _supplemental_search(self, task: str, files_read: dict[str, str]) -> str:
        """Run targeted searches based on task and file symbols."""
        terms = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", task)[:5]
        sections: list[str] = []
        for term in terms:
            matches = self._search_tool.search_code(None, term)
            if matches:
                sections.append(
                    f"### '{term}'\n{self._search_tool.format_matches(matches)}"
                )
        return "\n\n".join(sections) if sections else ""

    def run(self, state: AgentState) -> dict[str, Any]:
        """Execute researcher logic and return state updates."""
        planner_data = state.planner_result

        if planner_data is None:
            planner_data = PlannerResult(
                understanding=state.understanding or "No planner output",
                files_to_investigate=[],
                plan=state.plan,
            )

        paths = planner_data.files_to_investigate
        if not paths and state.files_found:
            # Last resort: first few source files
            paths = [
                f
                for f in state.files_found
                if f.endswith((".py", ".php", ".js", ".ts"))
            ][:3]

        files_read = self._read_planned_files(paths)
        file_sections = []
        for path, content in files_read.items():
            file_sections.append(
                f"### File: {path}\n```\n{_truncate(content)}\n```"
            )
        files_text = "\n\n".join(file_sections) if file_sections else "(no files read)"

        search_extra = self._supplemental_search(state.task_description, files_read)
        plan_text = "\n".join(f"- {step}" for step in (state.plan or planner_data.plan))

        system = load_prompt("researcher_prompt.txt")
        user_content = f"""## Bug description
{state.task_description}

## Planner understanding
{planner_data.understanding}

## Investigation plan
{plan_text}

## Files read
{files_text}

## Additional search context
{search_extra or "(none)"}

Respond with JSON: suspected_root_cause, evidence, recommended_fix.
"""

        llm = self._build_llm()
        structured = llm.with_structured_output(ResearchResult)
        result: ResearchResult = structured.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user_content),
            ]
        )

        proposed_changes = _derive_proposed_changes(result, paths)

        reasoning_parts = [
            "Researcher completed root-cause analysis.",
            f"Evidence items: {len(result.evidence)}.",
        ]
        reasoning = " ".join(reasoning_parts)
        full_reasoning = f"{state.reasoning}\n\n{reasoning}".strip()

        return {
            "current_step": "researched",
            "files_read": files_read,
            "research_result": result.model_dump(),
            "proposed_changes": [c.model_dump() for c in proposed_changes],
            "reasoning": full_reasoning,
        }


def _derive_proposed_changes(
    result: ResearchResult, file_paths: list[str]
) -> list[ProposedChange]:
    """Map research output to structured proposed changes (suggestions only)."""
    changes: list[ProposedChange] = []
    primary = file_paths[0] if file_paths else "unknown"
    changes.append(
        ProposedChange(
            file_path=primary,
            description=result.recommended_fix[:500],
            rationale=result.suspected_root_cause[:500],
        )
    )
    for path in file_paths[1:3]:
        changes.append(
            ProposedChange(
                file_path=path,
                description="Review for related changes per recommended fix",
                rationale="Listed in planner investigation set",
            )
        )
    return changes


def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for the researcher agent."""
    agent_state = AgentState.from_graph_dict(state)
    if agent_state.planner_result is None and state.get("planner_result"):
        agent_state.planner_result = PlannerResult.model_validate(
            state["planner_result"]
        )
    agent = ResearcherAgent(agent_state.repo_path)
    return agent.run(agent_state)
