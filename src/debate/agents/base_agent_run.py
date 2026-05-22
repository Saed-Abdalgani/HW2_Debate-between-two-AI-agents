"""BaseAgent main loop, pings, errors, rate checks."""

from __future__ import annotations

import sys
import time
import traceback
from datetime import UTC, datetime

from debate.orchestration.errors import ChildDisconnectedError
from debate.sdk.payloads import EventPayload, MessageType, PongPayload
from debate.sdk.schemas import SCHEMA_VERSION, Envelope

CLEAN_EXIT = 0
AGENT_ERROR_EXIT = 2
_MSG_RATE_WARN_THRESHOLD = 50
_LOG_PREFIX = "[AGENT]"


class BaseAgentRunMixin:
    """Message loop and health checks for ``BaseAgent``."""

    def run(self) -> int:
        self.on_start()
        while True:
            try:
                env = self.recv()
            except ChildDisconnectedError:
                self.on_shutdown()
                return CLEAN_EXIT
            self._turn_id = env.turn_id
            self._msg_count += 1
            self._check_rate()
            if env.type == MessageType.PING:
                self._reply_pong(env.turn_id)
                continue
            if env.type == MessageType.SHUTDOWN:
                self.on_shutdown()
                return CLEAN_EXIT
            try:
                self.handle(env)
            except Exception as exc:
                self._healthy = False
                self._emit_agent_error(exc)
                self.on_shutdown()
                return AGENT_ERROR_EXIT

    def _reply_pong(self, turn_id: int) -> None:
        self.send(
            Envelope(
                v=SCHEMA_VERSION,
                ts=datetime.now(UTC),
                turn_id=turn_id,
                role=self.role,
                type=MessageType.PONG,
                payload=PongPayload(turn_id=turn_id),
            )
        )

    def _emit_agent_error(self, exc: Exception) -> None:
        traceback.print_exc(file=sys.stderr)
        self.send(
            Envelope(
                v=SCHEMA_VERSION,
                ts=datetime.now(UTC),
                turn_id=self._turn_id,
                role=self.role,
                type=MessageType.EVENT,
                payload=EventPayload(
                    name="agent_error",
                    data={
                        "error": type(exc).__name__,
                        "detail": str(exc)[:500],
                    },
                ),
            )
        )

    def _check_schema_version(self, env: Envelope) -> None:
        if env.v != SCHEMA_VERSION:
            _log("schema_mismatch", f"expected={SCHEMA_VERSION} got={env.v}")

    def _check_rate(self) -> None:
        elapsed = time.monotonic() - self._start_time
        if elapsed > 0 and self._msg_count / elapsed > _MSG_RATE_WARN_THRESHOLD:
            _log("rate_warning", f"{self._msg_count / elapsed:.0f} msg/s")


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")
