"""Unit tests — envelope round-trip for every message type."""

from __future__ import annotations

import json

import pytest
from schema_helpers import LIMITS, NOW, make_envelope, roundtrip

from debate.sdk.payloads import (
    ContextMessage,
    EventPayload,
    InitPayload,
    MessageType,
    PingPayload,
    PongPayload,
    PromptPayload,
    ReplyPayload,
    Role,
    ScorePayload,
    SearchHit,
    ShutdownPayload,
    ToolCallPayload,
    ToolResultPayload,
    VerdictPayload,
    VerdictScores,
)
from debate.sdk.schemas import (
    SCHEMA_VERSION,
    SchemaError,
    load_schema_limits,
    parse_envelope,
    serialize,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("msg_type", "payload"),
    [
        (
            MessageType.INIT,
            InitPayload(motion="AI is good", stance="pro", rounds=10, max_tokens_per_turn=800),
        ),
        (
            MessageType.PROMPT,
            PromptPayload(
                phase="opening",
                context=[ContextMessage(role="system", content="debate")],
                opponent_last=None,
            ),
        ),
        (
            MessageType.REPLY,
            ReplyPayload(text="Argument here.", tokens_in=10, tokens_out=20),
        ),
        (
            MessageType.TOOL_CALL,
            ToolCallPayload(skill="search", args={"query": "climate data", "k": 3}),
        ),
        (
            MessageType.TOOL_RESULT,
            ToolResultPayload(
                skill="search",
                hits=[SearchHit(title="T", url="https://x", snippet="fact")],
                cached=False,
            ),
        ),
        (MessageType.PING, PingPayload()),
        (MessageType.PONG, PongPayload(turn_id=3)),
        (
            MessageType.SCORE,
            ScorePayload(for_role="pro", round=1, points=["clear"], score=7.5),
        ),
        (
            MessageType.VERDICT,
            VerdictPayload(
                winner="pro",
                reasons=[
                    "Strong evidence on economic impact throughout.",
                    "Better rebuttal of counter-arguments on jobs.",
                    "Clearer structure and signposting each round.",
                ],
                scores=VerdictScores(pro=72, con=61),
            ),
        ),
        (MessageType.EVENT, EventPayload(name="budget_exhausted", data={"usd": 1.5})),
        (MessageType.SHUTDOWN, ShutdownPayload(reason="done")),
    ],
)
def test_roundtrip_each_message_type(msg_type: MessageType, payload) -> None:
    reply_role = Role.PRO if msg_type == MessageType.REPLY else Role.JUDGE
    env = make_envelope(msg_type, payload, role=reply_role)
    parsed = roundtrip(env)
    assert parsed.type == msg_type
    assert parsed.payload == payload


@pytest.mark.unit
def test_reject_unknown_type() -> None:
    line = json.dumps(
        {
            "v": SCHEMA_VERSION,
            "ts": NOW.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "turn_id": 1,
            "role": "judge",
            "type": "not_a_type",
            "payload": {},
        }
    )
    with pytest.raises((SchemaError, ValueError)):
        parse_envelope(line, limits=LIMITS)


@pytest.mark.unit
def test_reject_invalid_json() -> None:
    with pytest.raises(SchemaError, match="invalid JSON"):
        parse_envelope("{not json", limits=LIMITS)


@pytest.mark.unit
def test_reject_invalid_role() -> None:
    line = json.dumps(
        {
            "v": SCHEMA_VERSION,
            "ts": NOW.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "turn_id": 1,
            "role": "audience",
            "type": "ping",
            "payload": {},
        }
    )
    with pytest.raises((SchemaError, ValueError)):
        parse_envelope(line, limits=LIMITS)


@pytest.mark.unit
def test_serialized_line_is_single_line() -> None:
    env = make_envelope(MessageType.PING, PingPayload())
    line = serialize(env)
    assert line.endswith("\n")
    assert line.count("\n") == 1


@pytest.mark.unit
def test_load_schema_limits_from_config() -> None:
    limits = load_schema_limits()
    assert limits.max_message_bytes == 65536
    assert limits.max_clock_skew_sec == 300
