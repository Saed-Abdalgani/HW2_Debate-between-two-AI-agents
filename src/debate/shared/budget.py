"""Budget ledger — tokens, USD, and request-rate enforcement."""

from __future__ import annotations

import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from debate.sdk.errors import PermanentProviderError, TransientProviderError  # noqa: F401


class BudgetExceeded(Exception):
    """Raised when a call would breach a configured cap."""

    def __init__(self, reason: str, snapshot: dict[str, Any]) -> None:
        self.reason = reason
        self.snapshot = snapshot
        super().__init__(reason)


@dataclass(frozen=True)
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    usd: Decimal = Decimal("0")
    requests: int = 1

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class BudgetCaps:
    max_tokens_per_turn: int
    max_tokens_per_debate: int
    max_usd_per_debate: Decimal
    max_requests_per_minute: int


@dataclass
class Ledger:
    tokens_in: int = 0
    tokens_out: int = 0
    usd_spent: Decimal = Decimal("0")
    requests: int = 0
    started_at: float = field(default_factory=time.monotonic)
    requests_window: deque[float] = field(default_factory=deque)

    def add(self, usage: Usage) -> None:
        self.tokens_in += usage.tokens_in
        self.tokens_out += usage.tokens_out
        self.usd_spent += usage.usd
        self.requests += usage.requests
        now = time.monotonic()
        for _ in range(usage.requests):
            self.requests_window.append(now)

    def _prune_rpm(self, now: float) -> None:
        cutoff = now - 60.0
        while self.requests_window and self.requests_window[0] < cutoff:
            self.requests_window.popleft()

    def rpm_count(self, now: float | None = None) -> int:
        now = now if now is not None else time.monotonic()
        self._prune_rpm(now)
        return len(self.requests_window)

    def would_exceed(
        self, estimate: Usage, caps: BudgetCaps, *, now: float | None = None
    ) -> str | None:
        """Return the first cap that would be breached, or ``None`` to allow."""
        now = now if now is not None else time.monotonic()
        if estimate.tokens_out > caps.max_tokens_per_turn:
            return "max_tokens_per_turn"
        if self.tokens_in + self.tokens_out + estimate.tokens_total > caps.max_tokens_per_debate:
            return "max_tokens_per_debate"
        if self.usd_spent + estimate.usd > caps.max_usd_per_debate:
            return "max_usd_per_debate"
        self._prune_rpm(now)
        if len(self.requests_window) + estimate.requests > caps.max_requests_per_minute:
            return "max_requests_per_minute"
        return None

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(
            {
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "usd_spent": str(self.usd_spent),
                "requests": self.requests,
                "rpm": self.rpm_count(),
                "started_at": self.started_at,
                "requests_window": list(self.requests_window),
            }
        )
