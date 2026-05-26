"""Tool-call and event handling for judge ↔ child IPC."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from debate.agents.judge_child_envelope import judge_envelope
from debate.sdk.payloads import MessageType
from debate.sdk.schemas import Envelope

if TYPE_CHECKING:
    from debate.orchestration.supervisor import Supervisor
    from debate.shared.router import SkillRouter

_LOG_PREFIX = "[CHILD]"


def handle_tool_call(
    supervisor: Supervisor,
    role: str,
    router: SkillRouter,
    env: Envelope,
) -> None:
    payload = env.payload
    if not hasattr(payload, "skill") or not payload.skill:
        _log("invalid_tool_call", f"{role}: missing skill field")
        return
    result = router.dispatch(payload)  # type: ignore[arg-type]
    supervisor.send(
        role,
        judge_envelope(MessageType.TOOL_RESULT, result, turn_id=env.turn_id),
    )


def handle_event(env: Envelope) -> None:
    from debate.shared.budget import BudgetExceeded

    if not hasattr(env.payload, "name"):
        return
    if env.payload.name != "agent_error":
        return
    data = getattr(env.payload, "data", {}) or {}
    if data.get("error") == "BudgetExceeded":
        raise BudgetExceeded(data.get("detail", "child budget exhausted"), {})
    exc_name = data.get("error", "Unknown")
    detail = data.get("detail", "")
    raise RuntimeError(f"child agent_error ({exc_name}): {detail}")


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")
