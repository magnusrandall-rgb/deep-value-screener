"""Quality score and data-confidence score — both 0..100 / 0..1, shared by stages.

Scoring is deliberate, transparent, and additive so a human can reason about why
a name ranked where it did. Nothing here hard-excludes (that lives in the floor
and the single Stage-3 auto-drop); these produce the numbers used to RANK.
"""
from __future__ import annotations

from statistics import mean
from typing import Optional

from .schema import StockRecord


def _avg(xs: list[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else None


def _trend(xs: list[float]) -> str:
    """xs is newest..oldest. Compare recent half vs older half."""
    xs = [x for x in xs if x is not None]
    if len(xs) < 3:
        return "unknown"
    half = len(xs) // 2
    recent, older = _avg(xs[:half]), _avg(xs[half:])
    if recent is None or older is None:
        return "unknown"
    if recent > older * 1.05:
        return "growing"
    if recent < older * 0.95:
        return "declining"
    return "stabilizing"


def compute_quality_score(rec: StockRecord, min_roic: float) -> tuple[float, list[str]]:
    """Return (score 0..100, flags). Additive, capped at 100."""
    score = 0.0
    flags: list[str] = []

    # Returns on capital (max 30) — reward consistent ROIC above the threshold.
    roic_avg = _avg(rec.roic_history)
    if roic_avg is not None:
        if roic_avg >= min_roic:
            score += 20
            above = sum(1 for r in rec.roic_history if r >= min_roic)
            score += 10 * (above / max(1, len(rec.roic_history)))
        elif roic_avg > 0:
            score += 8
        else:
            flags.append("negative average ROIC")
    else:
        flags.append("ROIC unavailable")

    # Margin durability (max 20) — EBIT margin emphasised, esp. non-US (IFRS).
    ebit_avg = _avg(rec.ebit_margin_history)
    if ebit_avg is not None:
        if ebit_avg > 0.15:
            score += 20
        elif ebit_avg > 0.05:
            score += 12
        elif ebit_avg > 0:
            score += 5
        else:
            flags.append("negative average EBIT margin")
    else:
        flags.append("EBIT margin unavailable")

    # Growth trend (max 20) — reward stabilizing/growing, penalise decline.
    t = _trend(rec.revenue_history)
    score += {"growing": 20, "stabilizing": 14, "unknown": 6, "declining": 0}[t]
    if t == "declining":
        flags.append("revenue still in structural decline")

    # Dilution (max 15) — fewer shares over time is good, steady dilution bad.
    sc = [s for s in rec.share_count_history if s]
    if len(sc) >= 2:
        change = (sc[0] - sc[-1]) / sc[-1]  # newest vs oldest
        if change <= -0.02:
            score += 15  # net buybacks
        elif change <= 0.01:
            score += 10
        elif change <= 0.05:
            score += 4
            flags.append("mild ongoing dilution")
        else:
            flags.append("significant ongoing dilution")

    # FCF positivity (max 15).
    fcf_avg = _avg(rec.fcf_margin_history)
    if fcf_avg is not None:
        if fcf_avg > 0.05:
            score += 15
        elif fcf_avg > 0:
            score += 8
        else:
            flags.append("negative average FCF margin")

    # Balance-sheet flag (no score impact — surfaced prominently).
    if rec.net_debt_to_ebitda is not None and rec.net_debt_to_ebitda > 4:
        flags.append(f"high leverage: net debt/EBITDA = {rec.net_debt_to_ebitda}")

    return min(score, 100.0), flags


def compute_data_confidence(rec: StockRecord, region: str,
                            a_share_penalty: float = 1.0,
                            is_a_share: bool = False) -> float:
    """0..1 overall trust. Starts from a per-region prior, adjusted by coverage."""
    base = {"US": 0.95, "Japan": 0.85, "Europe": 0.80, "China": 0.55}.get(region, 0.5)
    conf = base

    # ATH reliability feeds directly in.
    conf *= 0.6 + 0.4 * max(0.0, min(1.0, rec.ath_confidence))

    # Penalise missing fundamentals history.
    have = sum(bool(x) for x in (
        rec.roic_history, rec.ebit_margin_history, rec.revenue_history,
        rec.fcf_margin_history, rec.share_count_history,
    ))
    conf *= 0.5 + 0.5 * (have / 5)

    if is_a_share:
        conf *= a_share_penalty

    return round(max(0.0, min(1.0, conf)), 2)


# Re-export for stages that want the trend helper directly.
trend = _trend
