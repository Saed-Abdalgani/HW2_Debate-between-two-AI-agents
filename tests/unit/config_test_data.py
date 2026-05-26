"""Valid ``debate.json`` fixture for config unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_DEBATE_CONFIG: dict[str, Any] = {
    "rounds": 10,
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens_per_turn": 800,
    "max_tokens_per_debate": 60000,
    "max_usd_per_debate": 1.5,
    "max_requests_per_minute": 30,
    "heartbeat_sec": 5,
    "heartbeat_timeout_sec": 3,
    "heartbeat_max_consecutive_misses": 2,
    "child_terminate_grace_sec": 2,
    "recv_default_timeout_sec": 30,
    "max_restarts_per_child": 2,
    "max_message_bytes": 65536,
    "max_clock_skew_sec": 300,
    "max_retries": 3,
    "retry_initial_delay_sec": 0.25,
    "retry_jitter_sec": 0.05,
    "token_drift_warn_threshold": 0.2,
    "summary_max_tokens": 512,
    "search_cache_max_entries": 128,
    "score_model": "gpt-4o-mini",
    "judge_model": "gpt-4o-mini",
    "http_timeout_sec": 30,
    "search_snippet_max_chars": 500,
    "max_tool_calls_per_turn": 2,
    "max_tokens_for_verdict": 1200,
    "round_eval_max_tokens": 900,
    "search": {"provider": "tavily", "max_results": 5, "cache": True},
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
