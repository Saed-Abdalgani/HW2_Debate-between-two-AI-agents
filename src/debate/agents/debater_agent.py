"""Debater agent — stance via template; search proxied through Judge IPC."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import httpx

from debate.agents.base_agent import BaseAgent
from debate.agents.stub_llm import stub_from_env
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.llm_client import LLMClient
from debate.sdk.payloads import (
    InitPayload,
    MessageType,
    PromptPayload,
    ReplyPayload,
    Role,
    ToolCallPayload,
    ToolResultPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope, SchemaLimits
from debate.shared.config import Config, load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.secrets import get_env
from debate.shared.skills import LLMClientProto

_ROOT = Path(__file__).resolve().parents[3]
_DEBATER_PROMPT = _ROOT / "config" / "prompts" / "debater.system.txt"
_TOOL_PREFIX = "TOOL:search:"
Stance = Literal["pro", "con"]


def load_debater_system(stance: str, motion: str) -> str:
    return _DEBATER_PROMPT.read_text(encoding="utf-8").format(stance=stance, motion=motion)


def parse_tool_query(text: str) -> str | None:
    line = text.strip().split("\n", 1)[0]
    if line.startswith(_TOOL_PREFIX):
        query = line[len(_TOOL_PREFIX) :].strip()
        return query or None
    return None


class DebaterAgent(BaseAgent):
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

    def compose_reply(self, prompt: PromptPayload, turn_id: int) -> ReplyPayload:
        self._sync_prompt_context(prompt)
        messages = self._build_messages(prompt, turn_id)
        tokens_in = tokens_out = 0
        for tool_calls in range(self.cfg.max_tool_calls_per_turn + 2):
            estimate = self.gk.build_estimate(messages, self.cfg.model)
            result = self.gk.execute(
                lambda msgs=messages: self.llm.chat(msgs, self.cfg.max_tokens_per_turn),
                estimate=estimate,
                role=self.role.value,
                turn_id=turn_id,
                model=self.cfg.model,
            )
            tokens_in += result.tokens_in
            tokens_out += result.tokens_out
            query = parse_tool_query(result.text)
            if query is None:
                return self._reply_payload(self._non_empty(result.text), tokens_in, tokens_out)
            if tool_calls >= self.cfg.max_tool_calls_per_turn:
                return self._reply_payload(self._non_empty(result.text), tokens_in, tokens_out)
            hits = self._proxy_search(query, turn_id)
            messages.append({"role": "assistant", "content": result.text})
            messages.append({"role": "user", "content": self._format_hits(hits)})
        raise RuntimeError("compose_reply exhausted retry budget")

    def _proxy_search(self, query: str, turn_id: int) -> ToolResultPayload:
        self.send(
            Envelope(
                v=SCHEMA_VERSION,
                ts=datetime.now(UTC),
                turn_id=turn_id,
                role=self.role,
                type=MessageType.TOOL_CALL,
                payload=ToolCallPayload(
                    skill="search",
                    args={"query": query, "k": self.cfg.search.max_results},
                ),
            )
        )
        env = self.recv()
        if env.type != MessageType.TOOL_RESULT:
            raise ValueError(f"expected tool_result, got {env.type}")
        return env.payload  # type: ignore[return-value]

    def _sync_prompt_context(self, prompt: PromptPayload) -> None:
        if prompt.opponent_last:
            self.gk.context.note_opponent(self.role.value, prompt.opponent_last)
        for block in prompt.context:
            if block.role == "assistant":
                self.gk.context.note_reply(self.role.value, block.content)
            elif block.role == "user":
                self.gk.context.note_opponent(self.role.value, block.content)

    def _build_messages(self, prompt: PromptPayload, turn_id: int) -> list[dict[str, Any]]:
        ctx = self.gk.select_context(self.role.value, turn_id)
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt}]
        for block in ctx:
            messages.append({"role": block.role, "content": block.content})
        phase_note = f"Phase: {prompt.phase.value}."
        if prompt.opponent_last:
            phase_note += f" Opponent last: {prompt.opponent_last[:400]}"
        messages.append({"role": "user", "content": phase_note})
        return messages

    @staticmethod
    def _format_hits(payload: ToolResultPayload) -> str:
        lines = ["Search results:"]
        for hit in payload.hits:
            lines.append(f"- {hit.title}: {hit.snippet[:200]}")
        if payload.cached:
            lines.append("(cached)")
        return "\n".join(lines)

    def _reply_payload(self, text: str, tin: int, tout: int) -> ReplyPayload:
        return ReplyPayload(text=text, tokens_in=tin, tokens_out=tout)

    def _non_empty(self, text: str, *, retried: bool = False) -> str:
        cleaned = text.strip()
        if cleaned:
            return cleaned
        if retried:
            raise ValueError("empty LLM reply after retry")
        estimate = self.gk.build_estimate(
            [{"role": "user", "content": "Provide a non-empty debate reply."}], self.cfg.model
        )
        result = self.gk.execute(
            lambda: self.llm.chat(
                [{"role": "user", "content": "Provide a non-empty debate reply."}],
                self.cfg.max_tokens_per_turn,
            ),
            estimate=estimate,
            role=self.role.value,
            turn_id=self._turn_id,
            model=self.cfg.model,
        )
        return self._non_empty(result.text, retried=True)

    @classmethod
    def bootstrap(cls, *, llm: LLMClientProto | None = None) -> None:
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
        client = llm or _build_llm(cfg)
        role = Role.PRO if cls.STANCE == "pro" else Role.CON
        agent = cls(role, cfg, gk, client, reader, writer)
        sys.exit(agent.run())


def _build_llm(cfg: Config) -> LLMClientProto:
    stub = stub_from_env(get_env("DEBATE_STUB_LLM"))
    if stub is not None:
        return stub
    http = httpx.Client(timeout=cfg.http_timeout_sec)
    return LLMClient(cfg.model, cfg.temperature, http)
