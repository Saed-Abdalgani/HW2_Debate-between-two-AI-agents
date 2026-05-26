"""Pydantic config models (split from ``config`` to keep file size small)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConfigError(Exception):
    """All validation failures from a single load attempt."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1)
    max_results: int = Field(ge=1, le=50)
    cache: bool


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rounds: int = Field(ge=1)
    model: str = Field(min_length=1)
    temperature: float = Field(gt=0, le=2)
    max_tokens_per_turn: int = Field(ge=1)
    max_tokens_per_debate: int = Field(ge=1)
    max_usd_per_debate: float = Field(gt=0)
    max_requests_per_minute: int = Field(ge=1)
    heartbeat_sec: float = Field(gt=0)
    heartbeat_timeout_sec: float = Field(gt=0)
    heartbeat_max_consecutive_misses: int = Field(ge=1)
    child_terminate_grace_sec: float = Field(gt=0)
    recv_default_timeout_sec: float = Field(gt=0)
    max_restarts_per_child: int = Field(ge=0)
    max_message_bytes: int = Field(ge=1)
    max_clock_skew_sec: float = Field(ge=0)
    max_retries: int = Field(ge=0)
    retry_initial_delay_sec: float = Field(ge=0)
    retry_jitter_sec: float = Field(ge=0)
    token_drift_warn_threshold: float = Field(ge=0, le=1)
    summary_max_tokens: int = Field(ge=1)
    search_cache_max_entries: int = Field(ge=1)
    score_model: str = Field(min_length=1)
    judge_model: str = Field(min_length=1)
    http_timeout_sec: float = Field(gt=0)
    search_snippet_max_chars: int = Field(ge=1)
    max_tool_calls_per_turn: int = Field(ge=0, default=2)
    max_tokens_for_verdict: int = Field(ge=1, default=1200)
    round_eval_max_tokens: int = Field(ge=1, default=900)
    search: SearchConfig
