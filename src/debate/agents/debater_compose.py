"""LLM reply composition with Judge-proxied search tool calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from debate.agents.debater_prompt import parse_tool_query
from debate.sdk.payloads import (
    MessageType,
    PromptPayload,
    ReplyPayload,
    ToolCallPayload,
    ToolResultPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope

if TYPE_CHECKING:
    from debate.agents.debater_agent import DebaterAgent


class DebaterComposeMixin:
    """Compose debate replies — mixed into ``DebaterAgent``."""

    def compose_reply(self: DebaterAgent, prompt: PromptPayload, turn_id: int) -> ReplyPayload:
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

    def _proxy_search(self: DebaterAgent, query: str, turn_id: int) -> ToolResultPayload:
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

    def _sync_prompt_context(self: DebaterAgent, prompt: PromptPayload) -> None:
        if prompt.opponent_last:
            self.gk.context.note_opponent(self.role.value, prompt.opponent_last)
        for block in prompt.context:
            if block.role == "assistant":
                self.gk.context.note_reply(self.role.value, block.content)
            elif block.role == "user":
                self.gk.context.note_opponent(self.role.value, block.content)

    def _build_messages(
        self: DebaterAgent, prompt: PromptPayload, turn_id: int
    ) -> list[dict[str, Any]]:
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

    def _reply_payload(self: DebaterAgent, text: str, tin: int, tout: int) -> ReplyPayload:
        return ReplyPayload(text=text, tokens_in=tin, tokens_out=tout)

    def _non_empty(self: DebaterAgent, text: str, *, retried: bool = False) -> str:
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
