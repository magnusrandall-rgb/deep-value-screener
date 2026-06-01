"""yfinance price fetch. Returns plain pandas frames; never raises on a single
bad ticker (returns empty instead) so one dud can't kill the run.

Histories are deliberately fetched here only; incremental caching lives in
cache.py, which calls fetch_history() for the missing tail.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from .rate_limit import DataUnavailable, with_backoff

log = logging.getLogger("screener.prices")


@with_backoff
def fetch_history(ticker: str, start: Optional[str] = None, period: str = "max") -> pd.DataFrame:
    """Daily OHLCV for a ticker. Empty DataFrame on failure (logged, not raised)."""
    try:
        import yfinance as yf  # imported lazily so tests/offline don't need it
    except Exception as e:  # pragma: no cover
        raise DataUnavailable(f"yfinance unavailable: {e}")

    # NOTE: do NOT pass a session — yfinance >=1.x uses curl_cffi internally and
    # rejects requests/requests-cache sessions. Throttle defenses are our own
    # incremental file cache (cache.py) + the tenacity backoff decorator.
    try:
        tk = yf.Ticker(ticker)
        if start:
            df = tk.history(start=start, auto_adjust=True)
        else:
            df = tk.history(period=period, auto_adjust=True)
    except Exception as e:
        log.warning("price fetch failed for %s: %s", ticker, e)
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=str.title)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")


def latest_close(history: pd.DataFrame) -> Optional[float]:
    if history is None or history.empty:
        return None
    return float(history["Close"].iloc[-1])
