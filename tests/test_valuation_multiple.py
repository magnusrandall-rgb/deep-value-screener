"""Stage-4 normalized-multiple tests: the historical EV/EBIT path, the
sector/quality fallback path, and the guarantee that the multiple is NOT a pure
function of the quality score.
"""
from __future__ import annotations

from screener.config import load_config
from screener.schema import StockRecord
from screener.stages import valuation


def _record(ticker, *, price, ebit, n, quality, conf, dates,
            margin=0.20, revenue=5e9, debt=0.0, cash=0.0):
    return StockRecord(
        ticker=ticker, name=ticker, region="US", price=price,
        market_cap=price * 1e8,                       # -> implied shares = 1e8
        revenue_history=[revenue] * n,
        ebit_margin_history=[margin] * n,
        ebit_history=[ebit] * n,
        ebitda_history=[ebit * 1.2] * n,
        share_count_history=[1e8] * n,
        total_debt_history=[debt] * n,
        cash_history=[cash] * n,
        period_end_dates=dates[:n],
        quality_score=quality, data_confidence=conf,
    )


def test_historical_ev_ebit_path(flat_prices, year_ends):
    cfg = load_config()
    flat_prices("HISTCO", price=100.0)               # EV = 100*1e8 + net debt
    # net debt = 2e9 - 1e9 = 1e9 -> EV = 1.1e10; EBIT = 1e9 -> EV/EBIT = 11 each yr
    r = _record("HISTCO", price=100.0, ebit=1e9, n=6, quality=70, conf=0.90,
                dates=year_ends, debt=2e9, cash=1e9)
    valuation.value_stocks([r], cfg)

    assert r.multiple_basis == "EV/EBIT"
    assert r.multiple_from_fallback is False
    assert r.norm_multiple == 11.0                   # median of the company's own history
    assert r.data_confidence == 0.90                 # NOT lowered on the historical path
    assert r.upside_base is not None                 # positive margin -> upside estimated


def test_fallback_when_insufficient_history(flat_prices, year_ends):
    cfg = load_config()
    flat_prices("FALLCO", price=50.0)
    # only 2 usable years (< min_years_for_historical_multiple = 3) -> fallback band
    r = _record("FALLCO", price=50.0, ebit=3e8, n=2, quality=50, conf=0.80,
                dates=year_ends)
    valuation.value_stocks([r], cfg)

    assert r.multiple_from_fallback is True
    assert r.multiple_basis == "fallback-band"
    lo, hi = cfg.valuation.get("fallback_multiple_band", [8, 16])
    assert lo <= r.norm_multiple <= hi
    # data-confidence lowered by the configured penalty (0.80 * 0.85 = 0.68)
    assert r.data_confidence == round(0.80 * cfg.valuation.get(
        "fallback_multiple_confidence_penalty", 0.85), 2)


def test_multiple_is_not_a_pure_function_of_quality(flat_prices, year_ends):
    """Two names with IDENTICAL quality but different price histories must get
    different normalized multiples — proving the multiple is history-driven."""
    cfg = load_config()
    flat_prices("CHEAPHIST", price=100.0)
    flat_prices("RICHHIST", price=200.0)
    a = _record("CHEAPHIST", price=100.0, ebit=1e9, n=5, quality=60, conf=0.9,
                dates=year_ends)                     # EV/EBIT = 10
    b = _record("RICHHIST", price=200.0, ebit=1e9, n=5, quality=60, conf=0.9,
                dates=year_ends)                     # EV/EBIT = 20
    valuation.value_stocks([a, b], cfg)

    assert a.quality_score == b.quality_score
    assert a.multiple_from_fallback is False and b.multiple_from_fallback is False
    assert a.norm_multiple == 10.0
    assert b.norm_multiple == 20.0
    assert a.norm_multiple != b.norm_multiple


def test_negative_margin_not_estimated_even_with_a_multiple(flat_prices, year_ends):
    """A name with a usable historical multiple but a negative normalized margin
    still gets no upside (method doesn't apply), not a bogus number."""
    cfg = load_config()
    flat_prices("LOSSCO", price=100.0)
    r = _record("LOSSCO", price=100.0, ebit=1e9, n=5, quality=40, conf=0.9,
                dates=year_ends, margin=-0.05)
    valuation.value_stocks([r], cfg)
    assert r.norm_multiple is not None               # multiple still computed
    assert r.upside_base is None                      # but upside intentionally unestimated
