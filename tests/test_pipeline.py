"""End-to-end offline pipeline test plus per-stage unit checks. No network."""
from __future__ import annotations

from screener.config import load_config
from screener.pipeline import run_pipeline
from screener.schema import StockRecord
from screener.stages import floor, valuation


def test_pipeline_offline_surfaces_deep_value_and_drops_junk():
    cfg = load_config()
    records = run_pipeline(cfg, allow_fetch=False)
    tickers = {r.ticker for r in records}

    # The profitable, beaten-down name is surfaced...
    assert "DEEPUS" in tickers
    # ...the never-profitable name is the one hard auto-drop.
    assert "JUNKUS" not in tickers

    deep = next(r for r in records if r.ticker == "DEEPUS")
    assert deep.rank == 1
    assert deep.pct_off_ath >= 50
    assert deep.pct_above_52w_low <= 20
    assert deep.quality_score is not None and deep.quality_score > 0
    assert deep.writeup and "DEEPUS" in deep.writeup
    assert 0 <= deep.data_confidence <= 1
    # bear/base/bull must all be present (never a single point estimate)
    assert deep.upside_bear is not None
    assert deep.upside_base is not None
    assert deep.upside_bull is not None


def test_floor_requires_present_data():
    cfg = load_config()
    r = StockRecord(ticker="X", market_cap=None, avg_dollar_volume=5e6, years_listed=10)
    assert floor.apply_floor([r], cfg) == []  # missing market cap fails the floor


def test_floor_uses_per_currency_threshold():
    cfg = load_config()
    # Same nominal market cap (5e9), different native currency. $5B clears the
    # USD floor; ¥5B (~$33M) must fail the much larger JPY floor — so a JPY
    # micro-cap can't slip a USD-sized floor.
    usd = StockRecord(ticker="U", currency="USD", market_cap=5e9,
                      avg_dollar_volume=5e8, years_listed=10)
    jpy = StockRecord(ticker="J", currency="JPY", market_cap=5e9,
                      avg_dollar_volume=5e8, years_listed=10)
    kept = {r.ticker for r in floor.apply_floor([usd, jpy], cfg)}
    assert "U" in kept
    assert "J" not in kept


def test_valuation_ranks_but_does_not_gate():
    cfg = load_config()
    # Two names: one with strong base upside, one weak. Both must survive Stage 4.
    strong = StockRecord(ticker="A", price=10, market_cap=1e9,
                         revenue_history=[1e9], ebit_margin_history=[0.2],
                         quality_score=80)
    weak = StockRecord(ticker="B", price=10, market_cap=1e9,
                       revenue_history=[1e9], ebit_margin_history=[0.01],
                       quality_score=20)
    ranked = valuation.value_stocks([weak, strong], cfg)
    assert len(ranked) == 2                      # nothing dropped by valuation
    assert ranked[0].ticker == "A"               # stronger upside ranks first
    assert all(r.rank is not None for r in ranked)


def test_confidence_weighted_ranking_reorders_but_keeps_all():
    cfg = load_config()
    # Raw upside would rank NOISY (100%) above SOLID (60%); confidence weighting
    # flips it (100%*0.5=0.50 < 60%*0.95=0.57) — solid high-confidence name wins.
    noisy = StockRecord(ticker="NOISY", upside_base=1.0, data_confidence=0.5, quality_score=30)
    solid = StockRecord(ticker="SOLID", upside_base=0.6, data_confidence=0.95, quality_score=90)
    ranked = valuation.rank_records([noisy, solid], cfg)
    assert [r.ticker for r in ranked] == ["SOLID", "NOISY"]
    # nothing dropped; raw upside & confidence untouched (still visible columns)
    assert {r.ticker for r in ranked} == {"NOISY", "SOLID"}
    assert noisy.upside_base == 1.0 and solid.upside_base == 0.6
    assert noisy.data_confidence == 0.5 and solid.data_confidence == 0.95


def test_ranking_toggle_off_uses_raw_upside():
    cfg = load_config()
    cfg.raw["valuation"]["confidence_weighted_ranking"] = False
    noisy = StockRecord(ticker="NOISY", upside_base=1.0, data_confidence=0.5, quality_score=30)
    solid = StockRecord(ticker="SOLID", upside_base=0.6, data_confidence=0.95, quality_score=90)
    ranked = valuation.rank_records([noisy, solid], cfg)
    assert [r.ticker for r in ranked] == ["NOISY", "SOLID"]  # raw upside ordering


def test_ath_confidence_scored():
    cfg = load_config()
    records = run_pipeline(cfg, allow_fetch=False)
    deep = next(r for r in records if r.ticker == "DEEPUS")
    # ~6y history -> approximate ATH, confidence between 0 and 1, flagged as approx.
    assert deep.ath_is_approx is True
    assert 0 < deep.ath_confidence < 1
