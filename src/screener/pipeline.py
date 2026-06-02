"""The only orchestrator. Wires Stages 0->5 into the daily funnel, then applies
the Stage-6 feedback tagging. No stage logic lives here — just sequencing.

Funnel order (note: price screen runs first to fill the numbers the floor needs):
    universe -> price_screen + market_cap -> FLOOR (0) -> quality (3)
             -> valuation/rank (4) -> feedback tag (6) -> write-ups (5)
"""
from __future__ import annotations

import logging

from . import feedback, persist
from .config import Config
from .data import rate_limit
from .schema import StockRecord
from .stages import floor, price_screen, quality, valuation, writeup
from .universe import build_universe

log = logging.getLogger("screener.pipeline")


def run_pipeline(cfg: Config, allow_fetch: bool = True,
                 force_universe: bool = False,
                 stats: dict | None = None) -> list[StockRecord]:
    """Run the funnel. If `stats` is given, it's filled with run metadata
    (currently `universe_size` = the number of tickers screened)."""
    # Configure the network throttle from config so every live fetch is spaced
    # out and backs off politely on a Yahoo 429 (no-op when allow_fetch=False).
    fcfg = cfg.raw.get("fetch", {}) or {}
    rate_limit.configure_throttle(
        request_delay_seconds=fcfg.get("request_delay_seconds"),
        max_concurrency=fcfg.get("max_concurrency"),
        rate_limit_backoff_seconds=fcfg.get("rate_limit_backoff_seconds"),
        max_attempts=fcfg.get("max_attempts"),
    )

    # Stage 1 — universe
    records = build_universe(cfg, force=force_universe)
    if stats is not None:
        stats["universe_size"] = len(records)   # tickers screened (post shard/cap)
    log.info("universe: %d", len(records))

    # Stage 2 — price screen (also fills price-derived floor inputs)
    records = price_screen.screen_prices(records, cfg, allow_fetch=allow_fetch)
    records = price_screen.attach_market_cap(records, cfg, allow_fetch=allow_fetch)

    # Stage 0 — hard floor (now that market cap / liquidity / age are populated)
    records = floor.apply_floor(records, cfg)

    # Stage 3 — quality (score, single junk auto-drop)
    records = quality.assess_quality(records, cfg, allow_fetch=allow_fetch)

    # Stage 4 — valuation + ranking
    records = valuation.value_stocks(records, cfg)

    # Stage 6 — tag with prior decisions / suppress repeats (before write-ups so
    # the tag can appear in the prose and the suppressed names skip generation)
    records = feedback.apply_decisions(records, cfg)

    # mark new entrants vs. the prior saved run
    records = persist.diff_against_prior(records)

    # Stage 5 — write-ups on the FINAL list only
    records = writeup.generate_writeups(records, cfg)

    return records
