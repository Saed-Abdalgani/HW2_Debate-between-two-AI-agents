"""Unit tests for Gatekeeper.execute(): retries, drift, context I/O."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from debate.shared.budget import BudgetExceeded, TransientProviderError, Usage
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger


@dataclass
class _Result:
    tokens_in: int
    tokens_out: int
    value: str = "ok"


@pytest.fixture
def cfg(tmp_path: Path):
    return load_config()


@pytest.fixture
def gk(cfg, tmp_path: Path):
    run = tmp_path / "runs" / "t1"
    fast = cfg.model_copy(update={"retry_initial_delay_sec": 0.0, "retry_jitter_sec": 0.0})
    return Gatekeeper(fast, logger=Logger(run, root=tmp_path), run_dir=run)


@pytest.mark.unit
def test_budget_exhausted_event_shape(gk: Gatekeeper, tmp_path: Path) -> None:
    gk.ledger.tokens_in = gk.cfg.max_tokens_per_debate
    est = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.0001"))
    with pytest.raises(BudgetExceeded) as exc:
        gk.execute(
            lambda: _Result(1, 1), estimate=est, role="judge", turn_id=1, model="gpt-4o-mini"
        )
    assert exc.value.reason == "max_tokens_per_debate"
    assert "tokens_in" in exc.value.snapshot
    log = (tmp_path / "runs" / "t1" / "run.jsonl").read_text(encoding="utf-8")
    assert "budget_exhausted" in log


@pytest.mark.unit
def test_retry_on_transient(gk: Gatekeeper) -> None:
    calls = {"n": 0}

    def flaky() -> _Result:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientProviderError("429")
        return _Result(5, 5)

    est = Usage(tokens_in=5, tokens_out=5, usd=Decimal("0.0001"))
    out = gk.execute(flaky, estimate=est, role="pro", turn_id=2, model="gpt-4o-mini")
    assert out.value == "ok"
    assert calls["n"] == 3


@pytest.mark.unit
def test_reconcile_overwrites_estimate(gk: Gatekeeper) -> None:
    est = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.0001"))
    gk.execute(lambda: _Result(40, 60), estimate=est, role="con", turn_id=3, model="gpt-4o-mini")
    assert gk.ledger.tokens_in == 40
    assert gk.ledger.tokens_out == 60


@pytest.mark.unit
def test_select_write_context(gk: Gatekeeper, tmp_path: Path) -> None:
    gk.context.note_reply("pro", "we affirm")
    gk.context.note_opponent("pro", "they deny")
    gk.write_summary("pro", 1, "round one gist")
    msgs = gk.select_context("pro", 1)
    assert any("round one gist" in m.content for m in msgs)
    assert (tmp_path / "runs" / "t1" / "summary.pro.md").exists()


@pytest.mark.unit
def test_failed_retries_accounted_in_ledger(gk: Gatekeeper) -> None:
    attempts = {"n": 0}

    def flaky() -> _Result:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TransientProviderError("503")
        return _Result(5, 5)

    est = Usage(tokens_in=5, tokens_out=5, usd=Decimal("0.0001"))
    gk.execute(flaky, estimate=est, role="pro", turn_id=4, model="gpt-4o-mini")
    assert gk.ledger.requests == 3
    assert len(gk.ledger.requests_window) == 3


@pytest.mark.unit
def test_retry_exhaustion_raises(gk: Gatekeeper) -> None:
    def always_fail() -> _Result:
        raise TransientProviderError("429")

    est = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.0001"))
    with pytest.raises(TransientProviderError):
        gk.execute(always_fail, estimate=est, role="pro", turn_id=5, model="gpt-4o-mini")
    assert gk.ledger.requests == gk.cfg.max_retries + 1


@pytest.mark.unit
def test_drift_warning_emitted(gk: Gatekeeper, tmp_path: Path) -> None:
    est = Usage(tokens_in=10, tokens_out=10, usd=Decimal("0.0001"))
    gk.execute(lambda: _Result(100, 100), estimate=est, role="con", turn_id=6, model="gpt-4o-mini")
    log = (tmp_path / "runs" / "t1" / "run.jsonl").read_text(encoding="utf-8")
    assert "token_estimate_drift" in log


@pytest.mark.unit
def test_no_drift_warning_within_threshold(gk: Gatekeeper, tmp_path: Path) -> None:
    est = Usage(tokens_in=50, tokens_out=50, usd=Decimal("0.0001"))
    gk.execute(lambda: _Result(50, 50), estimate=est, role="con", turn_id=7, model="gpt-4o-mini")
    log = (tmp_path / "runs" / "t1" / "run.jsonl").read_text(encoding="utf-8")
    assert "token_estimate_drift" not in log


@pytest.mark.unit
def test_drift_guard_zero_actual(gk: Gatekeeper) -> None:
    est = Usage(tokens_in=10, tokens_out=10, usd=Decimal("0"))
    gk.execute(lambda: _Result(0, 0), estimate=est, role="judge", turn_id=8, model="gpt-4o-mini")


@pytest.mark.unit
def test_build_estimate_uses_max_tokens_per_turn(gk: Gatekeeper) -> None:
    est = gk.build_estimate([{"role": "user", "content": "hi"}], "gpt-4o-mini")
    assert est.tokens_out == gk.cfg.max_tokens_per_turn
    assert est.usd > Decimal("0")


@pytest.mark.unit
def test_retry_honors_provider_retry_after_sec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = load_config().model_copy(
        update={"retry_initial_delay_sec": 0.0, "retry_jitter_sec": 0.0, "max_retries": 2}
    )
    run = tmp_path / "runs" / "t_ra"
    gk = Gatekeeper(cfg, logger=Logger(run, root=tmp_path), run_dir=run)
    sleeps: list[float] = []
    monkeypatch.setattr("debate.shared.gatekeeper.time.sleep", lambda s: sleeps.append(float(s)))
    n = {"c": 0}

    def flaky() -> _Result:
        n["c"] += 1
        if n["c"] < 2:
            raise TransientProviderError("HTTP 429", retry_after_sec=4.0)
        return _Result(1, 1)

    est = Usage(tokens_in=1, tokens_out=1, usd=Decimal("0.0001"))
    gk.execute(flaky, estimate=est, role="pro", turn_id=9, model="gpt-4o-mini")
    assert sleeps and sleeps[0] >= 4.0
