"""Cache behaviour: an empty/poisoned fundamentals entry must not be served as
valid, or it silently starves the floor (the bug that surfaced 0 names)."""
from __future__ import annotations

import json
from datetime import datetime

from screener import cache


def test_empty_fundamentals_cache_is_treated_as_stale(monkeypatch):
    ticker = "STALEFUND"
    # Write an empty-but-"fresh" cache, exactly as the old code did on a 429.
    path = cache._fund_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"_fetched_at": datetime.utcnow().isoformat()}))

    real = {"share_count": [1_000_000], "revenue": [5e8], "ebit": [6e7],
            "currency": "USD"}
    calls = {"n": 0}

    def fake_fetch(t, region):
        calls["n"] += 1
        return dict(real)

    monkeypatch.setattr(cache.fund_mod, "fetch_fundamentals", fake_fetch)

    out = cache.get_fundamentals(ticker, "US", allow_fetch=True)
    assert calls["n"] == 1                      # re-fetched, didn't serve the empty cache
    assert out.get("share_count") == [1_000_000]
    # and the usable result is now persisted
    assert cache._fundamentals_usable(json.loads(path.read_text()))


def test_usable_recent_fundamentals_cache_is_served(monkeypatch):
    ticker = "GOODFUND"
    path = cache._fund_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "_fetched_at": datetime.utcnow().isoformat(),
        "share_count": [2_000_000], "revenue": [9e8], "ebit": [1e8],
    }))

    def boom(t, region):  # must not be called
        raise AssertionError("should have served the fresh cache")

    monkeypatch.setattr(cache.fund_mod, "fetch_fundamentals", boom)
    out = cache.get_fundamentals(ticker, "US", allow_fetch=True)
    assert out.get("share_count") == [2_000_000]
