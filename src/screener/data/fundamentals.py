"""Fundamentals fetch + IFRS/US-GAAP handling.

Returns a normalized dict of history lists so downstream scoring never touches
yfinance shapes. Missing data is returned as empty lists / None and FLAGGED,
never guessed. For non-US names we lean on EBIT margins (IFRS distorts the rest).
"""
from __future__ import annotations

import logging
from typing import Optional

from .rate_limit import DataUnavailable, with_backoff

log = logging.getLogger("screener.fundamentals")

# Region -> accounting standard assumption (used to choose adjustments & flags).
_GAAP_REGIONS = {"US"}


def accounting_standard_for(region: str) -> str:
    return "US-GAAP" if region in _GAAP_REGIONS else "IFRS"


def _safe_row(df, *names):
    """Pull the first matching row from a yfinance financial statement frame.
    Returns a list newest..oldest, or [] if absent. Drops NaN (for ratios)."""
    if df is None or getattr(df, "empty", True):
        return []
    for n in names:
        if n in df.index:
            vals = df.loc[n].tolist()
            return [float(v) for v in vals if v == v]  # drop NaN
    return []


def _col_dates(df):
    """Fiscal period-end dates (ISO 'YYYY-MM-DD') for a statement frame's columns."""
    if df is None or getattr(df, "empty", True):
        return []
    return [str(c)[:10] for c in df.columns]


def _row_map(df, names):
    """{date_str: value|None} for the first matching row — preserves column
    positions (NaN -> None) so values can be aligned across statements by date."""
    if df is None or getattr(df, "empty", True):
        return {}
    cols = _col_dates(df)
    for n in names:
        if n in df.index:
            vals = df.loc[n].tolist()
            return {d: (None if v != v else float(v)) for d, v in zip(cols, vals)}
    return {}


@with_backoff
def fetch_fundamentals(ticker: str, region: str) -> dict:
    """Normalized fundamentals dict. Keys always present; values may be empty.

    Shape:
      revenue, ebit, ebit_margin, gross_margin, operating_cf, fcf, fcf_margin,
      net_income, total_assets, current_liabilities, total_debt, cash,
      ebitda, share_count   -> all lists newest..oldest
      net_debt_to_ebitda    -> float | None
      accounting_standard   -> str
      sector, currency      -> str
    """
    out: dict = {
        "revenue": [], "ebit": [], "ebit_margin": [], "gross_margin": [],
        "operating_cf": [], "fcf": [], "fcf_margin": [], "net_income": [],
        "ebitda": [], "share_count": [], "roic": [], "roce": [],
        "total_debt": [], "cash": [], "period_end_dates": [],
        "net_debt_to_ebitda": None,
        "accounting_standard": accounting_standard_for(region),
        "sector": "", "currency": "",
    }
    try:
        import yfinance as yf  # lazy
    except Exception as e:  # pragma: no cover
        raise DataUnavailable(f"yfinance unavailable: {e}")

    # See prices.py: no session — yfinance >=1.x uses curl_cffi and rejects one.
    try:
        tk = yf.Ticker(ticker)
        info = getattr(tk, "info", {}) or {}
        fin = tk.financials                 # income statement (annual)
        bs = tk.balance_sheet
        cf = tk.cashflow
    except Exception as e:
        log.warning("fundamentals fetch failed for %s: %s", ticker, e)
        return out

    out["sector"] = info.get("sector", "") or ""
    out["currency"] = info.get("financialCurrency") or info.get("currency", "") or ""

    revenue = _safe_row(fin, "Total Revenue", "TotalRevenue")
    gross_profit = _safe_row(fin, "Gross Profit", "GrossProfit")
    ebit = _safe_row(fin, "EBIT", "Operating Income", "OperatingIncome")
    net_income = _safe_row(fin, "Net Income", "NetIncome")
    op_cf = _safe_row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    capex = _safe_row(cf, "Capital Expenditure", "Capital Expenditures")
    total_debt = _safe_row(bs, "Total Debt", "TotalDebt")
    cash = _safe_row(bs, "Cash And Cash Equivalents", "Cash", "CashAndCashEquivalents")
    total_assets = _safe_row(bs, "Total Assets", "TotalAssets")
    current_liab = _safe_row(bs, "Current Liabilities", "CurrentLiabilities")
    shares = _safe_row(fin, "Diluted Average Shares", "Basic Average Shares")
    if not shares and info.get("sharesOutstanding"):
        shares = [float(info["sharesOutstanding"])]

    out["revenue"] = revenue
    out["ebit"] = ebit
    out["net_income"] = net_income
    out["operating_cf"] = op_cf
    out["share_count"] = shares

    # Margins (guard against div-by-zero / mismatched lengths) -----------------
    def _ratio(num, den):
        return [n / d for n, d in zip(num, den) if d]

    out["ebit_margin"] = _ratio(ebit, revenue)
    out["gross_margin"] = _ratio(gross_profit, revenue)
    fcf = [o + c for o, c in zip(op_cf, capex)]  # capex is negative in yfinance
    out["fcf"] = fcf
    out["fcf_margin"] = _ratio(fcf, revenue)

    # ROIC ~ NOPAT / invested capital; ROCE ~ EBIT / capital employed.
    # Free data is coarse — approximate, and flagging happens in scoring.
    invested = [a - cl for a, cl in zip(total_assets, current_liab)]
    out["roce"] = _ratio(ebit, invested)
    out["roic"] = _ratio([e * 0.79 for e in ebit], invested)  # ~21% tax haircut

    # EBITDA & leverage (balance-sheet flag only) ------------------------------
    da = _safe_row(cf, "Depreciation And Amortization", "Depreciation")
    ebitda = [e + d for e, d in zip(ebit, da)] if da else ebit
    out["ebitda"] = ebitda
    if ebitda and ebitda[0]:
        net_debt = (total_debt[0] if total_debt else 0) - (cash[0] if cash else 0)
        out["net_debt_to_ebitda"] = round(net_debt / ebitda[0], 2)

    # Date-aligned series for the historical EV/EBIT(DA) multiple (Stage 4).
    # Everything is keyed to the income-statement period-end dates so each year's
    # EBIT can be paired with the right share count, net debt, and market price.
    fin_dates = _col_dates(fin)
    ebit_map = _row_map(fin, ["EBIT", "Operating Income", "OperatingIncome"])
    da_map = _row_map(cf, ["Depreciation And Amortization", "Depreciation"])
    debt_map = _row_map(bs, ["Total Debt", "TotalDebt"])
    cash_map = _row_map(bs, ["Cash And Cash Equivalents", "Cash", "CashAndCashEquivalents"])
    shares_map = _row_map(fin, ["Diluted Average Shares", "Basic Average Shares"])

    out["period_end_dates"] = fin_dates
    out["ebit_aligned"] = [ebit_map.get(d) for d in fin_dates]
    out["ebitda_aligned"] = [
        (ebit_map.get(d) + da_map.get(d))
        if (ebit_map.get(d) is not None and da_map.get(d) is not None)
        else ebit_map.get(d)
        for d in fin_dates
    ]
    out["total_debt"] = [debt_map.get(d) for d in fin_dates]
    out["cash"] = [cash_map.get(d) for d in fin_dates]
    # Prefer per-year diluted shares aligned to dates; fall back to the flat list.
    out["shares_aligned"] = [
        shares_map.get(d) if shares_map.get(d) is not None
        else (shares[0] if shares else None)
        for d in fin_dates
    ]

    return out
