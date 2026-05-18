"""Debater child-process bootstrap — stdin/stdout IPC wiring."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import httpx

from debate.agents.stub_llm import stub_from_env
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.llm_client import LLMClient
from debate.sdk.payloads import Role
from debate.sdk.schemas import SchemaLimits
from debate.shared.config import Config, load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.secrets import get_env
from debate.shared.skills import LLMClientProto

if TYPE_CHECKING:
    from debate.agents.debater_agent import DebaterAgent


def build_debater_llm(cfg: Config) -> LLMClientProto:
    stub = stub_from_env(get_env("DEBATE_STUB_LLM"))
    if stub is not None:
        return stub
    http = httpx.Client(timeout=cfg.http_timeout_sec)
    return LLMClient(cfg.model, cfg.temperature, http)


class DebaterBootstrapMixin:
    """Process entry — mixed into ``DebaterAgent``."""

    @classmethod
    def bootstrap(cls: type[DebaterAgent], *, llm: LLMClientProto | None = None) -> None:
        cfg = load_config()
        limits = SchemaLimits(
            max_message_bytes=cfg.max_message_bytes,
            max_clock_skew_sec=cfg.max_clock_skew_sec,
        )
        # Raw stdin avoids BufferedReader filling its 8 KiB buffer on Windows pipes.
        reader = JsonPipeReader(
            sys.stdin.buffer.raw,
            max_bytes=cfg.max_message_bytes,
            limits=limits,
        )
        writer = JsonPipeWriter(sys.stdout.buffer)
        gk = Gatekeeper(cfg)
        client = llm or build_debater_llm(cfg)
        role = Role.PRO if cls.STANCE == "pro" else Role.CON
        agent = cls(role, cfg, gk, client, reader, writer)
        sys.exit(agent.run())
