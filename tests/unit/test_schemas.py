"""Unit tests for IPC envelope schemas."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

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
    ClockSkewError,
    Envelope,
    MessageTooLargeError,
    SchemaError,
    SchemaLimits,
    SchemaVersionError,
    VerdictValidationError,
    load_schema_limits,
    parse_envelope,
    serialize,
    validate_verdict,
)

LIMITS = SchemaLimits(max_message_bytes=4096, max_clock_skew_sec=3600)
NOW = datetime.now(UTC)


def _envelope(
    msg_type: MessageType,
    payload,
    role: Role = Role.JUDGE,
    turn_id: int = 1,
) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=NOW,
        turn_id=turn_id,
        role=role,
        type=msg_type,
        payload=payload,
    )


def _roundtrip(env: Envelope) -> Envelope:
    return parse_envelope(serialize(env), limits=LIMITS)


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
    env = _envelope(msg_type, payload, role=reply_role)
    parsed = _roundtrip(env)
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
def test_reject_mismatched_version() -> None:
    env = _envelope(MessageType.PING, PingPayload())
    bad = json.loads(serialize(env))
    bad["v"] = 99
    with pytest.raises(SchemaVersionError):
        parse_envelope(json.dumps(bad), limits=LIMITS)


@pytest.mark.unit
def test_reject_oversize_line() -> None:
    tiny = SchemaLimits(max_message_bytes=32, max_clock_skew_sec=3600)
    line = "x" * 40
    with pytest.raises(MessageTooLargeError):
        parse_envelope(line, limits=tiny)


@pytest.mark.unit
def test_reject_verdict_tie() -> None:
    with pytest.raises(VerdictValidationError):
        validate_verdict(
            {
                "winner": "tie",
                "reasons": ["a" * 20, "b" * 20, "c" * 20],
                "scores": {"pro": 50, "con": 50},
            }
        )


@pytest.mark.unit
def test_reject_verdict_short_reasons() -> None:
    with pytest.raises(VerdictValidationError):
        validate_verdict(
            {
                "winner": "pro",
                "reasons": ["too short", "b" * 20, "c" * 20],
                "scores": {"pro": 80, "con": 40},
            }
        )


@pytest.mark.unit
def test_reject_verdict_fewer_than_three_reasons() -> None:
    with pytest.raises(VerdictValidationError):
        validate_verdict(
            {
                "winner": "con",
                "reasons": ["only one reason here!!!!"],
                "scores": {"pro": 40, "con": 80},
            }
        )


@pytest.mark.unit
def test_reject_extra_fields_in_payload() -> None:
    line = json.dumps(
        {
            "v": SCHEMA_VERSION,
            "ts": NOW.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "turn_id": 1,
            "role": "pro",
            "type": "reply",
            "payload": {
                "text": "ok",
                "tokens_in": 1,
                "tokens_out": 2,
                "extra": "nope",
            },
        }
    )
    with pytest.raises(SchemaError):
        parse_envelope(line, limits=LIMITS)


@pytest.mark.unit
def test_reject_newline_in_payload_on_serialize() -> None:
    env = _envelope(
        MessageType.REPLY,
        ReplyPayload(text="line1\nline2", tokens_in=1, tokens_out=2),
        role=Role.PRO,
    )
    with pytest.raises(SchemaError, match="newline"):
        serialize(env)


@pytest.mark.unit
def test_validate_verdict_happy_path() -> None:
    verdict = validate_verdict(
        {
            "winner": "con",
            "reasons": [
                "Superior use of cited evidence in rebuttals.",
                "Stronger framing of the core trade-off.",
                "More consistent engagement with opponent claims.",
            ],
            "scores": {"pro": 55, "con": 68},
        }
    )
    assert verdict.winner == "con"


@pytest.mark.unit
def test_reject_clock_skew() -> None:
    old = datetime(2020, 1, 1, tzinfo=UTC)
    env = Envelope(
        v=SCHEMA_VERSION,
        ts=old,
        turn_id=1,
        role=Role.JUDGE,
        type=MessageType.PING,
        payload=PingPayload(),
    )
    tight = SchemaLimits(max_message_bytes=4096, max_clock_skew_sec=1)
    with pytest.raises(ClockSkewError):
        parse_envelope(serialize(env), limits=tight)


@pytest.mark.unit
def test_serialized_line_is_single_line() -> None:
    env = _envelope(MessageType.PING, PingPayload())
    line = serialize(env)
    assert line.endswith("\n")
    assert line.count("\n") == 1


@pytest.mark.unit
def test_load_schema_limits_from_config() -> None:
    limits = load_schema_limits()
    assert limits.max_message_bytes == 65536
    assert limits.max_clock_skew_sec == 300


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
