"""Debater agent — stance via template; search proxied through Judge IPC."""

from __future__ import annotations

from typing import ClassVar

from debate.agents.base_agent import BaseAgent
from debate.agents.debater_bootstrap import DebaterBootstrapMixin
from debate.agents.debater_compose import DebaterComposeMixin
from debate.agents.debater_prompt import Stance, load_debater_system, parse_tool_query
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.payloads import InitPayload, MessageType, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.skills import LLMClientProto

__all__ = ["DebaterAgent", "Stance", "load_debater_system", "parse_tool_query"]


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

    def handle(self, env: Envelope) -> None:
        if env.type == MessageType.INIT:
            self._on_init(env.payload)  # type: ignore[arg-type]
            return
        if env.type == MessageType.PROMPT:
            reply = self.compose_reply(env.payload, env.turn_id)  # type: ignore[arg-type]
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
            return
        raise ValueError(f"unexpected message type: {env.type}")

    def _on_init(self, payload: InitPayload) -> None:
        if payload.stance != self.STANCE:
            raise ValueError(f"stance mismatch: expected {self.STANCE}, got {payload.stance}")
        self._motion = payload.motion
        self._system_prompt = load_debater_system(self.STANCE, self._motion)
