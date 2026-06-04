"""Shared OpenAI chat model construction for agent roles."""

from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI

from config import Settings, get_settings

AgentLlmRole = Literal["planner", "researcher", "patcher"]

_ROLE_TEMPERATURE: dict[AgentLlmRole, float] = {
    "planner": 0.1,
    "researcher": 0.1,
    "patcher": 0.0,
}


def build_agent_llm(
    role: AgentLlmRole,
    settings: Settings | None = None,
) -> ChatOpenAI:
    """Build ChatOpenAI for planner, researcher, or patcher."""
    settings = settings or get_settings()
    if not settings.has_llm:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Set it in the environment or .env file."
        )
    return ChatOpenAI(
        model=settings.openai_model_for(role),
        api_key=settings.openai_api_key,
        temperature=_ROLE_TEMPERATURE[role],
    )
