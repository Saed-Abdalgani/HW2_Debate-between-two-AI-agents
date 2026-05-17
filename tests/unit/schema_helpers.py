"""Shared helpers for schema unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from debate.sdk.payloads import MessageType, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope, SchemaLimits, parse_envelope, serialize

LIMITS = SchemaLimits(max_message_bytes=4096, max_clock_skew_sec=3600)
NOW = datetime.now(UTC)


def make_envelope(
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


def roundtrip(env: Envelope) -> Envelope:
    return parse_envelope(serialize(env), limits=LIMITS)
