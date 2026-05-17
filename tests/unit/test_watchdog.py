"""Unit tests — Watchdog miss + respawn + exhaustion (P5.4)."""

from __future__ import annotations

import pytest

from debate.orchestration.errors import RestartsExhaustedError
from debate.orchestration.watchdog import Watchdog
from debate.sdk.schemas import Envelope


class _FakeSupervisor:
    def __init__(self) -> None:
        self.sent: list[tuple[str, Envelope]] = []
        self.terminated: list[str] = []

    def send(self, role: str, env: Envelope) -> None:
        self.sent.append((role, env))

    def terminate(self, role: str, *, grace_sec: float | None = None) -> None:
        self.terminated.append(role)


def _wd(
    *,
    pong_check,
    on_miss,
    max_misses: int = 2,
    max_restarts: int = 2,
    on_unrecoverable=None,
) -> tuple[Watchdog, _FakeSupervisor]:
    sup = _FakeSupervisor()
    wd = Watchdog(
        sup,
        heartbeat_sec=0.01,
        max_consecutive_misses=max_misses,
        max_restarts_per_child=max_restarts,
        pong_check=pong_check,
        on_miss=on_miss,
        on_unrecoverable=on_unrecoverable,
    )
    return wd, sup


@pytest.mark.unit
def test_miss_callback_fires_after_max_misses() -> None:
    calls: list[str] = []
    wd, sup = _wd(pong_check=lambda role: False, on_miss=calls.append, max_misses=2)
    wd.tick_once()
    assert calls == []
    wd.tick_once()
    assert calls.count("pro") == 1
    assert calls.count("con") == 1
    assert sup.sent  # pings sent


@pytest.mark.unit
def test_reset_role_clears_counter() -> None:
    def pong(role: str) -> bool:
        return False

    calls: list[str] = []
    wd, _sup = _wd(pong_check=pong, on_miss=calls.append, max_misses=2)
    wd.tick_once()
    wd.reset_role("pro")
    wd.reset_role("con")
    wd.tick_once()
    assert calls == []


@pytest.mark.unit
def test_pong_resets_miss_counter() -> None:
    sequence = iter([False, True, False, False])

    def pong(role: str) -> bool:
        if role == "pro":
            return next(sequence)
        return True

    calls: list[str] = []
    wd, _sup = _wd(pong_check=pong, on_miss=calls.append, max_misses=2)
    wd.tick_once()
    wd.tick_once()
    wd.tick_once()
    assert calls == []
    wd.tick_once()
    assert calls == ["pro"]


@pytest.mark.unit
def test_restart_counter_tracks_misses() -> None:
    wd, _sup = _wd(
        pong_check=lambda role: False, on_miss=lambda _role: None, max_misses=1, max_restarts=5
    )
    wd.tick_once()
    assert wd.restarts("pro") == 1
    assert wd.restarts("con") == 1


@pytest.mark.unit
def test_restarts_exhausted_raises_after_limit() -> None:
    unrecoverable: list[str] = []
    wd, _sup = _wd(
        pong_check=lambda role: False,
        on_miss=lambda _role: None,
        max_misses=1,
        max_restarts=1,
        on_unrecoverable=unrecoverable.append,
    )
    wd.tick_once()
    with pytest.raises(RestartsExhaustedError):
        wd.tick_once()
    assert "pro" in unrecoverable or "con" in unrecoverable
