"""Gatekeeper — single choke-point for budget, retries, and context I/O."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar

from debate.sdk.payloads import ContextMessage
from debate.shared.budget import BudgetCaps, BudgetExceeded, Ledger, TransientProviderError, Usage
from debate.shared.config import Config
from debate.shared.context_store import ContextStore
from debate.shared.logger import Logger
from debate.shared.pricing import price
from debate.shared.tokens import estimate_tokens

T = TypeVar("T")


class Gatekeeper:
    """Wrap every external call; enforce caps before dispatch; reconcile after."""

    def __init__(
        self,
        cfg: Config,
        *,
        ledger: Ledger | None = None,
        context: ContextStore | None = None,
        logger: Logger | None = None,
        run_dir: Path | None = None,
    ) -> None:
        self.cfg = cfg
        self.ledger = ledger or Ledger()
        self.context = context or ContextStore()
        self.logger = logger
        self.run_dir = run_dir
        self._lock = RLock()
        # Single-call output ceiling must cover every path through this gatekeeper
        # (debater turns, judge score/summary, verdict) so preflight matches real max_tokens.
        max_out = max(
            cfg.max_tokens_per_turn,
            cfg.summary_max_tokens,
            cfg.max_tokens_for_verdict,
        )
        self._caps = BudgetCaps(
            max_tokens_per_turn=max_out,
            max_tokens_per_debate=cfg.max_tokens_per_debate,
            max_usd_per_debate=Decimal(str(cfg.max_usd_per_debate)),
            max_requests_per_minute=cfg.max_requests_per_minute,
        )

    def build_estimate(
        self,
        messages: list[dict[str, Any]],
        model: str,
        *,
        tokens_out: int | None = None,
    ) -> Usage:
        tin = estimate_tokens(messages, model)
        tout = tokens_out if tokens_out is not None else self.cfg.max_tokens_per_turn
        partial = Usage(tokens_in=tin, tokens_out=tout, requests=1)
        return Usage(
            tokens_in=tin,
            tokens_out=tout,
            usd=price(partial, model),
            requests=1,
        )

    def execute(
        self, fn: Callable[[], T], *, estimate: Usage, role: str, turn_id: int, model: str
    ) -> T:
        with self._lock:
            reason = self.ledger.would_exceed(estimate, self._caps)
            if reason:
                snap = self.ledger.snapshot()
                self._emit("budget_exhausted", role, turn_id, snap, reason=reason)
                raise BudgetExceeded(reason, snap)
        result = self._retry(fn, role, turn_id)
        actual = self._usage_from(result, estimate, model)
        self._warn_drift(estimate, actual, role, turn_id)
        with self._lock:
            self.ledger.add(actual)
            snap = self.ledger.snapshot()
        self._emit("gatekeeper_call", role, turn_id, snap, model=model)
        return result

    def select_context(self, role: str, turn_id: int) -> list[ContextMessage]:
        return self.context.select_context(role, turn_id)

    def write_summary(self, role: str, turn_id: int, text: str) -> None:
        self.context.set_summary(role, text)
        self.context.truncate_summary(role, self.cfg.summary_max_tokens, self.cfg.model)
        if self.run_dir:
            path = self.run_dir / f"summary.{role}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## turn {turn_id}\n{text}\n")
                fh.flush()

    def _usage_from(self, result: T, estimate: Usage, model: str) -> Usage:
        tin = int(getattr(result, "tokens_in", estimate.tokens_in))
        tout = int(getattr(result, "tokens_out", estimate.tokens_out))
        actual = Usage(tokens_in=tin, tokens_out=tout, requests=1)
        return Usage(tokens_in=tin, tokens_out=tout, usd=price(actual, model), requests=1)

    def _retry(self, fn: Callable[[], T], role: str, turn_id: int) -> T:
        delay = self.cfg.retry_initial_delay_sec
        jitter = self.cfg.retry_jitter_sec
        for attempt in range(self.cfg.max_retries + 1):
            try:
                return fn()
            except TransientProviderError as exc:
                with self._lock:
                    self.ledger.add(Usage(requests=1))
                self._emit(
                    "provider_transient",
                    role,
                    turn_id,
                    self.ledger.snapshot(),
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt >= self.cfg.max_retries:
                    raise
                time.sleep(delay * (2**attempt) + random.uniform(0, jitter))
        raise RuntimeError("retry loop exhausted")

    def _warn_drift(self, est: Usage, act: Usage, role: str, turn_id: int) -> None:
        if est.tokens_total == 0 or act.tokens_total == 0:
            return
        drift = abs(est.tokens_total - act.tokens_total) / act.tokens_total
        if drift > self.cfg.token_drift_warn_threshold and self.logger:
            self.logger.event(
                "token_estimate_drift",
                role=role,
                turn_id=turn_id,
                data={"estimate": est.tokens_total, "actual": act.tokens_total, "drift": drift},
            )

    def _emit(self, name: str, role: str, turn_id: int, snap: dict[str, Any], **extra: Any) -> None:
        if not self.logger:
            return
        self.logger.event(name, role=role, turn_id=turn_id, data={**snap, **extra})
