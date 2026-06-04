"""Isolate production hardening policy during tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_hardening_policy(monkeypatch):
    root = Path(__file__).resolve().parent.parent
    monkeypatch.setenv(
        "AI_AGENT_HARDENING_CONFIG",
        str(root / "hardening.defaults.json"),
    )
    from tools.security_policy import reload_hardening_policy

    reload_hardening_policy()
    yield
    reload_hardening_policy()
