"""Debater child-process bootstrap — stdin/stdout IPC wiring.

Includes startup validation, graceful error handling, signal registration,
and configuration sanity checks before entering the main agent loop.
"""

from __future__ import annotations

import signal
import sys
from typing import TYPE_CHECKING

import httpx

from debate.agents.stub_llm import stub_from_env
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.llm_client import LLMClient, resolve_llm_base_url
from debate.sdk.payloads import Role
from debate.sdk.schemas import SchemaLimits
from debate.shared.config import Config, load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.secrets import get_env
from debate.shared.skills import LLMClientProto

if TYPE_CHECKING:
    from debate.agents.debater_agent import DebaterAgent

# Minimum reasonable values for critical config fields.
_MIN_TIMEOUT_SEC = 1.0
_MIN_MAX_TOKENS = 10
_MAX_TEMPERATURE = 2.0


def validate_config(cfg: Config) -> list[str]:
    """Return a list of config warnings (empty = all good)."""
    warnings: list[str] = []
    if cfg.http_timeout_sec < _MIN_TIMEOUT_SEC:
        warnings.append(f"http_timeout_sec={cfg.http_timeout_sec} below minimum {_MIN_TIMEOUT_SEC}")
    if cfg.max_tokens_per_turn < _MIN_MAX_TOKENS:
        warnings.append(
            f"max_tokens_per_turn={cfg.max_tokens_per_turn} below minimum {_MIN_MAX_TOKENS}"
        )
    if cfg.temperature > _MAX_TEMPERATURE:
        warnings.append(f"temperature={cfg.temperature} exceeds max {_MAX_TEMPERATURE}")
    if not cfg.model:
        warnings.append("model name is empty")
    return warnings


def build_debater_llm(cfg: Config) -> LLMClientProto:
    """Build the LLM client, preferring a test stub if set."""
    stub = stub_from_env(get_env("DEBATE_STUB_LLM"))
    if stub is not None:
        return stub
    http = httpx.Client(timeout=cfg.http_timeout_sec)
    return LLMClient(cfg.model, cfg.temperature, http, base_url=resolve_llm_base_url())


def _register_shutdown_signals() -> None:
    """Register signal handlers for graceful child shutdown."""

    def _handler(signum: int, _frame: object) -> None:
        _log_bootstrap("signal_received", f"signal={signum}")
        sys.exit(0)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _handler)


def _log_bootstrap(event: str, detail: str = "") -> None:
    """Structured stderr logging for bootstrap events."""
    msg = f"[BOOTSTRAP] {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")


class DebaterBootstrapMixin:
    """Process entry — mixed into ``DebaterAgent``."""

    @classmethod
    # pyrefly: ignore [invalid-annotation]
    def bootstrap(cls: type[DebaterAgent], *, llm: LLMClientProto | None = None) -> None:
        """Wire IPC, validate config, and enter the main agent loop."""
        _register_shutdown_signals()
        try:
            cfg = load_config()
        except Exception as exc:
            _log_bootstrap("config_load_failed", str(exc))
            sys.exit(2)
        warnings = validate_config(cfg)
        for w in warnings:
            _log_bootstrap("config_warning", w)
        limits = SchemaLimits(
            max_message_bytes=cfg.max_message_bytes,
            max_clock_skew_sec=cfg.max_clock_skew_sec,
        )
        # Raw stdin avoids BufferedReader filling its 8 KiB buffer
        # on Windows pipes.
        reader = JsonPipeReader(
            sys.stdin.buffer.raw,
            max_bytes=cfg.max_message_bytes,
            limits=limits,
        )
        writer = JsonPipeWriter(sys.stdout.buffer)
        gk = Gatekeeper(cfg)
        client = llm or build_debater_llm(cfg)
        role = Role.PRO if cls.STANCE == "pro" else Role.CON
        _log_bootstrap("agent_ready", f"role={role.value} model={cfg.model}")
        agent = cls(role, cfg, gk, client, reader, writer)
        try:
            exit_code = agent.run()
        except Exception as exc:
            _log_bootstrap("agent_crash", f"{type(exc).__name__}: {exc}")
            sys.exit(2)
        _log_bootstrap("agent_exit", f"code={exit_code}")
        sys.exit(exit_code)


def check_env_ready() -> list[str]:
    """Check that required environment state is valid for bootstrap."""
    import os

    issues: list[str] = []
    if not sys.stdin:
        issues.append("stdin is not available")
    if not sys.stdout:
        issues.append("stdout is not available")
    if os.environ.get("PYTHONUNBUFFERED") != "1":
        issues.append("PYTHONUNBUFFERED not set — may cause pipe stalls")
    return issues


def dump_config_summary(cfg: Config) -> dict[str, object]:
    """Return a serialisable config summary for logging."""
    return {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "rounds": cfg.rounds,
        "max_tokens_per_turn": cfg.max_tokens_per_turn,
        "http_timeout_sec": cfg.http_timeout_sec,
        "max_message_bytes": cfg.max_message_bytes,
    }
