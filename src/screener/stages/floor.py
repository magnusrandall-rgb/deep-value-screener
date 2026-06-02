"""Stage 0 — hard floor. Applied before anything else.

Drops sub-threshold market cap, illiquid names, and too-young listings. This is
the biggest quality+speed lever: it removes dead micro-caps, shells, and
terminal-decline names a 50%-off screen otherwise drowns in. The deliberate
false-positive bias applies only ABOVE this floor.
"""
from __future__ import annotations

import logging

from ..config import Config
from ..schema import StockRecord

log = logging.getLogger("screener.stage0")


def _threshold_for(spec, currency: str, default_key: str = "default") -> float:
    """Resolve a floor threshold from either a scalar or a per-currency map.

    Figures are kept in each security's native currency, so a USD-sized floor
    would let JPY/EUR micro-caps through. When `spec` is a map keyed by currency
    we pick the row matching `currency`, else the `default` row. A plain scalar
    is used as-is (back-compat)."""
    if isinstance(spec, dict):
        ccy = (currency or "").upper()
        if ccy in spec:
            return spec[ccy]
        return spec.get(default_key, 0)
    return spec if spec is not None else 0


def apply_floor(records: list[StockRecord], cfg: Config) -> list[StockRecord]:
    f = cfg.floor
    cap_spec = f.get("min_market_cap", 0)
    adv_spec = f.get("min_avg_daily_dollar_volume", 0)
    min_years = f.get("min_years_listed", 0)

    kept: list[StockRecord] = []
    for r in records:
        min_cap = _threshold_for(cap_spec, r.currency)
        min_adv = _threshold_for(adv_spec, r.currency)
        # Missing data must NOT silently pass the floor; require the figure.
        if r.market_cap is None or r.market_cap < min_cap:
            continue
        if r.avg_dollar_volume is None or r.avg_dollar_volume < min_adv:
            continue
        if r.years_listed is None or r.years_listed < min_years:
            continue
        kept.append(r)

    log.info("Stage 0 floor: %d -> %d", len(records), len(kept))
    return kept
