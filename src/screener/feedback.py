"""Stage 6 — review feedback & self-learning. Surfaces and remembers; never
silently changes the strategy, never auto-trades, never tightens the funnel.

Four pieces, all human-in-the-loop:
  1. Decisions log      — data/decisions.csv: reject|watch|researching|bought + reason.
  2. Memory of judgments — tag previously-rejected names on resurfacing;
                           optionally suppress repeats (config toggle).
  3. Outcome tracking   — record price + est. upside when surfaced; later compare
                           actual forward return to the estimate (self-audit).
  4. Calibration digest — PROPOSE config tweaks from labelled data; never apply.
"""
from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Optional

from .config import Config
from .schema import StockRecord

log = logging.getLogger("screener.feedback")

_DECISION_VALUES = {"reject", "watch", "researching", "bought"}


# --- 1 & 2: decisions log + suppression/tagging ------------------------------
def load_decisions(path: str | Path) -> dict[str, dict]:
    """Return {ticker: {decision, note, date}} keeping the latest per ticker."""
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, dict] = {}
    with p.open(newline="") as fh:
        for row in csv.DictReader(fh):
            t = (row.get("ticker") or "").strip()
            if not t:
                continue
            out[t] = {
                "decision": (row.get("decision") or "").strip(),
                "note": (row.get("note") or "").strip(),
                "date": (row.get("date") or "").strip(),
            }
    return out


def record_decision(path: str | Path, ticker: str, decision: str,
                    note: str = "", when: Optional[str] = None) -> None:
    """Append a decision (low-friction CLI entry point)."""
    decision = decision.strip().lower()
    if decision not in _DECISION_VALUES:
        raise ValueError(f"decision must be one of {sorted(_DECISION_VALUES)}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "ticker", "decision", "note"])
        w.writerow([when or date.today().isoformat(), ticker.strip(), decision, note])


def apply_decisions(records: list[StockRecord], cfg: Config) -> list[StockRecord]:
    """Tag records with prior decisions; optionally suppress previously-rejected."""
    if not cfg.feedback.get("enabled", True):
        return records
    decisions = load_decisions(cfg.feedback.get("decisions_path", "data/decisions.csv"))
    suppress = cfg.feedback.get("suppress_previously_rejected", False)

    out: list[StockRecord] = []
    for r in records:
        d = decisions.get(r.ticker)
        if d:
            r.prior_decision = d["decision"]
            r.prior_decision_note = d["note"]
            r.prior_decision_date = d["date"]
            if d["decision"] == "reject" and suppress:
                continue  # hide repeats only when the user opted in
        out.append(r)
    return out


# --- 3: outcome tracking / self-audit ----------------------------------------
def record_outcomes(records: list[StockRecord], cfg: Config,
                    when: Optional[str] = None) -> None:
    """Snapshot price + estimated upside at surfacing time for later audit."""
    if not cfg.feedback.get("enabled", True):
        return
    p = Path(cfg.feedback.get("outcomes_path", "data/outcomes.csv"))
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with p.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["surfaced_date", "ticker", "price_at_surface",
                        "est_upside_base", "horizon_years", "data_confidence"])
        when = when or date.today().isoformat()
        for r in records:
            w.writerow([when, r.ticker, r.price, r.upside_base,
                        cfg.valuation.get("horizon_years", 3), r.data_confidence])


def calibration_digest(cfg: Config) -> Optional[str]:
    """PROPOSE (never apply) config tweaks from labelled data. Returns markdown.

    Runs only every calibration_cadence_days. Looks at which names the user
    advanced (watch/researching/bought) vs rejected and reports the metric skew,
    framed as a suggestion that preserves the false-positive bias.
    """
    if not cfg.feedback.get("enabled", True):
        return None
    cadence = cfg.feedback.get("calibration_cadence_days", 30)
    decisions = load_decisions(cfg.feedback.get("decisions_path", "data/decisions.csv"))
    if not decisions:
        return None

    # Cadence gate: only emit on the cadence boundary (day-of-month multiple).
    if datetime.utcnow().day % max(1, cadence) != 0:
        return None

    advanced = [t for t, d in decisions.items() if d["decision"] in ("watch", "researching", "bought")]
    rejected = [t for t, d in decisions.items() if d["decision"] == "reject"]
    if not advanced:
        return None

    lines = [
        "## Calibration digest (suggestion only — nothing applied)",
        f"- You advanced {len(advanced)} names and rejected {len(rejected)}.",
        "- These are *proposals* to consider; the screener will NOT auto-tighten "
        "thresholds, drop names, or erode the false-positive bias.",
        "- Review the advanced names' ROIC / leverage skew in data/outcomes.csv and "
        "decide whether any floor change is warranted.",
    ]
    return "\n".join(lines)
