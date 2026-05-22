"""Abstract agent IPC loop with rate limiting, lifecycle hooks, and health checks."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from debate.agents.base_agent_recv import BaseAgentRecvSendMixin
from debate.agents.base_agent_run import (
    AGENT_ERROR_EXIT,
    CLEAN_EXIT,
    BaseAgentRunMixin,
)
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.payloads import Role
from debate.sdk.schemas import Envelope
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper

if TYPE_CHECKING:
    from debate.shared.skills import LLMClientProto


class BaseAgent(BaseAgentRecvSendMixin, BaseAgentRunMixin, ABC):
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

    def on_start(self) -> None:
        pass

    def on_shutdown(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return self._healthy

    def messages_processed(self) -> int:
        return self._msg_count

    @abstractmethod
    def handle(self, env: Envelope) -> None:
        """Handle one inbound envelope (never ``ping`` or ``shutdown``)."""


__all__ = ["AGENT_ERROR_EXIT", "CLEAN_EXIT", "BaseAgent"]
