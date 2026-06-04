"""Tests for command allow/block enforcement."""

import pytest

from tools.command_guard import assert_command_allowed
from tools.security_policy import SecurityViolation, load_policy_from_dict, reload_hardening_policy


def test_git_allowed(monkeypatch, tmp_path):
    path = tmp_path / "hardening.json"
    path.write_text(
        '{"allowed_command_prefixes":["git","composer"],"blocked_command_patterns":["sudo\\\\s"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_AGENT_HARDENING_CONFIG", str(path))
    reload_hardening_policy()
    assert_command_allowed(["git", "status"])


def test_sudo_blocked(monkeypatch, tmp_path):
    path = tmp_path / "hardening.json"
    path.write_text(
        '{"allowed_command_prefixes":["git"],"blocked_command_patterns":["sudo\\\\s"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_AGENT_HARDENING_CONFIG", str(path))
    reload_hardening_policy()

    with pytest.raises(SecurityViolation, match="Blocked"):
        assert_command_allowed(["sudo", "rm", "-rf", "/"])


def test_not_in_allowlist(monkeypatch, tmp_path):
    path = tmp_path / "hardening.json"
    path.write_text(
        '{"allowed_command_prefixes":["git","composer"],"blocked_command_patterns":[]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_AGENT_HARDENING_CONFIG", str(path))
    reload_hardening_policy()

    with pytest.raises(SecurityViolation, match="allowlist"):
        assert_command_allowed(["npm", "install"])
