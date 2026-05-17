"""Pure unit tests for ledger maths, RPM windowing, and pricing."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

import pytest

from debate.shared.budget import BudgetCaps, Ledger, Usage
from debate.shared.config import load_config
from debate.shared.pricing import UnknownModelError, load_pricing_table, price


@pytest.fixture
def caps():
    cfg = load_config()
    return BudgetCaps(
        max_tokens_per_turn=cfg.max_tokens_per_turn,
        max_tokens_per_debate=cfg.max_tokens_per_debate,
        max_usd_per_debate=Decimal(str(cfg.max_usd_per_debate)),
        max_requests_per_minute=cfg.max_requests_per_minute,
    )


@pytest.mark.unit
def test_token_out_cap_boundary(caps: BudgetCaps) -> None:
    ledger = Ledger()
    est_at = Usage(tokens_in=10, tokens_out=caps.max_tokens_per_turn, usd=Decimal("0.0001"))
    assert ledger.would_exceed(est_at, caps) is None
    est_over = Usage(tokens_in=10, tokens_out=caps.max_tokens_per_turn + 1, usd=Decimal("0.0001"))
    assert ledger.would_exceed(est_over, caps) == "max_tokens_per_turn"


@pytest.mark.unit
def test_debate_cap_sums_across_turns(caps: BudgetCaps) -> None:
    ledger = Ledger(tokens_in=caps.max_tokens_per_debate - 5)
    est = Usage(tokens_in=10, tokens_out=10, usd=Decimal("0.0001"))
    assert ledger.would_exceed(est, caps) == "max_tokens_per_debate"


@pytest.mark.unit
def test_usd_cap_decimal_precision(caps: BudgetCaps) -> None:
    ledger = Ledger(usd_spent=Decimal("1.499999"))
    bad = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.000002"))
    ok = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.000001"))
    assert ledger.would_exceed(bad, caps) == "max_usd_per_debate"
    assert ledger.would_exceed(ok, caps) is None


@pytest.mark.unit
def test_rpm_windowing_inside_and_over() -> None:
    caps = BudgetCaps(800, 60000, Decimal("9"), 30)
    ledger = Ledger(requests_window=deque([100.0] * 29))
    est = Usage(requests=1)
    assert ledger.would_exceed(est, caps, now=120.0) is None
    ledger.requests_window.append(100.0)
    assert ledger.would_exceed(est, caps, now=120.0) == "max_requests_per_minute"
    over = Ledger(requests_window=deque([100.0] * 31))
    assert over.would_exceed(est, caps, now=120.0) == "max_requests_per_minute"


@pytest.mark.unit
def test_rpm_window_prunes_old_entries() -> None:
    ledger = Ledger(requests_window=deque([0.0] * 30))
    assert ledger.rpm_count(now=120.0) == 0


@pytest.mark.unit
def test_ledger_add_and_snapshot_deepcopy() -> None:
    ledger = Ledger()
    ledger.add(Usage(tokens_in=10, tokens_out=20, usd=Decimal("0.01"), requests=2))
    snap = ledger.snapshot()
    assert snap["tokens_in"] == 10
    assert snap["tokens_out"] == 20
    assert snap["usd_spent"] == "0.01"
    assert snap["requests"] == 2
    snap["requests_window"].clear()
    assert len(ledger.requests_window) == 2


@pytest.mark.unit
def test_pricing_unknown_model_rejected() -> None:
    with pytest.raises(UnknownModelError):
        price(Usage(tokens_in=1, tokens_out=1), "not-a-real-model", table=load_pricing_table())


@pytest.mark.unit
def test_pricing_half_up_six_dp() -> None:
    usd = price(Usage(tokens_in=1, tokens_out=1), "gpt-4o-mini", table=load_pricing_table())
    assert usd == Decimal("0.000001")
