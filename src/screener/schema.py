"""Single source of truth for the record that flows through Stages 0->5.

Every stage takes a list[StockRecord] in and returns a list[StockRecord] out,
annotating or filtering. Nothing else defines this shape. If you add a field,
add it here and nowhere else.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from enum import Enum
from typing import Optional


class Region(str, Enum):
    US = "US"
    JAPAN = "Japan"
    EUROPE = "Europe"
    CHINA = "China"


@dataclass
class StockRecord:
    # --- identity (Stage 1) ---------------------------------------------------
    ticker: str                       # Yahoo ticker, e.g. "AAPL", "7203.T", "0700.HK"
    name: str = ""
    region: str = ""
    exchange: str = ""
    sector: str = ""
    currency: str = ""                # native reporting currency of the security

    # --- price screen (Stage 2) ----------------------------------------------
    price: Optional[float] = None             # latest close, native currency
    ath: Optional[float] = None               # all-time-high (or max-over-history)
    ath_is_approx: bool = True                # True unless a true ATH was confirmed
    ath_confidence: float = 0.0               # 0..1 — trust in the ATH figure
    pct_off_ath: Optional[float] = None       # 0..100, how far below ATH
    low_52w: Optional[float] = None
    pct_above_52w_low: Optional[float] = None # 0..inf, distance above the 52w low
    market_cap: Optional[float] = None        # normalized to reporting_currency
    avg_dollar_volume: Optional[float] = None # normalized to reporting_currency
    years_listed: Optional[float] = None

    # --- quality (Stage 3) ----------------------------------------------------
    roic_history: list[float] = field(default_factory=list)
    roce_history: list[float] = field(default_factory=list)
    revenue_history: list[float] = field(default_factory=list)
    ebit_history: list[float] = field(default_factory=list)        # absolute EBIT, newest..oldest
    ebitda_history: list[float] = field(default_factory=list)      # absolute EBITDA
    ebit_margin_history: list[float] = field(default_factory=list)
    gross_margin_history: list[float] = field(default_factory=list)
    fcf_margin_history: list[float] = field(default_factory=list)
    share_count_history: list[float] = field(default_factory=list)
    total_debt_history: list[float] = field(default_factory=list)
    cash_history: list[float] = field(default_factory=list)
    period_end_dates: list[str] = field(default_factory=list)      # fiscal-year ends, aligned to EBIT
    net_debt_to_ebitda: Optional[float] = None
    growth_trend: str = ""            # "growing" | "stabilizing" | "declining" | "unknown"
    dilution_note: str = ""
    accounting_standard: str = ""     # "US-GAAP" | "IFRS" | "unknown"
    quality_score: Optional[float] = None     # 0..100
    quality_flags: list[str] = field(default_factory=list)

    # --- valuation (Stage 4) — ranking input, never a gate -------------------
    norm_margin: Optional[float] = None
    norm_multiple: Optional[float] = None
    multiple_basis: str = ""            # "EV/EBIT" | "EV/EBITDA" | "fallback-band"
    multiple_from_fallback: bool = False  # True when <3 usable yrs forced the band
    fair_value_bear: Optional[float] = None
    fair_value_base: Optional[float] = None
    fair_value_bull: Optional[float] = None
    upside_bear: Optional[float] = None        # annualized over horizon, fraction
    upside_base: Optional[float] = None
    upside_bull: Optional[float] = None
    valuation_assumptions: list[str] = field(default_factory=list)

    # --- write-up (Stage 5) ---------------------------------------------------
    writeup: str = ""
    writeup_is_draft: bool = False             # True if LLM-generated

    # --- cross-cutting --------------------------------------------------------
    data_confidence: float = 0.0               # 0..1 — overall trust in this row
    rank: Optional[int] = None

    # --- feedback (Stage 6) ---------------------------------------------------
    prior_decision: str = ""                   # "", "reject", "watch", "researching", "bought"
    prior_decision_note: str = ""
    prior_decision_date: str = ""
    is_new_entrant: bool = False               # not present in the prior run

    # ---- helpers -------------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StockRecord":
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})


# Column order used for the saved CSV shortlist (consumed by the dashboard).
SUMMARY_COLUMNS = [
    "rank", "ticker", "name", "region", "exchange", "sector",
    "pct_off_ath", "ath_is_approx", "pct_above_52w_low",
    "quality_score", "upside_base", "upside_bear", "upside_bull",
    "norm_multiple", "multiple_basis", "multiple_from_fallback",
    "net_debt_to_ebitda", "data_confidence", "prior_decision", "is_new_entrant",
]
