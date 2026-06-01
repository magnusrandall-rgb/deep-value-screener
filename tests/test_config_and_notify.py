"""Config validation + result-report rendering (no email/SMTP)."""
from __future__ import annotations

import pytest

from screener import notify
from screener.config import load_config
from screener.schema import StockRecord


def test_config_loads_and_validates():
    cfg = load_config()
    assert cfg.price.pct_off_ath == 50
    assert cfg.write_up.engine in ("templated", "llm")
    assert "US" in cfg.enabled_regions


def test_invalid_engine_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "price: {pct_off_ath: 50}\nfloor: {}\nquality: {}\n"
        "valuation: {}\nuniverse: {}\nwrite_up: {engine: nonsense}\n"
    )
    with pytest.raises(ValueError):
        load_config(bad)


def test_report_body_highlights_new_entrants():
    r = StockRecord(ticker="DEEPUS", name="Deep Value Co", region="US",
                    exchange="NYSE", rank=1, pct_off_ath=65.0,
                    pct_above_52w_low=3.0, quality_score=72.0,
                    upside_base=0.18, data_confidence=0.9, is_new_entrant=True,
                    writeup="### 1. Deep Value Co (DEEPUS)")
    body = notify.build_body([r], "2026-06-01")
    assert "Deep-Value Screen" in body
    assert "DEEPUS" in body
    assert "🆕" in body            # new entrant highlighted
    assert "not investment advice" in body


def test_notify_has_no_email_machinery():
    # Email/SMTP was removed; guard against it creeping back in.
    import inspect
    src = inspect.getsource(notify)
    assert "smtplib" not in src
    assert "GMAIL" not in src
    assert not hasattr(notify, "send_results")
