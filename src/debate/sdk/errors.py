"""Provider HTTP errors — no shared imports (avoids circular loads)."""


class TransientProviderError(Exception):
    """HTTP 429 / 5xx / timeout — Gatekeeper may retry."""

    def __init__(self, message: str, *, retry_after_sec: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class PermanentProviderError(Exception):
    """HTTP 4xx (except 429) — do not retry."""
