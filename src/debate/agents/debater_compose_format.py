"""Search-hit formatting and IPC-safe reply text for debater compose."""

from __future__ import annotations

import sys

from debate.sdk.payloads import ToolResultPayload

_COMPOSE_LOG_PREFIX = "[COMPOSE]"


def format_search_hits(payload: ToolResultPayload) -> str:
    """Format tool search hits for the LLM follow-up message."""
    lines = ["Search results:"]
    for hit in payload.hits:
        lines.append(f"- {hit.title}: {hit.snippet[:200]}")
    if payload.cached:
        lines.append("(cached)")
    return "\n".join(lines)


def ipc_safe_reply_text(text: str) -> str:
    """Collapse newlines so IPC JSON lines stay single-line framed."""
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def log_compose_tool(role: str, turn_id: int, query: str, hit_count: int) -> None:
    sys.stderr.write(
        f"{_COMPOSE_LOG_PREFIX} {role} turn={turn_id} "
        f"tool_call query={query[:60]!r} hits={hit_count}\n"
    )
