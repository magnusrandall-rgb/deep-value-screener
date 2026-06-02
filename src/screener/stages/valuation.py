"""Stage 4 — valuation / upside. RANKING INPUT, never a hard filter.

For each survivor we derive a normalized margin and a **normalized valuation
multiple from the company's OWN history** — the median historical EV/EBIT (and,
if that lacks enough usable years, EV/EBITDA) over available years with the
single highest and lowest year trimmed. Only when fewer than
`min_years_for_historical_multiple` usable years exist do we fall back to a
sector/quality band — and when we do, we set a flag and lower data_confidence.
The multiple is NEVER a pure function of the quality score.

Bear/base/bull fair values come from config deltas on both the margin and the
multiple. Names below the return hurdle are kept but ranked lower — a noisy
fair-value estimate must never silently drop a good idea.

Ranking is by base-case upside, by default weighted by data_confidence
(`confidence_weighted_ranking`, default true) so a high-upside but low-confidence
name ranks below a solid, high-confidence one. Raw upside and confidence stay as
separate visible columns; only the sort order changes — nothing is filtered.

Explicit caveat carried on every record: "normalized from history" can mislead
during a genuine structural de-rating (the market may have re-rated correctly).
"""
from __future__ import annotations

import logging
from statistics import median
from typing import Optional

import pandas as pd

from .. import cache
from ..config import Config
from ..schema import StockRecord

log = logging.getLogger("screener.stage4")


def _norm_margin(rec: StockRecord) -> Optional[float]:
    xs = [m for m in rec.ebit_margin_history if m is not None]
    return median(xs) if xs else None


def _norm_ebitda_margin(rec: StockRecord) -> Optional[float]:
    pairs = [
        e / r for e, r in zip(rec.ebitda_history, rec.revenue_history)
        if e is not None and r
    ]
    return median(pairs) if pairs else None


def _trimmed_median(xs: list[float], trim: bool) -> float:
    """Median, dropping the single highest & lowest year when trimming and >= 5."""
    xs = sorted(xs)
    if trim and len(xs) >= 5:
        xs = xs[1:-1]
    return median(xs)


def _price_on_or_before(hist: pd.DataFrame, date_str: str) -> Optional[float]:
    """Cached close at-or-before a fiscal period-end (nearest earlier trading day)."""
    if hist is None or hist.empty:
        return None
    try:
        d = pd.Timestamp(date_str)
    except Exception:
        return None
    sub = hist.loc[hist.index <= d]
    if sub.empty:
        return float(hist["Close"].iloc[0])  # date precedes our history
    return float(sub["Close"].iloc[-1])


def _current_net_debt(rec: StockRecord) -> float:
    """Best-available current net debt (used to convert EV -> equity value)."""
    td, csh = rec.total_debt_history, rec.cash_history
    if td and csh and td[0] is not None and csh[0] is not None:
        return td[0] - csh[0]
    if rec.net_debt_to_ebitda is not None and rec.ebitda_history and rec.ebitda_history[0]:
        return rec.net_debt_to_ebitda * rec.ebitda_history[0]
    return 0.0


def _ev_multiples(rec: StockRecord, hist: pd.DataFrame,
                  earnings: list[float]) -> list[float]:
    """Per-year EV / earnings for years with positive earnings & a known price.

    EV_t = price_t * shares_t + net_debt_t, paired to the fiscal period-end date.
    """
    dates = rec.period_end_dates
    shares = rec.share_count_history
    td, csh = rec.total_debt_history, rec.cash_history
    n = min(len(dates), len(earnings), len(shares))
    out: list[float] = []
    for i in range(n):
        e = earnings[i]
        if e is None or e <= 0:
            continue
        sh = shares[i]
        if not sh:
            continue
        price = _price_on_or_before(hist, dates[i])
        if price is None:
            continue
        debt_i = td[i] if i < len(td) and td[i] is not None else 0.0
        cash_i = csh[i] if i < len(csh) and csh[i] is not None else 0.0
        ev = price * sh + (debt_i - cash_i)
        if ev <= 0:
            continue
        out.append(ev / e)
    return out


def _historical_multiple(rec: StockRecord, cfg: Config) -> tuple[float, str, bool]:
    """Return (multiple, basis, from_fallback).

    Prefers median historical EV/EBIT, then EV/EBITDA; falls back to the
    sector/quality band only when neither has enough usable years.
    """
    v = cfg.valuation
    min_years = v.get("min_years_for_historical_multiple", 3)
    trim = v.get("multiple_outlier_trim", True)
    hist = cache.get_price_history(rec.ticker, allow_fetch=False)

    for basis, earnings in (("EV/EBIT", rec.ebit_history),
                            ("EV/EBITDA", rec.ebitda_history)):
        mults = _ev_multiples(rec, hist, earnings)
        # discard non-positive / absurd multiples before counting usable years
        mults = [m for m in mults if 0 < m < 100]
        if len(mults) >= min_years:
            return round(_trimmed_median(mults, trim), 1), basis, False

    # --- fallback band (the ONLY place quality/sector enters the multiple) ----
    lo, hi = v.get("fallback_multiple_band", [8, 16])
    q = rec.quality_score if rec.quality_score is not None else 50.0
    band = lo + (q / 100.0) * (hi - lo)
    return round(band, 1), "fallback-band", True


def _ranking_key(r: StockRecord, hurdle: float, confidence_weighted: bool) -> tuple:
    """Sort key (higher = better, used with reverse=True).

    Primary ordering is base-case upside, optionally weighted by data_confidence
    so a noisy high-upside name ranks below a solid name with high confidence.
    Raw upside and confidence remain untouched on the record (both stay visible);
    only the ORDER changes — nothing is dropped, preserving the false-positive bias.
    Names with no upside estimate sink to the bottom but are still kept.
    """
    if r.upside_base is None:
        return (0, -99.0, r.quality_score or 0, r.data_confidence or 0.0)
    base = r.upside_base
    conf = r.data_confidence if r.data_confidence is not None else 0.0
    primary = base * conf if confidence_weighted else base
    meets = 1 if base >= hurdle else 0  # above-hurdle names float up, others kept
    return (meets, primary, r.quality_score or 0, conf)


def rank_records(records: list[StockRecord], cfg: Config) -> list[StockRecord]:
    """Order the list and assign 1-based ranks. Ranking only — never filters."""
    v = cfg.valuation
    hurdle = v.get("annual_return_hurdle", 0.30)
    confidence_weighted = v.get("confidence_weighted_ranking", True)
    ranked = sorted(
        records,
        key=lambda r: _ranking_key(r, hurdle, confidence_weighted),
        reverse=True,
    )
    for i, r in enumerate(ranked, 1):
        r.rank = i
    log.info("Stage 4 valuation: ranked %d names (hurdle %.0f%% used for ordering only, "
             "confidence_weighted=%s)", len(ranked), hurdle * 100, confidence_weighted)
    return ranked


def value_stocks(records: list[StockRecord], cfg: Config) -> list[StockRecord]:
    v = cfg.valuation
    horizon = v.get("horizon_years", 3)
    m_deltas = v.get("bear_base_bull_deltas", {}).get("margin", [-0.3, 0.0, 0.3])
    mult_deltas = v.get("bear_base_bull_deltas", {}).get("multiple", [-0.25, 0.0, 0.25])
    fallback_penalty = v.get("fallback_multiple_confidence_penalty", 0.85)

    for r in records:
        assumptions: list[str] = [
            "Fair value = normalized margin x revenue x normalized multiple, less "
            "current net debt, per share.",
            "Normalized multiple = median of the company's own historical "
            "EV/EBIT (then EV/EBITDA), outlier years trimmed.",
            "CAVEAT: normalization can mislead during a genuine structural de-rating — "
            "the market may have re-rated this name correctly and permanently.",
        ]

        # ---- normalized multiple from the company's OWN history --------------
        base_multiple, basis, from_fallback = _historical_multiple(r, cfg)
        r.norm_multiple = base_multiple
        r.multiple_basis = basis
        r.multiple_from_fallback = from_fallback
        if from_fallback:
            assumptions.append(
                "Historical EV/EBIT(DA) had < "
                f"{v.get('min_years_for_historical_multiple', 3)} usable years — "
                "used a sector/quality fallback band; data-confidence lowered."
            )
            r.data_confidence = round(max(0.0, r.data_confidence * fallback_penalty), 2)

        # ---- normalized margin (basis matches the multiple) ------------------
        if basis == "EV/EBITDA":
            norm_margin = _norm_ebitda_margin(r)
        else:
            norm_margin = _norm_margin(r)
        revenue = r.revenue_history[0] if r.revenue_history else None
        r.norm_margin = round(norm_margin, 4) if norm_margin is not None else None

        if norm_margin is None or not revenue or not r.market_cap or not r.price:
            r.valuation_assumptions = assumptions + ["insufficient data for upside — flagged"]
            r.upside_bear = r.upside_base = r.upside_bull = None
            continue

        # Negative/zero normalized margin: no positive earnings to normalize from —
        # the method does not apply. FLAG it, don't emit a bogus 0 / -100%.
        if norm_margin <= 0:
            r.valuation_assumptions = assumptions + [
                f"normalized margin <= 0 ({basis} basis) — never reliably profitable, "
                "so the normalize-from-history method does not apply; upside not estimated."
            ]
            r.upside_bear = r.upside_base = r.upside_bull = None
            continue

        shares = r.market_cap / r.price if r.price else None
        if not shares:
            r.valuation_assumptions = assumptions + ["share count unavailable — flagged"]
            r.upside_bear = r.upside_base = r.upside_bull = None
            continue

        net_debt = _current_net_debt(r)

        def fair_value(margin_delta: float, mult_delta: float) -> float:
            norm_earnings = revenue * norm_margin * (1 + margin_delta)
            ev = norm_earnings * base_multiple * (1 + mult_delta)
            equity = ev - net_debt
            return max(0.0, equity / shares)

        r.fair_value_bear = round(fair_value(m_deltas[0], mult_deltas[0]), 2)
        r.fair_value_base = round(fair_value(m_deltas[1], mult_deltas[1]), 2)
        r.fair_value_bull = round(fair_value(m_deltas[2], mult_deltas[2]), 2)

        def annualized(fv: float) -> float:
            if r.price <= 0:
                return 0.0
            return round((fv / r.price) ** (1 / horizon) - 1, 4)

        r.upside_bear = annualized(r.fair_value_bear)
        r.upside_base = annualized(r.fair_value_base)
        r.upside_bull = annualized(r.fair_value_bull)
        r.valuation_assumptions = assumptions

    # ---- rank (base-case upside, optionally confidence-weighted) -------------
    return rank_records(records, cfg)
