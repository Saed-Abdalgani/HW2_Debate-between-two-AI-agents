"""IPC wiring helpers for behavioral edge-case tests."""

from __future__ import annotations

import queue
from datetime import UTC, datetime

from debate.agents.con_agent import ConAgent
from debate.agents.pro_agent import ProAgent
from debate.sdk.payloads import MessageType, Role, SearchHit, ToolResultPayload
from debate.sdk.schemas import SCHEMA_VERSION, Envelope


def envelope(
    msg_type: MessageType,
    payload,
    *,
    turn_id: int = 1,
    role: Role = Role.JUDGE,
) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=role,
        type=msg_type,
        payload=payload,
    )


def wire_agent(
    agent: ProAgent | ConAgent,
    inbox: queue.Queue[Envelope],
    outbox: list[Envelope],
) -> None:
    def fake_send(env: Envelope) -> None:
        outbox.append(env)
        if env.type == MessageType.TOOL_CALL:
            inbox.put(
                envelope(
                    MessageType.TOOL_RESULT,
                    ToolResultPayload(
                        skill="search",
                        hits=[
                            SearchHit(
                                title="CIA World Factbook",
                                url="https://example.com/fr",
                                snippet="Capital: Paris.",
                            )
                        ],
                        cached=False,
                    ),
                    turn_id=env.turn_id,
                )
            )

    agent.recv = lambda: inbox.get(timeout=3)  # type: ignore[method-assign]
    agent.send = fake_send  # type: ignore[method-assign]
