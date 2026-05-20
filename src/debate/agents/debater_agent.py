"""Debater agent — stance via template; search proxied through Judge IPC.

Includes input validation, reply safety filtering, turn tracking,
and structured event logging for robust debate participation.
"""

from __future__ import annotations

import re
import sys
from typing import ClassVar

from debate.agents.base_agent import BaseAgent
from debate.agents.debater_bootstrap import DebaterBootstrapMixin
from debate.agents.debater_compose import DebaterComposeMixin
from debate.agents.debater_prompt import (
    Stance,
    load_debater_system,
    parse_tool_query,
    sanitise_motion,
)
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.payloads import InitPayload, MessageType, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.skills import LLMClientProto

__all__ = ["DebaterAgent", "Stance", "load_debater_system", "parse_tool_query"]

# Safety: patterns that should never appear in outbound replies.
_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
]

# Limits for input validation.
_MAX_MOTION_LEN = 1000
_MAX_ROUNDS = 50
_MAX_TOKENS_CEILING = 100_000
_MAX_CONSECUTIVE_TURNS = 200


class DebaterAgent(DebaterComposeMixin, DebaterBootstrapMixin, BaseAgent):
    """Child debater — only ``STANCE`` differs in Pro/Con subclasses."""

    STANCE: ClassVar[Stance]

    def __init__(
        self,
        role: Role,
        cfg: Config,
        gk: Gatekeeper,
        llm: LLMClientProto,
        reader: JsonPipeReader,
        writer: JsonPipeWriter,
    ) -> None:
        super().__init__(role, cfg, gk, llm, reader, writer)
        self._motion = ""
        self._system_prompt = ""
        self._turns_handled = 0

    def handle(self, env: Envelope) -> None:
        """Dispatch INIT and PROMPT messages with safety checks."""
        if env.type == MessageType.INIT:
            self._on_init(env.payload)  # type: ignore[arg-type]
            return
        if env.type == MessageType.PROMPT:
            self._turns_handled += 1
            if self._turns_handled > _MAX_CONSECUTIVE_TURNS:
                raise RuntimeError(
                    f"exceeded {_MAX_CONSECUTIVE_TURNS} turns — possible infinite loop"
                )
            reply = self.compose_reply(
                env.payload,
                env.turn_id,  # type: ignore[arg-type]
            )
            safe_text = _sanitise_reply(reply.text)
            reply = reply.model_copy(update={"text": safe_text})
            self.send(
                Envelope(
                    v=SCHEMA_VERSION,
                    ts=env.ts,
                    turn_id=env.turn_id,
                    role=self.role,
                    type=MessageType.REPLY,
                    payload=reply,
                )
            )
            self._log("reply_sent", env.turn_id, len(safe_text))
            return
        raise ValueError(f"unexpected message type: {env.type}")

    def _on_init(self, payload: InitPayload) -> None:
        """Validate and apply the INIT payload."""
        if payload.stance != self.STANCE:
            raise ValueError(f"stance mismatch: expected {self.STANCE}, got {payload.stance}")
        _validate_init(payload)
        self._motion = sanitise_motion(payload.motion)
        self._system_prompt = load_debater_system(self.STANCE, self._motion)
        self._log("init_ok", 0, len(self._system_prompt))

    def status(self) -> dict[str, object]:
        """Return a snapshot of the agent's internal state."""
        return {
            "role": self.role.value,
            "stance": self.STANCE,
            "motion": self._motion[:80],
            "turns": self._turns_handled,
        }

    def _log(self, event: str, turn: int, detail: int) -> None:
        sys.stderr.write(f"[DEBATER] {self.role.value} {event} turn={turn} n={detail}\n")

    def __repr__(self) -> str:
        return f"<DebaterAgent stance={self.STANCE} turns={self._turns_handled}>"


def _validate_init(payload: InitPayload) -> None:
    """Reject clearly invalid init payloads."""
    if len(payload.motion) > _MAX_MOTION_LEN:
        raise ValueError("motion too long")
    if payload.rounds > _MAX_ROUNDS:
        raise ValueError(f"rounds={payload.rounds} exceeds {_MAX_ROUNDS}")
    if payload.max_tokens_per_turn > _MAX_TOKENS_CEILING:
        raise ValueError("max_tokens_per_turn unreasonably large")


def _sanitise_reply(text: str) -> str:
    """Redact any PII patterns found in outbound text."""
    result = text
    for pattern in _PII_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
