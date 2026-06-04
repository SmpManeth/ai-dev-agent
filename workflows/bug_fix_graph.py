"""LangGraph workflow through GitHub draft PR (no merge)."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.github_pr import github_pr_node
from agents.jira_updater import jira_updater_node
from agents.git_committer import git_committer_node
from agents.patch_applier import patch_applier_node
from agents.patcher import patcher_node
from agents.planner import planner_node
from agents.researcher import researcher_node
from agents.fix_verifier import fix_verifier_node
from agents.self_fix import self_fix_node
from agents.test_runner import test_runner_node
from models.state import AgentState, GraphState
from tools.pipeline_progress import PipelinePhase, PipelineProgressReporter
from tools.security_policy import max_retries_for_workflow, max_runtime_seconds
from workflows.progress_wrapper import with_pipeline_progress


def _patch_was_applied(state: dict[str, Any]) -> bool:
    return (
        bool(state.get("apply_patch"))
        and state.get("patch_apply_status") == "applied"
    )


def _should_commit(state: dict[str, Any]) -> bool:
    return bool(state.get("do_commit")) and _patch_was_applied(state)


def _should_create_pr(state: dict[str, Any]) -> bool:
    return bool(state.get("create_pr")) and state.get("commit_status") == "committed"


def _route_after_patch_applier(
    state: dict[str, Any],
) -> Literal["test_runner", "git_committer", "self_fix", "__end__"]:
    apply_status = state.get("patch_apply_status") or ""
    if apply_status in ("apply_failed", "validation_failed"):
        retry = state.get("retry_count", 0)
        if retry < state.get("max_retries", 3):
            return "self_fix"
        return "__end__"
    if state.get("run_tests") and _patch_was_applied(state):
        return "test_runner"
    if _should_commit(state):
        return "git_committer"
    return "__end__"


def _route_after_test(
    state: dict[str, Any],
) -> Literal["self_fix", "fix_verifier", "git_committer", "__end__"]:
    status = state.get("validation_status")
    if status == "failed":
        retry = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        if retry < max_retries:
            return "self_fix"
        return "__end__"
    if _patch_was_applied(state) and state.get("run_tests"):
        if status in ("passed", "skipped"):
            return "fix_verifier"
    if _should_commit(state):
        if status in ("passed", "skipped") or not state.get("run_tests"):
            if status != "failed":
                return "git_committer"
    return "__end__"


def _route_after_fix_verifier(
    state: dict[str, Any],
) -> Literal["self_fix", "git_committer", "__end__"]:
    status = state.get("fix_verification_status")
    if status == "failed":
        retry = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        if retry < max_retries:
            return "self_fix"
        return "__end__"
    if _should_commit(state) and status == "passed":
        return "git_committer"
    return "__end__"


def _route_after_git_committer(
    state: dict[str, Any],
) -> Literal["github_pr", "__end__"]:
    if _should_create_pr(state):
        return "github_pr"
    return "__end__"


def build_bug_fix_graph() -> Any:
    """
    Build and compile the bug-fix investigation graph.

    Flow:
      planner → researcher → patcher → patch_applier
        → [test_runner → fix_verifier ↔ self_fix] → [git_committer] → [github_pr] → [jira_updater] → END
    """
    graph = StateGraph(GraphState)
    graph.add_node("planner", with_pipeline_progress("planner", planner_node))
    graph.add_node("researcher", with_pipeline_progress("researcher", researcher_node))
    graph.add_node("patcher", with_pipeline_progress("patcher", patcher_node))
    graph.add_node("patch_applier", with_pipeline_progress("patch_applier", patch_applier_node))
    graph.add_node("test_runner", with_pipeline_progress("test_runner", test_runner_node))
    graph.add_node("fix_verifier", with_pipeline_progress("fix_verifier", fix_verifier_node))
    graph.add_node("self_fix", with_pipeline_progress("self_fix", self_fix_node))
    graph.add_node("git_committer", with_pipeline_progress("git_committer", git_committer_node))
    graph.add_node("github_pr", with_pipeline_progress("github_pr", github_pr_node))
    graph.add_node("jira_updater", with_pipeline_progress("jira_updater", jira_updater_node))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "patcher")
    graph.add_edge("patcher", "patch_applier")
    graph.add_conditional_edges(
        "patch_applier",
        _route_after_patch_applier,
        {
            "test_runner": "test_runner",
            "git_committer": "git_committer",
            "self_fix": "self_fix",
            "__end__": END,
        },
    )
    graph.add_conditional_edges(
        "test_runner",
        _route_after_test,
        {
            "self_fix": "self_fix",
            "fix_verifier": "fix_verifier",
            "git_committer": "git_committer",
            "__end__": END,
        },
    )
    graph.add_conditional_edges(
        "fix_verifier",
        _route_after_fix_verifier,
        {
            "self_fix": "self_fix",
            "git_committer": "git_committer",
            "__end__": END,
        },
    )
    graph.add_edge("self_fix", "patch_applier")
    graph.add_conditional_edges(
        "git_committer",
        _route_after_git_committer,
        {"github_pr": "github_pr", "__end__": END},
    )
    graph.add_conditional_edges(
        "github_pr",
        _route_after_github_pr,
        {"jira_updater": "jira_updater", "__end__": END},
    )
    graph.add_edge("jira_updater", END)
    return graph.compile()


def _route_after_github_pr(
    state: dict[str, Any],
) -> Literal["jira_updater", "__end__"]:
    if state.get("update_jira") and state.get("jira_issue_key"):
        if state.get("pr_status") in ("created", "exists"):
            return "jira_updater"
    return "__end__"


def run_bug_fix_workflow(
    repo_path: str,
    task_description: str,
    *,
    apply_patch: bool = False,
    run_tests: bool = False,
    do_commit: bool = False,
    branch_name: str = "",
    create_pr: bool = False,
    update_jira: bool = False,
    jira_issue_key: str = "",
    jira_summary: str = "",
    jira_description: str = "",
    progress_json_path: str = "",
) -> AgentState:
    """Run the full workflow and return final AgentState."""
    reporter: PipelineProgressReporter | None = None
    if progress_json_path:
        reporter = PipelineProgressReporter(
            progress_json_path,
            issue_key=jira_issue_key,
            jira_summary=jira_summary,
        )
        reporter.write(PipelinePhase.QUEUED)

    initial = AgentState(
        repo_path=str(repo_path),
        task_description=task_description,
        apply_patch=apply_patch,
        run_tests=run_tests,
        do_commit=do_commit,
        branch_name=branch_name,
        create_pr=create_pr,
        update_jira=update_jira,
        jira_issue_key=jira_issue_key,
        jira_summary=jira_summary,
        jira_description=jira_description,
        progress_json_path=progress_json_path,
        current_step="started",
        max_retries=max_retries_for_workflow(),
    )
    app = build_bug_fix_graph()
    try:
        import signal

        def _timeout_handler(signum: int, frame: object) -> None:
            raise TimeoutError(
                f"Workflow exceeded max runtime ({max_runtime_seconds()}s)"
            )

        use_alarm = hasattr(signal, "SIGALRM")
        if use_alarm:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(max_runtime_seconds())
        try:
            final_dict = app.invoke(initial.to_graph_dict())
        finally:
            if use_alarm:
                signal.alarm(0)
        final = AgentState.from_graph_dict(final_dict)
        if reporter:
            if _is_success_state(final):
                reporter.complete_success(final.to_graph_dict())
            else:
                err = _failure_message(final)
                reporter.complete_failed(err, final.to_graph_dict())
        return final
    except Exception as exc:
        if reporter:
            reporter.complete_failed(str(exc))
        raise


def _is_success_state(state: AgentState) -> bool:
    if state.pr_status in ("created", "exists") and state.pr_url:
        return True
    if state.update_jira and state.jira_update_status == "updated":
        return True
    if state.commit_status == "committed" and not state.create_pr:
        return True
    if state.patch_applied and not state.do_commit:
        return True
    return False


def _failure_message(state: AgentState) -> str:
    if state.fix_verification_status == "failed":
        return (state.fix_verification_output or "Fix verification failed")[:500]
    return (
        state.patch_apply_error
        or state.commit_error
        or state.pr_error
        or state.jira_error
        or (state.validation_output or "")[:500]
        or f"Workflow ended at {state.current_step}"
    )
