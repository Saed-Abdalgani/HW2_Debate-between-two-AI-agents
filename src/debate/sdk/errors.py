"""Provider HTTP errors — no shared imports (avoids circular loads)."""


class TransientProviderError(Exception):
    """HTTP 429 / 5xx / timeout — Gatekeeper may retry."""


class PermanentProviderError(Exception):
    """HTTP 4xx (except 429) — do not retry."""
