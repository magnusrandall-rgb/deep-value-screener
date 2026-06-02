"""Run persistence: universe_size round-trips, and old bare-array files still load."""
from __future__ import annotations

import json

from screener import persist
from screener.schema import StockRecord


def test_save_run_records_universe_size():
    recs = [StockRecord(ticker="AAA", name="A Co", region="US"),
            StockRecord(ticker="BBB", name="B Co", region="Japan")]
    persist.save_run(recs, "2030-01-02", universe_size=1234)

    # on-disk JSON carries it
    raw = json.loads(persist._results_path("2030-01-02").read_text())
    assert raw["universe_size"] == 1234
    assert raw["count"] == 2

    # read_run surfaces it; load_run still returns records
    records, usize = persist.read_run("2030-01-02")
    assert usize == 1234 and len(records) == 2
    assert {r.ticker for r in persist.load_run("2030-01-02")} == {"AAA", "BBB"}


def test_legacy_bare_array_run_still_loads():
    # a pre-universe_size file is a bare array of records
    path = persist._results_path("2029-12-31")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([StockRecord(ticker="OLD", region="US").to_dict()]))

    records, usize = persist.read_run("2029-12-31")
    assert usize is None
    assert [r.ticker for r in persist.load_run("2029-12-31")] == ["OLD"]
