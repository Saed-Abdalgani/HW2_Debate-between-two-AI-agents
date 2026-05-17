"""Select/Write context slices — minimal transcript exposure per agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from debate.sdk.payloads import ContextMessage
from debate.shared.tokens import estimate_tokens


@dataclass
class RoleContext:
    own_last: str = ""
    opponent_last: str = ""
    summary: str = ""


@dataclass
class ContextStore:
    """In-memory rolling context per role (never the full transcript)."""

    roles: dict[str, RoleContext] = field(default_factory=dict)

    def _role(self, role: str) -> RoleContext:
        return self.roles.setdefault(role, RoleContext())

    def note_reply(self, role: str, text: str) -> None:
        self._role(role).own_last = text

    def note_opponent(self, role: str, text: str) -> None:
        self._role(role).opponent_last = text

    def select_context(self, role: str, turn_id: int) -> list[ContextMessage]:
        ctx = self._role(role)
        out: list[ContextMessage] = []
        if ctx.summary:
            out.append(ContextMessage(role="system", content=ctx.summary))
        if ctx.own_last:
            out.append(ContextMessage(role="assistant", content=ctx.own_last))
        if ctx.opponent_last:
            out.append(ContextMessage(role="user", content=ctx.opponent_last))
        if not out:
            out.append(
                ContextMessage(role="system", content=f"turn {turn_id}: awaiting first reply")
            )
        return out

    def set_summary(self, role: str, text: str) -> None:
        self._role(role).summary = text

    def truncate_summary(self, role: str, max_tokens: int, model: str) -> str:
        ctx = self._role(role)
        words = ctx.summary.split()
        while (
            words
            and estimate_tokens([{"role": "user", "content": " ".join(words)}], model) > max_tokens
        ):
            words.pop(0)
        ctx.summary = " ".join(words)
        return ctx.summary
