"""Stage-6 feedback: decisions roundtrip, tagging, and opt-in suppression."""
from __future__ import annotations

from screener import feedback
from screener.config import load_config
from screener.schema import StockRecord


def test_decision_roundtrip(tmp_path):
    path = tmp_path / "decisions.csv"
    feedback.record_decision(path, "DEEPUS", "reject", "too levered", when="2026-05-01")
    loaded = feedback.load_decisions(path)
    assert loaded["DEEPUS"]["decision"] == "reject"
    assert loaded["DEEPUS"]["note"] == "too levered"


def test_invalid_decision_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        feedback.record_decision(tmp_path / "d.csv", "X", "maybe")


def test_previously_rejected_tagged_not_hidden_by_default(tmp_path, monkeypatch):
    path = tmp_path / "decisions.csv"
    feedback.record_decision(path, "DEEPUS", "reject", "cyclical trap", when="2026-04-01")
    cfg = load_config()
    monkeypatch.setitem(cfg.feedback.as_dict(), "decisions_path", str(path))
    monkeypatch.setitem(cfg.feedback.as_dict(), "suppress_previously_rejected", False)

    recs = [StockRecord(ticker="DEEPUS", name="Deep Value Co")]
    out = feedback.apply_decisions(recs, cfg)
    assert len(out) == 1                       # still surfaced...
    assert out[0].prior_decision == "reject"   # ...but tagged with the prior call


def test_suppression_when_opted_in(tmp_path, monkeypatch):
    path = tmp_path / "decisions.csv"
    feedback.record_decision(path, "DEEPUS", "reject", "no", when="2026-04-01")
    cfg = load_config()
    monkeypatch.setitem(cfg.feedback.as_dict(), "decisions_path", str(path))
    monkeypatch.setitem(cfg.feedback.as_dict(), "suppress_previously_rejected", True)

    out = feedback.apply_decisions([StockRecord(ticker="DEEPUS")], cfg)
    assert out == []                            # hidden only when user opts in
