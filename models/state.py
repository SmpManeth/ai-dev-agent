"""Pydantic state models for the bug-fix agent workflow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]


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
    confidence: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Confidence (0-100) that the root cause and fix are correct",
    )


class PatchResult(BaseModel):
    """Structured output from the patch proposal agent."""

    proposed_changes: str = Field(
        description="Narrative description of what the patch changes"
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="Repository-relative paths touched by the diff",
    )
    risk_level: RiskLevel = Field(description="low, medium, or high")
    patch_summary: str = Field(description="Short summary of the proposed patch")
    unified_diff: str = Field(
        default="",
        description="Unified diff text (empty when patch not generated)",
    )


class AgentState(BaseModel):
    """Full agent state persisted across workflow steps."""

    repo_path: str
    task_description: str
    apply_patch: bool = False
    run_tests: bool = False
    do_commit: bool = False
    branch_name: str = ""
    create_pr: bool = False
    update_jira: bool = False

    # Jira context (Step 7)
    jira_issue_key: str = ""
    jira_summary: str = ""
    jira_description: str = ""
    progress_json_path: str = ""

    files_found: list[str] = Field(default_factory=list)
    files_read: dict[str, str] = Field(default_factory=dict)

    plan: list[str] = Field(default_factory=list)
    reasoning: str = ""

    current_step: str = "initialized"

    # Enriched artifacts (Step 1)
    repo_summary: str = ""
    repo_summary_display: str = ""
    planner_result: PlannerResult | None = None
    research_result: ResearchResult | None = None
    understanding: str = ""

    # Step 2 — patch proposal (not applied to repo)
    proposed_changes: str = ""
    affected_files: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "high"
    patch_summary: str = ""
    unified_diff: str = ""
    patch_file_path: str = ""
    patch_result: PatchResult | None = None

    # Step 3 — local apply (no commit)
    patch_applied: bool = False
    changed_files: list[str] = Field(default_factory=list)
    git_diff: str = ""
    patch_apply_status: str = ""
    patch_apply_error: str = ""
    patch_validation_status: str = ""

    # Step 4 — validation + self-fix loop
    validation_status: str = ""
    validation_commands: list[str] = Field(default_factory=list)
    validation_output: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    fix_verification_status: str = ""
    fix_verification_confidence: int = 0
    fix_verification_output: str = ""
    fix_verification_errors: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    self_fix_history: list[dict[str, Any]] = Field(default_factory=list)

    # Step 5 — local branch + commit (no push)
    branch_created: bool = False
    commit_created: bool = False
    commit_hash: str = ""
    commit_message: str = ""
    commit_status: str = ""
    commit_error: str = ""
    original_branch: str = ""

    # Step 6 — GitHub push + draft PR (no merge)
    branch_pushed: bool = False
    push_status: str = ""
    push_error: str = ""
    pr_created: bool = False
    pr_url: str = ""
    pr_number: int = 0
    pr_status: str = ""
    pr_error: str = ""

    # Step 7 — Jira update after PR
    jira_comment_added: bool = False
    jira_transitioned: bool = False
    jira_update_status: str = ""
    jira_error: str = ""

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
    apply_patch: bool
    run_tests: bool
    do_commit: bool
    branch_name: str
    create_pr: bool
    update_jira: bool
    jira_issue_key: str
    jira_summary: str
    jira_description: str
    progress_json_path: str
    files_found: list[str]
    files_read: dict[str, str]
    plan: list[str]
    reasoning: str
    current_step: str
    repo_summary: str
    repo_summary_display: str
    planner_result: dict[str, Any] | None
    research_result: dict[str, Any] | None
    understanding: str
    proposed_changes: str
    affected_files: list[str]
    risk_level: str
    patch_summary: str
    unified_diff: str
    patch_file_path: str
    patch_result: dict[str, Any] | None
    patch_applied: bool
    changed_files: list[str]
    git_diff: str
    patch_apply_status: str
    patch_apply_error: str
    patch_validation_status: str
    validation_status: str
    validation_commands: list[str]
    validation_output: str
    validation_errors: list[str]
    fix_verification_status: str
    fix_verification_confidence: int
    fix_verification_output: str
    fix_verification_errors: list[str]
    retry_count: int
    max_retries: int
    self_fix_history: list[dict[str, Any]]
    branch_created: bool
    commit_created: bool
    commit_hash: str
    commit_message: str
    commit_status: str
    commit_error: str
    original_branch: str
    branch_pushed: bool
    push_status: str
    push_error: str
    pr_created: bool
    pr_url: str
    pr_number: int
    pr_status: str
    pr_error: str
    jira_comment_added: bool
    jira_transitioned: bool
    jira_update_status: str
    jira_error: str
