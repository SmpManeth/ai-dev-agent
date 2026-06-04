"""LangGraph workflow: Planner → Researcher (read/plan phase only)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.planner import planner_node
from agents.researcher import researcher_node
from models.state import AgentState, GraphState


def build_bug_fix_graph() -> Any:
    """
    Build and compile the bug-fix investigation graph.

    Flow: START → planner → researcher → END
    """
    graph = StateGraph(GraphState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", END)
    return graph.compile()


def run_bug_fix_workflow(repo_path: str, task_description: str) -> AgentState:
    """Run the full workflow and return final AgentState."""
    initial = AgentState(
        repo_path=str(repo_path),
        task_description=task_description,
        current_step="started",
    )
    app = build_bug_fix_graph()
    final_dict = app.invoke(initial.to_graph_dict())
    return AgentState.from_graph_dict(final_dict)
