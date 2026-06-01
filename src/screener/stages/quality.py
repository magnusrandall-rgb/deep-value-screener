"""Stage 3 — quality assessment. Score, don't hard-exclude.

The ONLY auto-drop here is obvious junk: never profitable in any of the last N
years. Everything else is scored (scoring.py) and flagged, preserving the
false-positive bias. Pulls fundamentals from cache, fills history fields, sets
growth trend / dilution note, leverage flag, accounting standard, and the
per-name quality + data-confidence scores.
"""
from __future__ import annotations

import logging

from .. import cache, scoring
from ..config import Config
from ..schema import StockRecord

log = logging.getLogger("screener.stage3")


def _dilution_note(share_counts: list[float]) -> str:
    sc = [s for s in share_counts if s]
    if len(sc) < 2:
        return "share-count history unavailable"
    change = (sc[0] - sc[-1]) / sc[-1]
    pct = round(change * 100, 1)
    if change <= -0.02:
        return f"net buybacks (~{pct}% shares over period) — positive"
    if change >= 0.05:
        # A one-off jump then flat usually means an acquisition; flag for review.
        steps = [sc[i] / sc[i + 1] - 1 for i in range(len(sc) - 1) if sc[i + 1]]
        big = [s for s in steps if s > 0.15]
        if len(big) == 1:
            return (f"share count +{pct}% — looks like a one-off (acquisition?); "
                    "check whether per-share profit/margins/ROIC improved after")
        return f"steady dilution (+{pct}% shares) — negative"
    return f"roughly flat share count ({pct}%)"


def assess_quality(records: list[StockRecord], cfg: Config,
                   allow_fetch: bool = True) -> list[StockRecord]:
    q = cfg.quality
    min_roic = q.get("min_roic", 0.07)
    min_years = q.get("min_years_history", 5)
    drop_n = q.get("drop_if_never_profitable_last_n_years", 5)
    a_penalty = cfg.universe.get("a_share_confidence_penalty", 1.0)

    kept: list[StockRecord] = []
    for r in records:
        f = cache.get_fundamentals(r.ticker, r.region, allow_fetch=allow_fetch)

        r.roic_history = f.get("roic", []) or []
        r.roce_history = f.get("roce", []) or []
        r.revenue_history = f.get("revenue", []) or []
        r.ebit_margin_history = f.get("ebit_margin", []) or []
        r.gross_margin_history = f.get("gross_margin", []) or []
        r.fcf_margin_history = f.get("fcf_margin", []) or []
        r.share_count_history = f.get("shares_aligned") or f.get("share_count", []) or []
        r.net_debt_to_ebitda = f.get("net_debt_to_ebitda")
        # Date-aligned series for the Stage-4 historical EV/EBIT(DA) multiple.
        r.ebit_history = f.get("ebit_aligned") or f.get("ebit", []) or []
        r.ebitda_history = f.get("ebitda_aligned") or f.get("ebitda", []) or []
        r.total_debt_history = f.get("total_debt", []) or []
        r.cash_history = f.get("cash", []) or []
        r.period_end_dates = f.get("period_end_dates", []) or []
        r.accounting_standard = f.get("accounting_standard", "")
        if f.get("sector") and not r.sector:
            r.sector = f["sector"]

        # ---- the single hard auto-drop: never profitable in last N years -----
        net_income = f.get("net_income", []) or []
        recent_ni = net_income[:drop_n]
        if recent_ni and all(ni <= 0 for ni in recent_ni):
            log.debug("dropping %s: never profitable in last %d yrs", r.ticker, drop_n)
            continue

        # ---- annotate, never gate -------------------------------------------
        r.growth_trend = scoring.trend(r.revenue_history)
        r.dilution_note = _dilution_note(r.share_count_history)
        if r.revenue_history and len(r.revenue_history) < min_years:
            r.quality_flags.append(
                f"only {len(r.revenue_history)} yrs history (< {min_years} required) — low confidence"
            )

        score, flags = scoring.compute_quality_score(r, min_roic)
        r.quality_score = round(score, 1)
        r.quality_flags = list(r.quality_flags) + flags

        is_a_share = r.ticker.endswith((".SS", ".SZ"))
        r.data_confidence = scoring.compute_data_confidence(
            r, r.region, a_share_penalty=a_penalty, is_a_share=is_a_share
        )

        kept.append(r)

    log.info("Stage 3 quality: %d -> %d (auto-dropped only obvious junk)",
             len(records), len(kept))
    return kept
