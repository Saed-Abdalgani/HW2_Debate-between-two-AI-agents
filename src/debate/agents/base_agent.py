"""Abstract agent IPC loop — ping/pong, shutdown, stamped outbound envelopes."""

from __future__ import annotations

import sys
import traceback
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from debate.orchestration.errors import ChildDisconnectedError
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.payloads import EventPayload, MessageType, PongPayload, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper

if TYPE_CHECKING:
    from debate.shared.skills import LLMClientProto

CLEAN_EXIT = 0
AGENT_ERROR_EXIT = 2


class BaseAgent(ABC):
    """Owns the stdin/stdout JSON loop; subclasses implement ``handle`` only."""

    def __init__(
        self,
        role: Role,
        cfg: Config,
        gk: Gatekeeper,
        llm: LLMClientProto,
        reader: JsonPipeReader,
        writer: JsonPipeWriter,
    ) -> None:
        self.role = role
        self.cfg = cfg
        self.gk = gk
        self.llm = llm
        self._reader = reader
        self._writer = writer
        self._turn_id = 0

    def recv(self) -> Envelope:
        return self._reader.read_envelope()

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

    def run(self) -> int:
        while True:
            try:
                env = self.recv()
            except ChildDisconnectedError:
                return CLEAN_EXIT
            self._turn_id = env.turn_id
            if env.type == MessageType.PING:
                self._reply_pong(env.turn_id)
                continue
            if env.type == MessageType.SHUTDOWN:
                return CLEAN_EXIT
            try:
                self.handle(env)
            except Exception as exc:
                self._emit_agent_error(exc)
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
                    data={"error": type(exc).__name__, "detail": str(exc)[:500]},
                ),
            )
        )

    @abstractmethod
    def handle(self, env: Envelope) -> None:
        """Handle one inbound envelope (never ``ping`` or ``shutdown``)."""
