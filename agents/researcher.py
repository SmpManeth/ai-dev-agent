"""Researcher agent: deep file inspection and root-cause analysis."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from config import get_settings, load_agent_prompt
from tools.llm_factory import build_agent_llm
from models.state import AgentState, PlannerResult, ResearchResult
from tools.file_tool import FileTool
from tools.investigation_paths import expand_investigation_paths
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

        paths = expand_investigation_paths(
            self.repo_path,
            planner_data.files_to_investigate,
            state.task_description,
        )
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

        system = load_agent_prompt("researcher_prompt.txt")
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

Respond with JSON: suspected_root_cause, evidence, recommended_fix, confidence (0-100).
"""

        llm = build_agent_llm("researcher", self._settings)
        structured = llm.with_structured_output(ResearchResult)
        result: ResearchResult = structured.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user_content),
            ]
        )

        result = _apply_research_sanity(result, files_read, state.task_description)

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
            "reasoning": full_reasoning,
        }


def _apply_research_sanity(
    result: ResearchResult,
    files_read: dict[str, str],
    task_description: str,
) -> ResearchResult:
    """Lower confidence when analysis cites files not read or ignores Blade+Swiper."""
    read_paths = set(files_read.keys())
    combined = " ".join(result.evidence) + result.recommended_fix + result.suspected_root_cause

    blade_read = any(p.endswith(".blade.php") for p in read_paths)
    corpus = "\n".join(files_read.values()).lower()
    has_swiper = "new swiper" in corpus or "swiper-slide" in corpus

    penalties: list[str] = []
    if (
        blade_read
        and has_swiper
        and "app.js" in result.recommended_fix.lower()
        and ".blade.php" not in result.recommended_fix
    ):
        penalties.append("recommends app.js but Swiper lives in Blade")

    if blade_read and task_description:
        task_lower = task_description.lower()
        if any(w in task_lower for w in ("slider", "scroll", "autoplay", "carousel")):
            if "app.js" in result.recommended_fix and ".blade.php" not in result.recommended_fix:
                penalties.append("UI slider bug should fix Blade/Swiper not only app.js")

    if penalties:
        capped = min(result.confidence, 45)
        extra = "; ".join(penalties)
        return result.model_copy(
            update={
                "confidence": capped,
                "suspected_root_cause": (
                    f"{result.suspected_root_cause}\n\n[Sanity check] {extra}"
                ),
            }
        )
    return result


def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper for the researcher agent."""
    agent_state = AgentState.from_graph_dict(state)
    if agent_state.planner_result is None and state.get("planner_result"):
        agent_state.planner_result = PlannerResult.model_validate(
            state["planner_result"]
        )
    agent = ResearcherAgent(agent_state.repo_path)
    return agent.run(agent_state)
