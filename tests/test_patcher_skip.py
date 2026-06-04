"""Tests for patcher skip logic (no LLM)."""

from agents.patcher import PatcherAgent
from models.state import AgentState, ResearchResult


def test_patcher_skips_low_confidence(tmp_path, monkeypatch) -> None:
    import config

    out = tmp_path / "outputs"
    out.mkdir()
    monkeypatch.setattr(config, "get_outputs_dir", lambda: out)

    state = AgentState(
        repo_path=str(tmp_path),
        task_description="Fix x",
        files_read={"a.py": "x = 1\n"},
        research_result=ResearchResult(
            suspected_root_cause="x wrong",
            recommended_fix="fix x",
            confidence=40,
        ),
    )
    result = PatcherAgent().run(state)
    assert result["risk_level"] == "high"
    assert result["unified_diff"] == ""
    assert result["patch_file_path"]
