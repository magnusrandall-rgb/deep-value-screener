"""The only entrypoint.

Commands:
    python -m screener.run                 # full daily run (fetch, log, save)
    python -m screener.run --offline       # cache/fixture only, no network
    python -m screener.run decision TICKER reject "too levered"   # log a decision
    python -m screener.run audit           # print outcome audit (est vs actual)

Results are logged to the terminal and saved to data/results/ (CSV, JSON, and a
markdown report); a dashboard frontend consumes those. There is no email step.
Exit code is non-zero on failure so CI can detect it.
"""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import date

from . import feedback, notify, persist
from .config import load_config
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# yfinance logs an ERROR per delisted/invalid ticker ("possibly delisted",
# "Period 'max' is invalid" for warrants/units). That's expected noise — we
# return an empty frame and skip such names — so quiet its logger to keep the
# pipeline's own output readable.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
log = logging.getLogger("screener.run")


def _cmd_decision(args: list[str]) -> int:
    cfg = load_config()
    if len(args) < 2:
        print("usage: decision TICKER reject|watch|researching|bought [note]")
        return 2
    ticker, decision = args[0], args[1]
    note = args[2] if len(args) > 2 else ""
    feedback.record_decision(cfg.feedback.get("decisions_path", "data/decisions.csv"),
                             ticker, decision, note)
    print(f"recorded: {ticker} -> {decision} ({note})")
    return 0


def _cmd_audit() -> int:
    """Self-audit: compare recorded estimates to subsequent realized prices."""
    cfg = load_config()
    from . import cache
    import csv
    from pathlib import Path

    p = Path(cfg.feedback.get("outcomes_path", "data/outcomes.csv"))
    if not p.exists():
        print("no outcomes recorded yet")
        return 0
    rows = list(csv.DictReader(p.open()))
    print(f"{'ticker':10} {'surfaced':12} {'est_base':>9} {'actual':>9}")
    for r in rows:
        hist = cache.get_price_history(r["ticker"], allow_fetch=False)
        actual = ""
        if not hist.empty and r.get("price_at_surface"):
            try:
                actual = f"{(hist['Close'].iloc[-1]/float(r['price_at_surface'])-1)*100:.0f}%"
            except Exception:
                actual = "?"
        print(f"{r['ticker']:10} {r['surfaced_date']:12} "
              f"{r.get('est_upside_base',''):>9} {actual:>9}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if argv and argv[0] == "decision":
        return _cmd_decision(argv[1:])
    if argv and argv[0] == "audit":
        return _cmd_audit()

    offline = "--offline" in argv
    force_universe = "--refresh-universe" in argv
    run_date = date.today().isoformat()

    cfg = load_config()
    stats: dict = {}
    try:
        records = run_pipeline(cfg, allow_fetch=not offline,
                               force_universe=force_universe, stats=stats)
    except Exception:
        tb = traceback.format_exc()
        notify.report_failure(tb, run_date)
        return 1

    persist.save_run(records, run_date, universe_size=stats.get("universe_size"))
    feedback.record_outcomes(records, cfg, when=run_date)
    digest = feedback.calibration_digest(cfg)

    if not records:
        notify.report_heartbeat(cfg, run_date)
    else:
        notify.report_results(records, cfg, run_date, calibration=digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
