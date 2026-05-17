"""Model pricing table — Decimal USD, never float."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from debate.shared.budget import Usage

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PATH = _ROOT / "config" / "pricing.json"
_QUANT = Decimal("0.000001")


class UnknownModelError(Exception):
    def __init__(self, model: str) -> None:
        super().__init__(f"no pricing entry for model: {model}")


@lru_cache(maxsize=4)
def load_pricing_table(path: Path | None = None) -> dict[str, dict[str, Decimal]]:
    raw = json.loads((path or _DEFAULT_PATH).read_text(encoding="utf-8"))
    return {
        model: {
            "input_usd_per_1k": Decimal(str(rates["input_usd_per_1k"])),
            "output_usd_per_1k": Decimal(str(rates["output_usd_per_1k"])),
        }
        for model, rates in raw.items()
    }


def price(
    usage: Usage, model: str, *, table: dict[str, dict[str, Decimal]] | None = None
) -> Decimal:
    """Return USD cost for token usage; round half-up to 6 dp."""
    rates = (table or load_pricing_table()).get(model)
    if rates is None:
        raise UnknownModelError(model)
    usd = (
        Decimal(usage.tokens_in) / Decimal(1000) * rates["input_usd_per_1k"]
        + Decimal(usage.tokens_out) / Decimal(1000) * rates["output_usd_per_1k"]
    )
    return usd.quantize(_QUANT, rounding=ROUND_HALF_UP)
