"""Semantic review: does the applied patch actually fix the reported bug?"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import get_settings, load_agent_prompt
from models.state import AgentState, ResearchResult
from tools.llm_factory import build_agent_llm
from tools.diff_guard import validate_proposed_diff
from tools.llm_usage import track_from_response

MIN_VERIFIER_CONFIDENCE = 75


class FixVerifierResult(BaseModel):
    verdict: Literal["pass", "fail"] = Field(description="pass or fail")
    confidence: int = Field(ge=0, le=100, default=0)
    reasoning: str = Field(default="", description="Why the patch does or does not fix the bug")
    symptom_coverage: list[str] = Field(
        default_factory=list,
        description="Bug symptoms addressed by the patch",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Symptoms or acceptance criteria not addressed",
    )


class FixVerifierAgent:
    """LLM gate before commit/PR — blocks plausible-but-wrong fixes."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def run(self, state: AgentState) -> dict[str, Any]:
        if not state.apply_patch or state.patch_apply_status != "applied":
            return {
                "current_step": "fix_verify_skipped",
                "fix_verification_status": "skipped",
                "fix_verification_output": "Patch not applied.",
                "fix_verification_errors": [],
                "fix_verification_confidence": 0,
            }

        diff = (state.unified_diff or state.git_diff or "").strip()
        if not diff:
            return self._fail(
                state,
                reasoning="No diff available for review.",
                gaps=["Missing unified diff"],
                confidence=0,
            )

        research = state.research_result
        if isinstance(research, dict):
            research = ResearchResult.model_validate(research) if research else None

        research_block = ""
        if research:
            research_block = f"""
## Research root cause
{research.suspected_root_cause}

## Recommended fix
{research.recommended_fix}

## Research confidence
{research.confidence}%
"""

        prog_errors = validate_proposed_diff(
            diff,
            state.files_read,
            task_description=state.task_description,
        )
        if prog_errors:
            return self._fail(
                state,
                reasoning="Programmatic guard: " + "; ".join(prog_errors),
                gaps=prog_errors,
                confidence=95,
            )

        system = load_agent_prompt("fix_verifier_prompt.txt")
        user_content = f"""## Bug report
{state.task_description}

{research_block}

## Patch summary
{state.patch_summary or state.proposed_changes}

## Affected files
{", ".join(state.changed_files or state.affected_files) or "(unknown)"}

## Validation output
{(state.validation_output or "(none)")[:6000]}

## Applied unified diff
```diff
{diff[:20000]}
```

Respond with JSON: verdict, confidence, reasoning, symptom_coverage, gaps.
"""

        llm = build_agent_llm("researcher", self._settings)
        structured = llm.with_structured_output(FixVerifierResult)
        result: FixVerifierResult = structured.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user_content),
            ]
        )
        track_from_response(
            result,
            task_key=state.jira_issue_key,
            model=self._settings.openai_model_for("researcher"),
        )

        if result.verdict == "pass" and result.confidence >= MIN_VERIFIER_CONFIDENCE:
            return self._pass(state, result)

        return self._fail(
            state,
            reasoning=result.reasoning,
            gaps=result.gaps,
            confidence=result.confidence,
            symptoms=result.symptom_coverage,
        )

    def _pass(self, state: AgentState, result: FixVerifierResult) -> dict[str, Any]:
        reasoning = (
            f"{state.reasoning}\n\n"
            f"FixVerifier: PASS ({result.confidence}%) — {result.reasoning[:300]}"
        ).strip()
        return {
            "current_step": "fix_verified",
            "fix_verification_status": "passed",
            "fix_verification_confidence": result.confidence,
            "fix_verification_output": result.reasoning,
            "fix_verification_errors": [],
            "reasoning": reasoning,
        }

    def _fail(
        self,
        state: AgentState,
        *,
        reasoning: str,
        gaps: list[str],
        confidence: int,
        symptoms: list[str] | None = None,
    ) -> dict[str, Any]:
        errors = list(gaps) or [reasoning or "Patch does not fix the reported bug."]
        if symptoms:
            errors.insert(0, f"Partial coverage only: {', '.join(symptoms[:5])}")
        output = reasoning
        if gaps:
            output += "\nGaps:\n" + "\n".join(f"- {g}" for g in gaps)

        full = (
            f"{state.reasoning}\n\n"
            f"FixVerifier: FAIL ({confidence}%) — {reasoning[:400]}"
        ).strip()
        return {
            "current_step": "fix_verify_failed",
            "fix_verification_status": "failed",
            "fix_verification_confidence": confidence,
            "fix_verification_output": output,
            "fix_verification_errors": errors,
            "validation_errors": list(state.validation_errors) + errors,
            "validation_output": (
                (state.validation_output or "")
                + "\n\n--- Fix verification ---\n"
                + output
            )[:12_000],
            "reasoning": full,
        }


def fix_verifier_node(state: dict[str, Any]) -> dict[str, Any]:
    return FixVerifierAgent().run(AgentState.from_graph_dict(state))
