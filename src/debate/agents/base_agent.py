"""Abstract agent IPC loop with rate limiting, lifecycle hooks, and health checks."""
from __future__ import annotations
import sys
import time
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
# Rate limiting: warn if more than this many messages per second.
_MSG_RATE_WARN_THRESHOLD = 50
_LOG_PREFIX = "[AGENT]"
class BaseAgent(ABC):
    """Owns the stdin/stdout JSON loop; subclasses implement ``handle``."""

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
        self._msg_count = 0
        self._start_time = time.monotonic()
        self._healthy = True
    def recv(self) -> Envelope:
        """Read one envelope, validating schema version."""
        env = self._reader.read_envelope()
        self._check_schema_version(env)
        return env
    def send(self, env: Envelope) -> None:
        """Stamp and write an outbound envelope."""
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
        """Main message loop with lifecycle hooks and rate monitoring."""
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
    # --- Lifecycle hooks (override in subclasses) ------------------
    def on_start(self) -> None:  # noqa: B027
        """Called once before the message loop begins."""
        pass
    def on_shutdown(self) -> None:  # noqa: B027
        """Called once when the agent is shutting down."""
        pass
    # --- Health & inspection ---------------------------------------
    def is_healthy(self) -> bool:
        """Return ``True`` if no unrecoverable error has occurred."""
        return self._healthy

    def messages_processed(self) -> int:
        """Total messages received since startup."""
        return self._msg_count
    # --- Internal --------------------------------------------------
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
            _log(
                "schema_mismatch",
                f"expected={SCHEMA_VERSION} got={env.v}",
            )

    def _check_rate(self) -> None:
        elapsed = time.monotonic() - self._start_time
        if elapsed > 0 and self._msg_count / elapsed > _MSG_RATE_WARN_THRESHOLD:
            _log("rate_warning", f"{self._msg_count / elapsed:.0f} msg/s")
    @abstractmethod
    def handle(self, env: Envelope) -> None:
        """Handle one inbound envelope (never ``ping`` or ``shutdown``)."""

def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")