"""Environment secrets — sole module that reads os.environ (NFR-10, NFR-11)."""

from __future__ import annotations

import os
import re
from typing import Any

_MASK = "***REDACTED***"
_SECRET_ENV_NAMES = frozenset({"LLM_API_KEY", "SEARCH_API_KEY"})
_REDACT_PATTERNS = (
    re.compile(r"LLM_API_KEY=sk-[A-Za-z0-9]{10,}"),
    re.compile(r"SEARCH_API_KEY=[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
)


class MissingSecretError(Exception):
    """Raised when a required API key env var is unset or empty."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Missing required secret: {name}")


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a non-secret env var (config paths, tunable overrides)."""
    return os.environ.get(name, default)


def get_key(name: str) -> str:
    """Return a required API key; never log or include the value in errors."""
    value = os.environ.get(name)
    if not value:
        raise MissingSecretError(name)
    return value


def _redact_str(text: str) -> str:
    out = text
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub(_MASK, out)
    return out


def redact(payload: Any) -> Any:
    """Mask secret patterns in strings; recurse dicts/lists; idempotent."""
    if isinstance(payload, str):
        return _redact_str(payload)
    if isinstance(payload, dict):
        return {
            key: _MASK if key in _SECRET_ENV_NAMES else redact(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    return payload
