"""Test harness: build a tiny offline cache fixture and point the screener at it.

We set SCREENER_CACHE and SCREENER_CONFIG *before* importing any screener module
so the module-level cache root / config path resolve to the fixture. Tests then
run the full pipeline with allow_fetch=False — no network, fast, deterministic.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# --- wire env BEFORE importing screener --------------------------------------
_TMP = Path(tempfile.mkdtemp(prefix="dv_screener_test_"))
os.environ["SCREENER_CACHE"] = str(_TMP)
os.environ["SCREENER_CONFIG"] = str(Path(__file__).parent / "fixtures" / "config.test.yaml")

import pandas as pd  # noqa: E402


def _write_price_csv(ticker: str, peak: float, trough: float, years: float = 6.0):
    """Synthetic daily history that peaks then falls to near the 52w low."""
    end = datetime(2026, 5, 29)
    start = end - timedelta(days=int(365.25 * years))
    idx = pd.bdate_range(start, end)
    n = len(idx)
    rise = int(n * 0.4)
    closes = []
    for i in range(n):
        if i < rise:
            closes.append(peak * (0.5 + 0.5 * i / rise))     # climb to peak
        else:
            frac = (i - rise) / (n - rise)
            closes.append(peak - (peak - trough) * frac)     # decline to trough
    df = pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes],
         "Low": [c * 0.99 for c in closes], "Close": closes,
         "Volume": [2_000_000] * n},
        index=idx,
    )
    p = _TMP / "prices" / f"{ticker}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p)


_YEAR_ENDS = ["2025-12-31", "2024-12-31", "2023-12-31",
              "2022-12-31", "2021-12-31", "2020-12-31"]


def _write_fundamentals(ticker: str, **over):
    data = {
        "revenue": [5.0e9, 5.2e9, 5.1e9, 5.4e9, 5.3e9, 5.6e9],
        "ebit": [6e8, 6.2e8, 6.1e8, 6.4e8, 6.3e8, 6.6e8],
        "ebit_margin": [0.12, 0.119, 0.12, 0.118, 0.119, 0.118],
        "gross_margin": [0.4, 0.41, 0.4, 0.42, 0.41, 0.42],
        "operating_cf": [5e8] * 6,
        "fcf": [4e8] * 6,
        "fcf_margin": [0.08, 0.08, 0.079, 0.08, 0.081, 0.08],
        "net_income": [3e8, 3.1e8, 3.0e8, 3.2e8, 3.1e8, 3.3e8],
        "ebitda": [7e8] * 6,
        "share_count": [100_000_000] * 6,
        "roic": [0.09, 0.095, 0.092, 0.10, 0.098, 0.101],
        "roce": [0.11, 0.115, 0.112, 0.12, 0.118, 0.121],
        "net_debt_to_ebitda": 1.5,
        # date-aligned series for the Stage-4 historical EV/EBIT(DA) multiple
        "period_end_dates": list(_YEAR_ENDS),
        "ebit_aligned": [6e8, 6.2e8, 6.1e8, 6.4e8, 6.3e8, 6.6e8],
        "ebitda_aligned": [7e8] * 6,
        "total_debt": [1.5e9] * 6,
        "cash": [0.5e9] * 6,
        "shares_aligned": [100_000_000] * 6,
        "accounting_standard": "US-GAAP",
        "sector": "Technology",
        "currency": "USD",
        "_fetched_at": datetime.utcnow().isoformat(),
    }
    data.update(over)
    p = _TMP / "fundamentals" / f"{ticker}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


def write_flat_prices(ticker: str, price: float = 100.0, years: float = 8.0):
    """Write a flat daily price history into the fixture cache (for unit tests)."""
    end = datetime(2026, 5, 29)
    start = end - timedelta(days=int(365.25 * years))
    idx = pd.bdate_range(start, end)
    df = pd.DataFrame(
        {"Open": price, "High": price, "Low": price, "Close": price,
         "Volume": 1_000_000},
        index=idx,
    )
    p = _TMP / "prices" / f"{ticker}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p)


def _write_universe():
    # A deep-value US name (should pass), and a junk never-profitable name (drop).
    from screener.schema import StockRecord
    recs = [
        StockRecord(ticker="DEEPUS", name="Deep Value Co", region="US",
                    exchange="NYSE", sector="Technology", currency="USD"),
        StockRecord(ticker="JUNKUS", name="Junk Co", region="US",
                    exchange="NASDAQ", sector="Technology", currency="USD"),
    ]
    p = _TMP / "universe.json"
    p.write_text(json.dumps([r.to_dict() for r in recs]))


@pytest.fixture(scope="session", autouse=True)
def _fixture_cache():
    _write_universe()
    # passes the price screen: down ~65% from peak, near 52w low
    _write_price_csv("DEEPUS", peak=200.0, trough=70.0)
    _write_fundamentals("DEEPUS")
    # junk: also beaten down, but never profitable -> Stage 3 auto-drops it
    _write_price_csv("JUNKUS", peak=50.0, trough=10.0)
    _write_fundamentals("JUNKUS", net_income=[-1e8, -2e8, -1.5e8, -1e8, -3e8, -2e8])
    yield


@pytest.fixture
def cfg():
    from screener.config import load_config
    return load_config()


@pytest.fixture
def flat_prices():
    """Returns the helper that writes a flat price series for a ticker."""
    return write_flat_prices


@pytest.fixture
def year_ends():
    return list(_YEAR_ENDS)
