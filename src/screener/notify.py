"""Result reporting — terminal log + on-disk markdown summary.

Email/SMTP delivery was removed; results are surfaced by a dashboard frontend.
This module no longer sends anything over the network. It:
  - logs a concise ranked summary to the terminal, and
  - writes the full markdown report (ranked table + write-ups) to
    data/results/<run_date>.md alongside the CSV/JSON that persist.py saves.

Highlights new entrants vs. the prior run, and prints a heartbeat on 0 results /
a clear error on failure so a silent break is still visible in the logs.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from .config import Config
from .schema import StockRecord

log = logging.getLogger("screener.notify")

_RESULTS_DIR = Path("data/results")


def _fmt_pct(x, nd=0):
    return "n/a" if x is None else f"{x*100:.{nd}f}%"


def build_body(records: list[StockRecord], run_date: str) -> str:
    """Full human-readable markdown report (ranked table + write-ups)."""
    new = [r for r in records if r.is_new_entrant]
    lines = [
        f"# Deep-Value Screen — {run_date}",
        "",
        f"{len(records)} names passed. {len(new)} new vs. prior run.",
        "Research/idea-generation only — not investment advice. You make the call.",
        "",
        "## Ranked shortlist",
        "",
        "| # | Ticker | Region | %offATH | %>52wLow | Qual | Upside(base) | Mult | NetDebt/EBITDA | Conf | Note |",
        "|--:|--------|--------|--------:|---------:|-----:|-------------:|------|---------------:|-----:|------|",
    ]
    for r in records:
        star = " 🆕" if r.is_new_entrant else ""
        approx = "~" if r.ath_is_approx else ""
        note = r.prior_decision or ""
        mult = f"{r.norm_multiple}x" if r.norm_multiple is not None else "n/a"
        if r.multiple_from_fallback:
            mult += " (fb)"
        lines.append(
            f"| {r.rank} | {r.ticker}{star} | {r.region} | "
            f"{approx}{r.pct_off_ath}% | {r.pct_above_52w_low}% | "
            f"{r.quality_score} | {_fmt_pct(r.upside_base)} | {mult} | "
            f"{r.net_debt_to_ebitda if r.net_debt_to_ebitda is not None else 'n/a'} | "
            f"{r.data_confidence} | {note} |"
        )
    lines += ["", "## Write-ups", ""]
    for r in records:
        lines.append(r.writeup)
        lines.append("\n---\n")
    return "\n".join(lines)


def _write_markdown(body: str, run_date: str) -> Path:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = _RESULTS_DIR / f"{run_date}.md"
    out.write_text(body)
    return out


def report_results(records: list[StockRecord], cfg: Config,
                   run_date: Optional[str] = None,
                   calibration: Optional[str] = None) -> Path:
    """Log a concise summary to the terminal and save the full markdown report."""
    run_date = run_date or date.today().isoformat()
    body = build_body(records, run_date)
    if calibration:
        body += "\n\n" + calibration
    md_path = _write_markdown(body, run_date)

    n_new = sum(r.is_new_entrant for r in records)
    log.info("Results %s: %d names (%d new). Full report: %s",
             run_date, len(records), n_new, md_path)
    for r in records:
        flag = " [NEW]" if r.is_new_entrant else ""
        fb = " [fallback-mult]" if r.multiple_from_fallback else ""
        log.info("  #%s %-10s %-7s offATH %s  qual %s  upside(base) %s  conf %s%s%s",
                 r.rank, r.ticker, r.region,
                 f"{r.pct_off_ath}%" if r.pct_off_ath is not None else "n/a",
                 r.quality_score, _fmt_pct(r.upside_base), r.data_confidence, flag, fb)
    return md_path


def report_heartbeat(cfg: Config, run_date: Optional[str] = None) -> None:
    """Log a heartbeat on a 0-result day so a silent break stays visible."""
    run_date = run_date or date.today().isoformat()
    log.warning("Heartbeat %s: screen ran and surfaced 0 names. If this persists, "
                "check thresholds in config.yaml or data sources.", run_date)


def report_failure(error: str, run_date: Optional[str] = None) -> None:
    """Log a clear failure marker (CI also flags via the non-zero exit code)."""
    run_date = run_date or date.today().isoformat()
    log.error("RUN FAILED %s:\n%s", run_date, error)
