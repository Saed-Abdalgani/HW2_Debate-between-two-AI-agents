"""Integration — stub Judge drives Pro/Con via Supervisor (P6.5)."""

from __future__ import annotations

import pytest
from debater_stub_helpers import drive_three_phases, stub_env

from debate.orchestration.supervisor import Supervisor
from debate.sdk.payloads import Role
from debate.shared.config import load_config


@pytest.fixture
def cfg():
    return load_config()


@pytest.mark.integration
def test_pro_three_replies(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_env(monkeypatch)
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        replies = drive_three_phases(sup, "pro", "AI helps humanity")
    finally:
        sup.shutdown_all()
    assert len(replies) == 3
    assert all(r.role == Role.PRO and r.payload.text for r in replies)  # type: ignore[union-attr]


@pytest.mark.integration
def test_con_three_replies(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_env(monkeypatch)
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        replies = drive_three_phases(sup, "con", "Remote work should stay default")
    finally:
        sup.shutdown_all()
    assert len(replies) == 3
    assert all(r.role == Role.CON for r in replies)
