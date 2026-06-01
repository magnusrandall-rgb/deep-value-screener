"""Stage 1 — assemble & cache the ticker universe across the four regions.

Source of tickers is `financedatabase`; we filter to equities in the enabled
regions/exchanges, drop ETFs & funds, de-duplicate cross-listings (one entry per
company, preferring the most-liquid / primary line), and cache the result.
Refresh weekly, not every run.

If financedatabase is unavailable we fall back to a small built-in seed list so
the pipeline still runs (and tests don't need the package).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .cache import CACHE_ROOT
from .config import Config
from .schema import StockRecord

log = logging.getLogger("screener.universe")

_UNIVERSE_PATH = CACHE_ROOT / "universe.json"

# Suffix -> region map is derived from config; this seed is the offline fallback.
_SEED = [
    ("AAPL", "Apple", "US", "NASDAQ", "Technology", "USD"),
    ("INTC", "Intel", "US", "NASDAQ", "Technology", "USD"),
    ("WBA", "Walgreens Boots Alliance", "US", "NASDAQ", "Healthcare", "USD"),
    ("7203.T", "Toyota", "Japan", "Tokyo", "Consumer Cyclical", "JPY"),
    ("BARC.L", "Barclays", "Europe", "LSE", "Financial Services", "GBP"),
    ("0700.HK", "Tencent", "China", "HKEX", "Communication Services", "HKD"),
    ("BABA", "Alibaba (ADR)", "China", "NYSE", "Consumer Cyclical", "USD"),
]


def _suffix_region_map(cfg: Config) -> dict[str, str]:
    m: dict[str, str] = {}
    suffixes = cfg.universe.get("exchange_suffixes", {})
    for region, sfxs in suffixes.items():
        if region == "China_a_shares":
            region = "China"
        for s in sfxs:
            m[s] = region
    return m


def _is_fresh(path: Path, days: int) -> bool:
    if not path.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(path.stat().st_mtime)
    return age < timedelta(days=days)


def _dedupe_cross_listings(records: list[StockRecord]) -> list[StockRecord]:
    """Collapse the same company on multiple exchanges to one entry.

    Heuristic with free data: group by normalized name; keep the line whose
    suffix order best matches "primary/most-liquid" (US bare ticker > HK > home).
    """
    priority = {"": 0, ".HK": 1}  # lower = preferred; US bare tickers win

    def rank(rec: StockRecord) -> int:
        sfx = "" if "." not in rec.ticker else "." + rec.ticker.split(".")[-1]
        return priority.get(sfx, 5)

    best: dict[str, StockRecord] = {}
    for r in records:
        key = r.name.strip().lower() or r.ticker
        if key not in best or rank(r) < rank(best[key]):
            best[key] = r
    return list(best.values())


def _build_from_financedatabase(cfg: Config) -> list[StockRecord]:
    import financedatabase as fd  # type: ignore

    equities = fd.Equities()
    df = equities.select()  # full table; we filter below
    smap = _suffix_region_map(cfg)
    include_a = cfg.universe.get("include_a_shares", False)
    a_suffixes = set(cfg.universe.get("exchange_suffixes", {}).get("China_a_shares", []))
    excluded = set(cfg.universe.get("excluded_exchanges", []))

    out: list[StockRecord] = []
    for symbol, row in df.iterrows():
        if not isinstance(symbol, str):
            continue
        sfx = "" if "." not in symbol else "." + symbol.split(".")[-1]
        if sfx in excluded:
            continue
        if sfx in a_suffixes and not include_a:
            continue
        # US bare tickers (no suffix) only count as US.
        region = smap.get(sfx, "US" if sfx == "" else None)
        if region is None or not cfg.universe.regions.get(region, False):
            continue
        out.append(StockRecord(
            ticker=symbol,
            name=str(row.get("name", "") or ""),
            region=region,
            exchange=str(row.get("exchange", "") or ""),
            sector=str(row.get("sector", "") or ""),
            currency=str(row.get("currency", "") or ""),
        ))
    return out


def build_universe(cfg: Config, force: bool = False) -> list[StockRecord]:
    """Return the (cached) universe of candidate equities."""
    refresh_days = cfg.universe.get("refresh_days", 7)
    if not force and _is_fresh(_UNIVERSE_PATH, refresh_days):
        try:
            data = json.loads(_UNIVERSE_PATH.read_text())
            return [StockRecord.from_dict(d) for d in data]
        except Exception as e:
            log.warning("universe cache unreadable, rebuilding: %s", e)

    try:
        records = _build_from_financedatabase(cfg)
        if not records:
            raise RuntimeError("financedatabase returned 0 rows after filtering")
    except Exception as e:
        log.warning("financedatabase unavailable (%s); using seed list", e)
        records = [
            StockRecord(ticker=t, name=n, region=r, exchange=ex, sector=sec, currency=c)
            for (t, n, r, ex, sec, c) in _SEED
            if cfg.universe.regions.get(r, False)
        ]

    records = _dedupe_cross_listings(records)

    cap = cfg.universe.get("max_tickers")
    if cap:
        records = records[: int(cap)]

    _UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _UNIVERSE_PATH.write_text(json.dumps([r.to_dict() for r in records]))
    except Exception as e:  # pragma: no cover
        log.warning("could not write universe cache: %s", e)

    log.info("universe: %d tickers across regions", len(records))
    return records
