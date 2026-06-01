"""Stage 5 — per-stock write-up. engine = "templated" (default, free) | "llm".

Templated: deterministic prose from the computed metrics. Free, reliable, drier.
LLM: richer prose, NOT free — needs ANTHROPIC_API_KEY. The model is given ONLY
the computed metrics (a compact dict), must not introduce outside "facts", every
write-up is labelled a draft to verify, output is capped, and results are cached
on (ticker, hash-of-metrics) so unchanged names aren't regenerated.

Write-ups run ONLY on the final ranked list — never on Stage-2 survivors.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from ..cache import CACHE_ROOT
from ..config import Config
from ..schema import StockRecord

log = logging.getLogger("screener.stage5")

_WRITEUP_CACHE = CACHE_ROOT / "cache" / "writeups.json"

# --- house rules shared with both engines and the methodology skill ----------
_CHART_HINT = {
    "popped-hype": "looks like a popped hype spike — expectations outran fundamentals "
                   "(these often need to fall well past 50%)",
    "cyclical": "looks cyclical/commodity-driven",
    "mispriced-quality": "looks like genuinely mispriced quality",
    "unknown": "chart pattern unclear from available history",
}


def _pct(x, nd=0):
    return "n/a" if x is None else f"{x*100:.{nd}f}%"


def _classify_chart(rec: StockRecord) -> str:
    # Crude heuristic from available signals; the skill documents the full method.
    if rec.pct_off_ath and rec.pct_off_ath > 80 and (rec.quality_score or 0) < 40:
        return "popped-hype"
    if rec.sector in ("Energy", "Basic Materials", "Industrials"):
        return "cyclical"
    if (rec.quality_score or 0) >= 60:
        return "mispriced-quality"
    return "unknown"


def _why_cheap(rec: StockRecord) -> str:
    bits = []
    if rec.net_debt_to_ebitda and rec.net_debt_to_ebitda > 3:
        bits.append("balance-sheet leverage")
    if rec.growth_trend == "declining":
        bits.append("falling revenue")
    if "significant ongoing dilution" in " ".join(rec.quality_flags):
        bits.append("shareholder dilution")
    if rec.pct_off_ath and rec.pct_off_ath > 75:
        bits.append("severe sentiment drawdown")
    return ", ".join(bits) if bits else "broad sell-off / out of favour (reason not obvious from data)"


def _templated(rec: StockRecord) -> str:
    chart = _CHART_HINT[_classify_chart(rec)]
    approx = " (approx — ATH not fully verified)" if rec.ath_is_approx else ""
    lines = [
        f"### {rec.rank}. {rec.name} ({rec.ticker}) — {rec.region}/{rec.exchange}",
        "",
        f"**Chart context.** Public ~{rec.years_listed or '?'}y; down "
        f"{rec.pct_off_ath}%{approx} from high and {rec.pct_above_52w_low}% above its "
        f"52-week low. Pattern {chart}.",
        "",
        f"**Business.** {rec.sector or 'sector n/a'} company. "
        f"(Plain-language description requires the LLM engine or manual fill.)",
        "",
        f"**Quality.** Score {rec.quality_score}/100. "
        f"Avg ROIC {_pct(_avg(rec.roic_history),1)}, avg EBIT margin "
        f"{_pct(_avg(rec.ebit_margin_history),1)}, revenue trend: {rec.growth_trend}. "
        f"{rec.dilution_note}. Net debt/EBITDA: {rec.net_debt_to_ebitda}. "
        f"Accounting: {rec.accounting_standard}.",
    ]
    if rec.quality_flags:
        lines.append(f"  - Flags: {'; '.join(rec.quality_flags)}.")
    lines += [
        "",
        f"**Upside (2-3yr annualized).** bear {_pct(rec.upside_bear,0)} / "
        f"base {_pct(rec.upside_base,0)} / bull {_pct(rec.upside_bull,0)}. "
        f"Fair value bear/base/bull: {rec.fair_value_bear}/{rec.fair_value_base}/"
        f"{rec.fair_value_bull} vs price {rec.price}. "
        f"Norm margin {_pct(rec.norm_margin,1)}, norm multiple {rec.norm_multiple}x "
        f"({rec.multiple_basis or 'n/a'}).",
    ]
    if rec.multiple_from_fallback:
        lines.append(
            "  - ⚠️ Multiple is a sector/quality **fallback band** (< 3 usable years of "
            "historical EV/EBIT(DA)) — not derived from this company's own history; "
            "data-confidence lowered accordingly."
        )
    lines += [
        "",
        f"**Why it's cheap.** {_why_cheap(rec)}.",
        f"_Data confidence: {rec.data_confidence}._",
    ]
    if rec.prior_decision:
        lines.append(f"_Previously {rec.prior_decision} {rec.prior_decision_date}: "
                     f"{rec.prior_decision_note}._")
    return "\n".join(lines)


def _avg(xs):
    xs = [x for x in (xs or []) if x is not None]
    return sum(xs) / len(xs) if xs else None


def _metrics_payload(rec: StockRecord) -> dict:
    """The ONLY data the LLM is allowed to see — pure computed numbers."""
    return {
        "ticker": rec.ticker, "name": rec.name, "region": rec.region,
        "sector": rec.sector, "years_listed": rec.years_listed,
        "pct_off_ath": rec.pct_off_ath, "ath_is_approx": rec.ath_is_approx,
        "pct_above_52w_low": rec.pct_above_52w_low,
        "quality_score": rec.quality_score, "quality_flags": rec.quality_flags,
        "avg_roic": _avg(rec.roic_history), "avg_ebit_margin": _avg(rec.ebit_margin_history),
        "growth_trend": rec.growth_trend, "dilution_note": rec.dilution_note,
        "net_debt_to_ebitda": rec.net_debt_to_ebitda,
        "accounting_standard": rec.accounting_standard,
        "price": rec.price, "norm_margin": rec.norm_margin, "norm_multiple": rec.norm_multiple,
        "fair_value": [rec.fair_value_bear, rec.fair_value_base, rec.fair_value_bull],
        "upside": [rec.upside_bear, rec.upside_base, rec.upside_bull],
        "data_confidence": rec.data_confidence,
    }


def _metrics_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _load_cache() -> dict:
    if _WRITEUP_CACHE.exists():
        try:
            return json.loads(_WRITEUP_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(d: dict) -> None:
    _WRITEUP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _WRITEUP_CACHE.write_text(json.dumps(d))
    except Exception:  # pragma: no cover
        pass


_LLM_SYSTEM = (
    "You are a buy-side analyst writing a terse draft note. You may use ONLY the "
    "numbers in the provided JSON. Do NOT introduce any outside facts, news, names, "
    "or figures not present in the JSON. If something is unknown, say so. Cover: "
    "chart context, business (only if inferable from sector — otherwise say "
    "'verify business description'), quality summary with red flags, the bear/base/"
    "bull upside math, and one line on why it's cheap. Label clearly as a DRAFT."
)


def _llm(rec: StockRecord, cfg: Config, cache: dict) -> str:
    payload = _metrics_payload(rec)
    key = f"{rec.ticker}:{_metrics_hash(payload)}"
    if key in cache:
        return cache[key]
    try:
        import os
        from anthropic import Anthropic  # type: ignore

        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=cfg.write_up.get("model", "claude-haiku-4-5-20251001"),
            max_tokens=cfg.write_up.get("max_output_tokens", 600),
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
        )
        text = "**[DRAFT — verify all claims]**\n\n" + "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        )
    except Exception as e:
        log.warning("LLM write-up failed for %s, falling back to templated: %s", rec.ticker, e)
        return _templated(rec)

    cache[key] = text
    return text


def generate_writeups(records: list[StockRecord], cfg: Config) -> list[StockRecord]:
    engine = cfg.write_up.get("engine", "templated")
    cache = _load_cache() if engine == "llm" else {}
    for r in records:
        if engine == "llm":
            r.writeup = _llm(r, cfg, cache)
            r.writeup_is_draft = True
        else:
            r.writeup = _templated(r)
            r.writeup_is_draft = False
    if engine == "llm":
        _save_cache(cache)
    log.info("Stage 5 write-ups: %d generated (engine=%s)", len(records), engine)
    return records
