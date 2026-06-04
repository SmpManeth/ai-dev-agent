"""Tests for patch artifact writer."""

from tools.patch_output import write_patch_artifacts


def test_write_patch_artifacts(tmp_path, monkeypatch) -> None:
    import config

    monkeypatch.setattr(config, "get_outputs_dir", lambda: tmp_path)

    patch_path, summary_path = write_patch_artifacts(
        unified_diff="--- a/foo.py\n+++ b/foo.py\n",
        patch_summary="Fix foo",
        task_description="Fix bug",
        root_cause="Bad foo",
        recommended_fix="Change foo",
        affected_files=["foo.py"],
        risk_level="low",
        proposed_changes="Update foo constant",
        confidence=90,
        skipped=False,
    )

    assert patch_path.exists()
    assert summary_path.exists()
    assert "foo.py" in patch_path.read_text(encoding="utf-8")
    assert "Fix foo" in summary_path.read_text(encoding="utf-8")
