"""Stage 2 — the fast price screen, plus the price-derived floor inputs.

Keeps names that are BOTH down >= pct_off_ath from their all-time high AND
within pct_above_52w_low of the 52-week low. Also fills in market cap, average
dollar volume, and years-listed so Stage 0's floor can run against real numbers.

ATH handling: prefer a true ATH; otherwise use the max over available history,
mark ath_is_approx=True, and SCORE ath_confidence per ticker (short/sparse/
gappy histories score low). Never present an approximation as a hard figure.

Market cap & dollar volume are kept in each security's NATIVE currency (FX
normalization was removed to avoid extra Yahoo requests); `r.currency` records
which currency that is.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from .. import cache
from ..config import Config
from ..schema import StockRecord

log = logging.getLogger("screener.stage2")

# A "true ATH" needs a long, dense history. These heuristics set ath_confidence.
_MIN_YEARS_FOR_TRUE_ATH = 15
_MIN_ROWS_PER_YEAR = 200  # trading days; sparse series are suspect


def _ath_confidence(hist: pd.DataFrame) -> tuple[bool, float]:
    if hist.empty:
        return True, 0.0
    span_days = (hist.index.max() - hist.index.min()).days
    years = span_days / 365.25
    rows_per_year = len(hist) / max(years, 0.01)
    # Confidence blends history length and density.
    length_score = min(1.0, years / _MIN_YEARS_FOR_TRUE_ATH)
    density_score = min(1.0, rows_per_year / _MIN_ROWS_PER_YEAR)
    conf = round(0.5 * length_score + 0.5 * density_score, 2)
    is_true_ath = years >= _MIN_YEARS_FOR_TRUE_ATH and density_score > 0.8
    return (not is_true_ath), conf


def _years_listed(hist: pd.DataFrame) -> float:
    if hist.empty:
        return 0.0
    return round((hist.index.max() - hist.index.min()).days / 365.25, 1)


def screen_prices(records: list[StockRecord], cfg: Config,
                  allow_fetch: bool = True) -> list[StockRecord]:
    pct_off = cfg.price.get("pct_off_ath", 50)
    pct_above = cfg.price.get("pct_above_52w_low", 20)
    ath_mode = cfg.price.get("ath_mode", "approx-allowed")

    kept: list[StockRecord] = []
    for r in records:
        hist = cache.get_price_history(r.ticker, allow_fetch=allow_fetch)
        if hist.empty or len(hist) < 30:
            continue

        price = float(hist["Close"].iloc[-1])
        ath = float(hist["Close"].max())
        approx, conf = _ath_confidence(hist)

        # Respect strict ATH mode: skip names whose ATH we can't trust.
        if ath_mode == "true" and approx:
            continue

        if ath <= 0:
            continue
        pct_off_ath = (1 - price / ath) * 100

        last_year = hist.loc[hist.index >= hist.index.max() - pd.Timedelta(days=365)]
        low_52w = float(last_year["Close"].min()) if not last_year.empty else price
        pct_above_low = (price / low_52w - 1) * 100 if low_52w else 0.0

        if pct_off_ath < pct_off:
            continue
        if pct_above_low > pct_above:
            continue

        # Passed the price screen — enrich for the floor & later stages.
        r.price = round(price, 4)
        r.ath = round(ath, 4)
        r.ath_is_approx = approx
        r.ath_confidence = conf
        r.pct_off_ath = round(pct_off_ath, 1)
        r.low_52w = round(low_52w, 4)
        r.pct_above_52w_low = round(pct_above_low, 1)
        r.years_listed = _years_listed(hist)

        # Average dollar volume (60d), in the security's native currency.
        vol = (hist["Close"] * hist["Volume"]).tail(60).mean()
        r.avg_dollar_volume = float(vol) if vol == vol else None

        kept.append(r)

    log.info("Stage 2 price screen: %d -> %d", len(records), len(kept))
    return kept


def attach_market_cap(records: list[StockRecord], cfg: Config,
                      allow_fetch: bool = True) -> list[StockRecord]:
    """Market cap from cached fundamentals' share count x price, native currency.

    Kept separate from screen_prices so the floor can run on real figures while
    avoiding a fundamentals pull for names that already failed the price screen.
    """
    for r in records:
        f = cache.get_fundamentals(r.ticker, r.region, allow_fetch=allow_fetch)
        shares = f.get("share_count") or []
        # Native reporting currency from yfinance (financialCurrency), if known.
        ccy = f.get("currency") or r.currency
        if shares and r.price:
            r.market_cap = shares[0] * r.price
        if ccy:
            r.currency = ccy
    return records
