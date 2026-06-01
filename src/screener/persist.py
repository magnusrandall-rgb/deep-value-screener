"""Daily results storage + run-to-run diffing.

Each run is written to data/results/<YYYY-MM-DD>.json (full records) and a CSV
shortlist. `diff_against_prior` marks new entrants vs. the most recent prior run
so notify.py can highlight them.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from .cache import CACHE_ROOT
from .schema import StockRecord, SUMMARY_COLUMNS

log = logging.getLogger("screener.persist")

_RESULTS_DIR = CACHE_ROOT / "results"


def _results_path(run_date: str) -> Path:
    return _RESULTS_DIR / f"{run_date}.json"


def latest_prior_run(before: Optional[str] = None) -> Optional[str]:
    if not _RESULTS_DIR.exists():
        return None
    runs = sorted(p.stem for p in _RESULTS_DIR.glob("*.json"))
    runs = [r for r in runs if not before or r < before]
    return runs[-1] if runs else None


def load_run(run_date: str) -> list[StockRecord]:
    p = _results_path(run_date)
    if not p.exists():
        return []
    return [StockRecord.from_dict(d) for d in json.loads(p.read_text())]


def diff_against_prior(records: list[StockRecord]) -> list[StockRecord]:
    """Mark is_new_entrant for tickers absent from the most recent prior run."""
    today = date.today().isoformat()
    prior_run = latest_prior_run(before=today)
    prior_tickers = {r.ticker for r in load_run(prior_run)} if prior_run else set()
    for r in records:
        r.is_new_entrant = r.ticker not in prior_tickers if prior_tickers else True
    return records


def save_run(records: list[StockRecord], run_date: Optional[str] = None) -> tuple[Path, Path]:
    run_date = run_date or date.today().isoformat()
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = _results_path(run_date)
    json_path.write_text(json.dumps([r.to_dict() for r in records], default=str))

    csv_path = _RESULTS_DIR / f"{run_date}.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(SUMMARY_COLUMNS)
        for r in records:
            d = r.to_dict()
            w.writerow([d.get(c, "") for c in SUMMARY_COLUMNS])

    log.info("saved run %s: %d records -> %s", run_date, len(records), csv_path)
    return json_path, csv_path
