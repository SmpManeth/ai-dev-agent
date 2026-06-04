"""Model configuration for agent roles."""

from config import DEFAULT_OPENAI_MODEL, Settings


def test_default_model_is_gpt53_codex() -> None:
    assert DEFAULT_OPENAI_MODEL == "gpt-5.3-codex"
    s = Settings(_env_file=None, openai_api_key="x")
    assert s.openai_model == "gpt-5.3-codex"


def test_role_overrides() -> None:
    s = Settings(
        _env_file=None,
        openai_api_key="x",
        openai_model="gpt-5.3-codex",
        openai_model_planner="gpt-4o-mini",
        openai_model_patcher="gpt-5.3-codex",
    )
    assert s.openai_model_for("planner") == "gpt-4o-mini"
    assert s.openai_model_for("researcher") == "gpt-5.3-codex"
    assert s.openai_model_for("patcher") == "gpt-5.3-codex"
