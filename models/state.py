"""Pydantic state models for the bug-fix agent workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class PlannerResult(BaseModel):
    """Structured output from the planner agent."""

    understanding: str = Field(description="Interpretation of the reported bug")
    files_to_investigate: list[str] = Field(
        default_factory=list,
        description="Repository-relative paths likely involved",
    )
    plan: list[str] = Field(
        default_factory=list,
        description="Ordered investigation steps",
    )


class ResearchResult(BaseModel):
    """Structured output from the researcher agent."""

    suspected_root_cause: str = Field(description="Most likely root cause")
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting observations from code inspection",
    )
    recommended_fix: str = Field(
        description="Concrete fix recommendation (no file writes yet)"
    )


class ProposedChange(BaseModel):
    """A suggested code change (read/plan phase only — not applied)."""

    file_path: str
    description: str
    rationale: str


class AgentState(BaseModel):
    """Full agent state persisted across workflow steps."""

    repo_path: str
    task_description: str

    files_found: list[str] = Field(default_factory=list)
    files_read: dict[str, str] = Field(default_factory=dict)

    plan: list[str] = Field(default_factory=list)
    reasoning: str = ""
    proposed_changes: list[ProposedChange] = Field(default_factory=list)

    current_step: str = "initialized"

    # Enriched artifacts
    repo_summary: str = ""
    planner_result: PlannerResult | None = None
    research_result: ResearchResult | None = None
    understanding: str = ""

    def to_graph_dict(self) -> dict[str, Any]:
        """Serialize for LangGraph invocation."""
        return self.model_dump(mode="json")

    @classmethod
    def from_graph_dict(cls, data: dict[str, Any]) -> AgentState:
        """Reconstruct from LangGraph state dict."""
        return cls.model_validate(data)


class GraphState(TypedDict, total=False):
    """LangGraph-compatible state schema (mirrors AgentState fields)."""

    repo_path: str
    task_description: str
    files_found: list[str]
    files_read: dict[str, str]
    plan: list[str]
    reasoning: str
    proposed_changes: list[dict[str, str]]
    current_step: str
    repo_summary: str
    planner_result: dict[str, Any] | None
    research_result: dict[str, Any] | None
    understanding: str
