"""Deterministic Judge LLM for integration / full-debate tests."""

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
    """Returns rubric scores, summaries, and a valid verdict JSON."""

    model: str = "gpt-4o-mini"
    fail_verdict_once: bool = False
    _verdict_calls: int = field(default=0, init=False)
    _score_calls: int = field(default=0, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
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
            return self._score_reply()
        summary = f"Round summary: {user[:80]}..."
        return ChatResult(text=summary, tokens_in=5, tokens_out=12, model=self.model)

    def _score_reply(self) -> ChatResult:
        self._score_calls += 1
        val = 6.5 + (self._score_calls % 3)
        text = f"score={val}\n- clear point\n- needs evidence"
        return ChatResult(text=text, tokens_in=4, tokens_out=10, model=self.model)

    def _verdict_reply(self) -> ChatResult:
        self._verdict_calls += 1
        if self.fail_verdict_once and self._verdict_calls == 1:
            bad = dict(_VALID_VERDICT)
            bad["reasons"] = ["short", "dup", "dup"]
            text = json.dumps(bad)
        else:
            text = json.dumps(_VALID_VERDICT)
        return ChatResult(text=text, tokens_in=8, tokens_out=len(text) // 4, model=self.model)
