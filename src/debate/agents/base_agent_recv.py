"""BaseAgent stdin/stdout envelope I/O."""

from __future__ import annotations

from datetime import UTC, datetime

from debate.sdk.schemas import SCHEMA_VERSION, Envelope


class BaseAgentRecvSendMixin:
    """Read/write envelopes for ``BaseAgent`` subclasses."""

    def recv(self) -> Envelope:
        env = self._reader.read_envelope()
        self._check_schema_version(env)
        return env

    def send(self, env: Envelope) -> None:
        stamped = Envelope(
            v=SCHEMA_VERSION,
            ts=datetime.now(UTC),
            turn_id=env.turn_id or self._turn_id,
            role=self.role,
            type=env.type,
            payload=env.payload,
        )
        self._writer.write_envelope(stamped)
