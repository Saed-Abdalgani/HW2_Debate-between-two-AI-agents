"""Unit tests — envelope validation, verdict schema, and defensive checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from schema_helpers import LIMITS, NOW, make_envelope

from debate.sdk.payloads import MessageType, PingPayload, ReplyPayload, Role
from debate.sdk.schemas import (
    SCHEMA_VERSION,
    ClockSkewError,
    Envelope,
    MessageTooLargeError,
    SchemaError,
    SchemaLimits,
    SchemaVersionError,
    VerdictValidationError,
    parse_envelope,
    serialize,
    validate_verdict,
)


@pytest.mark.unit
def test_reject_mismatched_version() -> None:
    env = make_envelope(MessageType.PING, PingPayload())
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
    env = make_envelope(
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
