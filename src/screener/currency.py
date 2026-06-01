"""FX normalization to the reporting currency.

Rates are fetched from Yahoo ("EURUSD=X" style) and cached for the day. If a
rate can't be obtained we return None and the caller flags lower data-confidence
rather than silently using 1.0.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from .cache import CACHE_ROOT
from .data.prices import fetch_history

log = logging.getLogger("screener.currency")

_RATE_CACHE = CACHE_ROOT / "cache" / "fx_rates.json"


def _load_cache() -> dict:
    if _RATE_CACHE.exists():
        try:
            return json.loads(_RATE_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(d: dict) -> None:
    _RATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _RATE_CACHE.write_text(json.dumps(d))
    except Exception:  # pragma: no cover
        pass


def get_rate(from_ccy: str, to_ccy: str, allow_fetch: bool = True) -> Optional[float]:
    """Units of `to_ccy` per 1 unit of `from_ccy`. None if unavailable."""
    if not from_ccy or not to_ccy:
        return None
    from_ccy, to_ccy = from_ccy.upper(), to_ccy.upper()
    if from_ccy == to_ccy:
        return 1.0

    key = f"{from_ccy}{to_ccy}:{date.today().isoformat()}"
    cache = _load_cache()
    if key in cache:
        return cache[key]
    if not allow_fetch:
        return None

    pair = f"{from_ccy}{to_ccy}=X"
    hist = fetch_history(pair, period="5d")
    rate = None
    if hist is not None and not hist.empty:
        rate = float(hist["Close"].iloc[-1])
    if rate:
        cache[key] = rate
        _save_cache(cache)
    else:
        log.warning("no FX rate for %s->%s", from_ccy, to_ccy)
    return rate


def convert(amount: Optional[float], from_ccy: str, to_ccy: str,
            allow_fetch: bool = True) -> Optional[float]:
    if amount is None:
        return None
    rate = get_rate(from_ccy, to_ccy, allow_fetch=allow_fetch)
    return None if rate is None else amount * rate
