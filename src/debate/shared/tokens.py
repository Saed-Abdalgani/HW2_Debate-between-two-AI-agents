"""Token estimation — tiktoken with chars/4 fallback."""

from __future__ import annotations

from typing import Any

import tiktoken


def estimate_tokens(messages: list[dict[str, Any]], model: str) -> int:
    """Estimate prompt tokens.

    Uses ``tiktoken`` for known models; otherwise ``len(text) / 4`` per message
    (standard coarse heuristic when the encoder mapping is unknown).
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = None
    total = 0
    for msg in messages:
        text = msg.get("content", "")
        if not isinstance(text, str):
            text = str(text)
        total += len(enc.encode(text)) if enc else max(1, len(text) // 4)
    return total
