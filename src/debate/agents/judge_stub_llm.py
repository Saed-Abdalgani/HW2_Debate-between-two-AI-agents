"""Deterministic Judge LLM for integration / full-debate tests.

Includes configurable verdict responses, call history tracking,
per-role score distribution control, multi-round score variation,
and summary quality variation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from debate.sdk.llm_client import ChatResult

_VALID_VERDICT = {
    "winner": "pro",
    "reasons": [
        "Pro presented stronger evidence throughout the debate rounds.",
        "Con failed to rebut the core economic framing effectively.",
        "Pro maintained clearer structure and engagement with the motion.",
    ],
    "scores": {"pro": 72.0, "con": 58.0},
}


@dataclass
class JudgeDebateStubLLM:
    """Returns rubric scores, summaries, and a valid verdict JSON.

    Supports configurable verdict dicts, per-role score ranges,
    and call history tracking for test assertions.
    """

    model: str = "gpt-4o-mini"
    fail_verdict_once: bool = False
    custom_verdict: dict[str, Any] | None = None
    pro_score_base: float = 6.5
    con_score_base: float = 6.5
    _verdict_calls: int = field(default=0, init=False)
    _score_calls: int = field(default=0, init=False)
    _call_history: list[dict[str, Any]] = field(default_factory=list, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        """Route to verdict, score, or summary based on system prompt."""
        self._call_history.append({"messages_count": len(messages), "max_tokens": max_tokens})
        system = ""
        user = ""
        for msg in messages:
            if msg.get("role") == "system":
                system = str(msg.get("content", ""))
            elif msg.get("role") == "user":
                user = str(msg.get("content", ""))
        if "final verdict" in system.lower() or "winner" in system.lower():
            return self._verdict_reply()
        if "score" in system.lower() or "0-100" in system:
            return self._score_reply(user)
        summary = self._summary_reply(user)
        return summary

    def _score_reply(self, user_text: str = "") -> ChatResult:
        """Return a score with per-role variation."""
        self._score_calls += 1
        variation = self._score_calls % 3
        is_pro = "pro" in user_text.lower()
        base = self.pro_score_base if is_pro else self.con_score_base
        val = base + variation
        text = f"score={val}\n- clear point\n- needs evidence"
        return ChatResult(text=text, tokens_in=4, tokens_out=10, model=self.model)

    def _verdict_reply(self) -> ChatResult:
        """Return a verdict, optionally failing the first attempt."""
        self._verdict_calls += 1
        verdict = self.custom_verdict or _VALID_VERDICT
        if self.fail_verdict_once and self._verdict_calls == 1:
            bad = dict(verdict)
            bad["reasons"] = ["short", "dup", "dup"]
            text = json.dumps(bad)
        else:
            text = json.dumps(verdict)
        return ChatResult(
            text=text,
            tokens_in=8,
            tokens_out=len(text) // 4,
            model=self.model,
        )

    def _summary_reply(self, user_text: str) -> ChatResult:
        """Return a summary of varying depth based on call count."""
        depth = min(self._score_calls, 3)
        base = f"Round summary: {user_text[:80]}"
        if depth >= 2:
            base += " Key arguments were examined thoroughly."
        if depth >= 3:
            base += " Evidence quality was mixed on both sides."
        return ChatResult(
            text=base,
            tokens_in=5,
            tokens_out=len(base) // 4,
            model=self.model,
        )

    @property
    def total_calls(self) -> int:
        """Total number of chat() invocations."""
        return len(self._call_history)

    def calls_for_type(self, call_type: str) -> int:
        """Count calls by type: 'verdict', 'score', or 'summary'."""
        if call_type == "verdict":
            return self._verdict_calls
        if call_type == "score":
            return self._score_calls
        return self.total_calls - self._verdict_calls - self._score_calls

    def get_call_history(self) -> list[dict[str, Any]]:
        """Return a copy of the full call history."""
        return list(self._call_history)

    def reset(self) -> None:
        """Reset all counters and history (useful between test runs)."""
        self._verdict_calls = 0
        self._score_calls = 0
        self._call_history.clear()

    def assert_min_calls(self, min_total: int) -> None:
        """Raise AssertionError if fewer than min_total calls made."""
        if self.total_calls < min_total:
            msg = f"expected >= {min_total} calls, got {self.total_calls}"
            raise AssertionError(msg)

    def last_system_prompt(self) -> str:
        """Return the system prompt from the most recent call."""
        if not self._call_history:
            return ""
        last = self._call_history[-1]
        return str(last.get("system", ""))

    def __repr__(self) -> str:
        return (
            f"<JudgeDebateStubLLM calls={self.total_calls} "
            f"verdicts={self._verdict_calls} scores={self._score_calls}>"
        )
