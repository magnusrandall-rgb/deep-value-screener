"""FastAPI backend for the deep-value screener frontend.

Serves the shortlist the screener already saves to ``data/results/<date>.json``
and the decisions log at ``data/decisions.csv`` — the SAME files the CLI writes,
so there is no second source of truth and no database (yet). The frontend (a
React dev server) reads runs and posts review decisions through these endpoints.

Run it from the project root so ``data/`` and ``config.yaml`` resolve:

    uvicorn src.api.main:app --reload

Endpoints (all under /api):
    GET  /api/runs            list of past run dates with result counts
    GET  /api/runs/latest     the most recent run's full results
    GET  /api/runs/{date}     a specific run's results (date = YYYY-MM-DD)
    POST /api/decisions       log a decision (ticker, decision, note)
    GET  /api/decisions       all decisions, keyed by ticker
"""
from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# The screener package is installed (`pip install -e .`), so we reuse its config
# loader and the persist/feedback helpers rather than re-deriving file paths.
from screener import persist, feedback
from screener.config import load_config

app = FastAPI(
    title="Deep-Value Screener API",
    version="0.1.0",
    description="Read-only access to saved screener runs + the decisions log.",
)

# Allow the local React dev server (any localhost port) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _run_dates() -> list[str]:
    """All saved run dates, newest first."""
    d = persist._RESULTS_DIR
    if not d.exists():
        return []
    return sorted((p.stem for p in d.glob("*.json")), reverse=True)


def _load_records(run_date: str) -> list[dict]:
    """Raw record dicts for a run (reads the JSON the screener wrote)."""
    path = persist._results_path(run_date)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as e:  # corrupt/partial file — surface as a 500, don't crash
        raise HTTPException(status_code=500, detail=f"could not read run {run_date}: {e}")


class DecisionIn(BaseModel):
    ticker: str = Field(..., min_length=1, description="Yahoo ticker, e.g. AAPL or 0700.HK")
    decision: str = Field(..., description="reject | watch | researching | bought")
    note: str = Field("", description="optional free-text reason")


@app.get("/")
def root() -> dict:
    return {
        "service": "deep-value-screener-api",
        "runs": len(_run_dates()),
        "endpoints": ["/api/runs", "/api/runs/latest", "/api/runs/{date}",
                      "/api/decisions"],
    }


@app.get("/api/runs")
def list_runs() -> list[dict]:
    """List past run dates with how many names each surfaced (newest first)."""
    return [{"date": d, "count": len(_load_records(d))} for d in _run_dates()]


@app.get("/api/runs/latest")
def latest_run() -> dict:
    """The most recent run's full results."""
    dates = _run_dates()
    if not dates:
        raise HTTPException(status_code=404, detail="no runs saved yet")
    date = dates[0]
    records = _load_records(date)
    return {"date": date, "count": len(records), "records": records}


@app.get("/api/runs/{date}")
def run_by_date(date: str) -> dict:
    """A specific run's results by date (YYYY-MM-DD)."""
    if not _DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    if date not in _run_dates():
        raise HTTPException(status_code=404, detail=f"no run for {date}")
    records = _load_records(date)
    return {"date": date, "count": len(records), "records": records}


@app.get("/api/decisions")
def get_decisions() -> dict:
    """All decisions, keyed by ticker (latest per ticker), for label display."""
    cfg = load_config()
    path = cfg.feedback.get("decisions_path", "data/decisions.csv")
    return feedback.load_decisions(path)


@app.post("/api/decisions", status_code=201)
def post_decision(body: DecisionIn) -> dict:
    """Log a decision the same way the CLI does (appends to data/decisions.csv)."""
    cfg = load_config()
    path = cfg.feedback.get("decisions_path", "data/decisions.csv")
    try:
        feedback.record_decision(path, body.ticker, body.decision, body.note)
    except ValueError as e:  # invalid decision value
        raise HTTPException(status_code=400, detail=str(e))
    return {"ticker": body.ticker.strip(),
            "decision": body.decision.strip().lower(),
            "note": body.note}
