"""Judge-stamped IPC envelope factory."""

from __future__ import annotations

from datetime import UTC, datetime

from debate.sdk.payloads import MessageType, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope


def judge_envelope(msg_type: MessageType, payload: object, *, turn_id: int) -> Envelope:
    """Build a Judge-stamped envelope with current UTC timestamp."""
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=msg_type,
        payload=payload,
    )
