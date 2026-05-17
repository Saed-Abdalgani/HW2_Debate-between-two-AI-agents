"""Heartbeat watchdog — ping/pong, respawn, restart counter (P5.4)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from debate.orchestration.errors import (
    ChildDisconnectedError,
    RecvTimeoutError,
    RestartsExhaustedError,
)
from debate.sdk.payloads import MessageType, PingPayload, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope


class _SupervisorLike(Protocol):
    def send(self, role: str, env: Envelope) -> None: ...
    def terminate(self, role: str, *, grace_sec: float | None = None) -> None: ...


_ROLES = ("pro", "con")


def _ping_envelope(turn_id: int) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=MessageType.PING,
        payload=PingPayload(),
    )


class Watchdog:
    """Background pinger; counts misses; fires ``on_miss`` then ``on_unrecoverable``."""

    def __init__(
        self,
        supervisor: _SupervisorLike,
        *,
        heartbeat_sec: float,
        max_consecutive_misses: int,
        max_restarts_per_child: int,
        pong_check: Callable[[str], bool],
        on_miss: Callable[[str], None],
        on_unrecoverable: Callable[[str], None] | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._heartbeat_sec = heartbeat_sec
        self._max_misses = max_consecutive_misses
        self._max_restarts = max_restarts_per_child
        self._pong_check = pong_check
        self._on_miss = on_miss
        self._on_unrecoverable = on_unrecoverable or (lambda _role: None)
        self._misses: dict[str, int] = dict.fromkeys(_ROLES, 0)
        self._restarts: dict[str, int] = dict.fromkeys(_ROLES, 0)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="watchdog", daemon=True)
        self._tick = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop.set()
        self._thread.join(timeout=join_timeout)

    def reset_role(self, role: str) -> None:
        self._misses[role] = 0

    def restarts(self, role: str) -> int:
        return self._restarts[role]

    def tick_once(self) -> None:
        """Single tick — exposed for deterministic unit tests."""
        self._tick += 1
        for role in _ROLES:
            self._send_ping(role)
            if self._pong_check(role):
                self._misses[role] = 0
                continue
            self._handle_miss(role)

    def _loop(self) -> None:
        while not self._stop.wait(self._heartbeat_sec):
            try:
                self.tick_once()
            except Exception:
                continue

    def _send_ping(self, role: str) -> None:
        try:
            self._supervisor.send(role, _ping_envelope(self._tick))
        except (ChildDisconnectedError, RecvTimeoutError, BrokenPipeError):
            return

    def _handle_miss(self, role: str) -> None:
        self._misses[role] += 1
        if self._misses[role] < self._max_misses:
            return
        self._misses[role] = 0
        self._restarts[role] += 1
        if self._restarts[role] > self._max_restarts:
            self._on_unrecoverable(role)
            raise RestartsExhaustedError(role, self._restarts[role])
        self._on_miss(role)
