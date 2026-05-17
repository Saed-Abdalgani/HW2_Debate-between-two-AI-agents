"""Typed IPC payload models (Judge ↔ Child)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_FORBID = ConfigDict(extra="forbid")


class Role(StrEnum):
    JUDGE = "judge"
    PRO = "pro"
    CON = "con"


class MessageType(StrEnum):
    INIT = "init"
    PROMPT = "prompt"
    REPLY = "reply"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PING = "ping"
    PONG = "pong"
    SCORE = "score"
    VERDICT = "verdict"
    EVENT = "event"
    SHUTDOWN = "shutdown"


class DebatePhase(StrEnum):
    OPENING = "opening"
    ARGUE = "argue"
    CLOSING = "closing"


class _Payload(BaseModel):
    model_config = _FORBID


class ContextMessage(_Payload):
    role: str
    content: str


class InitPayload(_Payload):
    motion: str
    stance: Literal["pro", "con"]
    rounds: int
    max_tokens_per_turn: int


class PromptPayload(_Payload):
    phase: DebatePhase
    context: list[ContextMessage]
    opponent_last: str | None = None


class ReplyPayload(_Payload):
    text: str
    tokens_in: int
    tokens_out: int


class ToolCallPayload(_Payload):
    skill: Literal["search"]
    args: dict[str, Any]


class SearchHit(_Payload):
    title: str
    url: str
    snippet: str


class ToolResultPayload(_Payload):
    skill: Literal["search"]
    hits: list[SearchHit]
    cached: bool


class PingPayload(_Payload):
    pass


class PongPayload(_Payload):
    turn_id: int


class ScorePayload(_Payload):
    for_role: Literal["pro", "con"]
    round: int
    points: list[str]
    score: float


class VerdictScores(_Payload):
    pro: float = Field(ge=0, le=100)
    con: float = Field(ge=0, le=100)


class VerdictPayload(_Payload):
    winner: Literal["pro", "con"]
    reasons: list[str]
    scores: VerdictScores


class EventPayload(_Payload):
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class ShutdownPayload(_Payload):
    reason: str


PayloadModel = (
    InitPayload
    | PromptPayload
    | ReplyPayload
    | ToolCallPayload
    | ToolResultPayload
    | PingPayload
    | PongPayload
    | ScorePayload
    | VerdictPayload
    | EventPayload
    | ShutdownPayload
)

PAYLOAD_BY_TYPE: dict[MessageType, type[_Payload]] = {
    MessageType.INIT: InitPayload,
    MessageType.PROMPT: PromptPayload,
    MessageType.REPLY: ReplyPayload,
    MessageType.TOOL_CALL: ToolCallPayload,
    MessageType.TOOL_RESULT: ToolResultPayload,
    MessageType.PING: PingPayload,
    MessageType.PONG: PongPayload,
    MessageType.SCORE: ScorePayload,
    MessageType.VERDICT: VerdictPayload,
    MessageType.EVENT: EventPayload,
    MessageType.SHUTDOWN: ShutdownPayload,
}
