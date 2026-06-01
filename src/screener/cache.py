"""Price/fundamentals caching with incremental daily updates.

Histories are expensive and Yahoo throttles, so we never re-download a full
history when we already hold most of it: we read the cached frame, fetch only
the missing tail (from the day after the last cached row), and append.

Cache layout (all gitignored except the tiny test fixture):
    data/prices/<safe_ticker>.csv          daily OHLCV
    data/fundamentals/<safe_ticker>.json   normalized fundamentals dict
    data/cache/fundamentals_age.json       per-ticker fetch dates

Tests point CACHE_ROOT at tests/fixtures/cache so they never hit the network.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from .data import prices, fundamentals as fund_mod
from .data.rate_limit import DataUnavailable

log = logging.getLogger("screener.cache")

CACHE_ROOT = Path(os.environ.get("SCREENER_CACHE", "data"))
_PRICE_DIR = "prices"
_FUND_DIR = "fundamentals"
_FUND_MAX_AGE_DAYS = 7  # fundamentals change slowly; refresh weekly


def _safe(ticker: str) -> str:
    return ticker.replace("/", "_").replace("\\", "_")


def _price_path(ticker: str) -> Path:
    return CACHE_ROOT / _PRICE_DIR / f"{_safe(ticker)}.csv"


def _fund_path(ticker: str) -> Path:
    return CACHE_ROOT / _FUND_DIR / f"{_safe(ticker)}.json"


def get_price_history(ticker: str, allow_fetch: bool = True) -> pd.DataFrame:
    """Return full daily history, using cache + incremental tail fetch."""
    path = _price_path(ticker)
    cached = pd.DataFrame()
    if path.exists():
        try:
            cached = pd.read_csv(path, index_col=0, parse_dates=True)
        except Exception as e:
            log.warning("could not read price cache %s: %s", path, e)

    if not allow_fetch:
        return cached

    try:
        if cached.empty:
            fresh = prices.fetch_history(ticker, period="max")
        else:
            last = cached.index.max()
            start = (last + timedelta(days=1)).strftime("%Y-%m-%d")
            if pd.Timestamp(start) > pd.Timestamp(datetime.utcnow().date()):
                return cached  # already current
            tail = prices.fetch_history(ticker, start=start)
            fresh = pd.concat([cached, tail]) if not tail.empty else cached
    except DataUnavailable as e:
        log.warning("throttled/unavailable for %s, serving cache: %s", ticker, e)
        return cached

    if fresh is None or fresh.empty:
        return cached

    fresh = fresh[~fresh.index.duplicated(keep="last")].sort_index()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fresh.to_csv(path)
    except Exception as e:  # pragma: no cover
        log.warning("could not write price cache %s: %s", path, e)
    return fresh


def get_fundamentals(ticker: str, region: str, allow_fetch: bool = True) -> dict:
    """Return normalized fundamentals dict, refreshing at most weekly."""
    path = _fund_path(ticker)
    cached: Optional[dict] = None
    if path.exists():
        try:
            cached = json.loads(path.read_text())
        except Exception:
            cached = None

    fresh_enough = False
    if cached:
        ts = cached.get("_fetched_at")
        if ts:
            age = datetime.utcnow() - datetime.fromisoformat(ts)
            fresh_enough = age < timedelta(days=_FUND_MAX_AGE_DAYS)

    if cached and (fresh_enough or not allow_fetch):
        return cached

    try:
        data = fund_mod.fetch_fundamentals(ticker, region)
    except DataUnavailable as e:
        log.warning("fundamentals throttled for %s: %s", ticker, e)
        return cached or {}

    data["_fetched_at"] = datetime.utcnow().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(data))
    except Exception as e:  # pragma: no cover
        log.warning("could not write fundamentals cache %s: %s", path, e)
    return data
