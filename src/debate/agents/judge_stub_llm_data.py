"""Default verdict payload for ``JudgeDebateStubLLM``."""

from __future__ import annotations

from typing import Any

VALID_VERDICT: dict[str, Any] = {
    "winner": "pro",
    "reasons": [
        "Pro presented stronger evidence throughout the debate rounds.",
        "Con failed to rebut the core economic framing effectively.",
        "Pro maintained clearer structure and engagement with the motion.",
    ],
    "scores": {"pro": 72.0, "con": 58.0},
}
