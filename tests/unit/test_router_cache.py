"""Unit tests for SkillRouter search cache and normalisation."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from debate.sdk.payloads import SearchHit, ToolCallPayload, ToolResultPayload
from debate.shared.budget import Ledger
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.router import (
    InvalidToolArgsError,
    SkillRouter,
    UnknownSkillError,
    normalize_query,
    search_cache_key,
)


def _hit(title: str = "T") -> ToolResultPayload:
    return ToolResultPayload(
        skill="search",
        hits=[SearchHit(title=title, url="https://example.com", snippet="fact")],
        cached=False,
    )


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def router(cfg):
    r = SkillRouter(cfg)
    calls = {"n": 0}

    def search_fn(args: dict[str, Any]) -> ToolResultPayload:
        calls["n"] += 1
        return _hit(args["query"][:3])

    r.register("search", search_fn)
    r._calls = calls  # type: ignore[attr-defined]
    return r


@pytest.mark.unit
def test_cache_hit_cached_true(router: SkillRouter) -> None:
    tc = ToolCallPayload(skill="search", args={"query": "climate policy", "k": 3})
    a = router.dispatch(tc)
    b = router.dispatch(tc)
    assert a.cached is False
    assert b.cached is True
    assert router._calls["n"] == 1  # type: ignore[attr-defined]


@pytest.mark.unit
def test_normalisation_collapses_whitespace_and_case() -> None:
    assert search_cache_key("  Foo\tBar ", 2) == search_cache_key("foo bar", 2)


@pytest.mark.unit
def test_different_k_different_key() -> None:
    assert search_cache_key("topic", 3) != search_cache_key("topic", 5)


@pytest.mark.unit
def test_lru_eviction(cfg) -> None:
    cfg_small = cfg.model_copy(update={"search_cache_max_entries": 2})
    r = SkillRouter(cfg_small)
    n = {"v": 0}

    def fn(args: dict[str, Any]) -> ToolResultPayload:
        n["v"] += 1
        return _hit()

    r.register("search", fn)
    for q in ("a", "b", "c"):
        r.dispatch(ToolCallPayload(skill="search", args={"query": q, "k": 1}))
    assert n["v"] == 3


@pytest.mark.unit
def test_cache_hit_bypasses_gatekeeper(cfg) -> None:
    gk = Gatekeeper(cfg, ledger=Ledger())
    r = SkillRouter(cfg)
    r.register("search", lambda _a: _hit())
    before = gk.ledger.snapshot()
    tc = ToolCallPayload(skill="search", args={"query": "budget", "k": 2})
    r.dispatch(tc)
    r.dispatch(tc)
    after = gk.ledger.snapshot()
    assert before == after


@pytest.mark.unit
def test_invalid_args_rejected(router: SkillRouter) -> None:
    with pytest.raises(InvalidToolArgsError):
        router.dispatch(ToolCallPayload(skill="search", args={"query": "  ", "k": 1}))


@pytest.mark.unit
def test_unknown_skill(cfg) -> None:
    r = SkillRouter(cfg)
    with pytest.raises(UnknownSkillError):
        r.dispatch(ToolCallPayload(skill="search", args={"query": "x", "k": 1}))


@pytest.mark.unit
def test_concurrent_search_single_upstream(cfg) -> None:
    r = SkillRouter(cfg)
    count = {"n": 0}
    lock = threading.Lock()

    def slow(args: dict[str, Any]) -> ToolResultPayload:
        with lock:
            count["n"] += 1
        return _hit()

    r.register("search", slow)
    tc = ToolCallPayload(skill="search", args={"query": "parallel", "k": 1})
    threads = [threading.Thread(target=r.dispatch, args=(tc,)) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert count["n"] == 1


@pytest.mark.unit
def test_normalize_strips_url_fragment() -> None:
    assert normalize_query("https://Ex.com/a?x=1#frag") == normalize_query("https://ex.com/a")
