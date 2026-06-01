---
name: free-data-handling
description: Per-region free-data coverage quirks (esp. China A-shares and non-US fundamentals), yfinance gotchas, the rate-limit/backoff/retry pattern, incremental-cache rules, and the fallback ladder when a source is throttled or missing. Load when editing data fetchers, cache, currency, or universe logic, or when debugging missing/unreliable data.
---

# Free-data handling

Free data is imperfect — worst for ATH history and non-US/China fundamentals.
**Flag, don't guess.** Never present an approximation as a hard figure. One bad
ticker must never crash a run.

## Region coverage gradient
- **US** (NYSE/NASDAQ/AMEX) — best free coverage, prices and fundamentals.
- **Japan** (`.T`, Tokyo Prime/Standard/Growth) — good.
- **Europe** (`.L .PA .AS .BR .LS .DE .SW .MI .MC .ST .OL .CO .HE`) — decent;
  IFRS distorts gross/net margins (favour EBIT). Multiple currencies → must
  FX-normalize to `reporting_currency`.
- **China** — mainland A-shares (`.SS`, `.SZ`) are **poorly covered** and hard
  to access; OFF by default (`universe.include_a_shares`). Get Chinese exposure
  via **HK-listed** (`.HK`) names and **US ADRs**. If A-shares are enabled, apply
  `a_share_confidence_penalty` so their `data_confidence` reflects the risk.

## yfinance gotchas
- Histories can be **truncated or badly split-adjusted**, especially old and
  international tickers → score `ath_confidence`, never trust a lone ATH.
- Financial-statement row labels vary ("EBIT" vs "Operating Income", "Total
  Revenue" vs "TotalRevenue"); `data/fundamentals.py::_safe_row` tries aliases.
- `info` is flaky/slow; treat any field as possibly missing.
- `financialCurrency` may differ from the trading currency → use it for FX.

## Rate-limit / backoff / cache pattern
- **Do NOT pass a `session=` to `yf.Ticker`.** yfinance >=1.x uses `curl_cffi`
  internally and *rejects* `requests` / `requests-cache` sessions ("request_cache
  sessions don't work with curl_cffi"). Passing one makes every fetch fail. Let
  yfinance manage its own HTTP.
- Throttle defenses are therefore: (1) our **incremental file cache** in
  `cache.py` (never re-download a full history) and (2) the **`tenacity`
  exponential backoff** decorator in `data/rate_limit.py`. The `get_session`
  helper there is reserved for *non-yfinance* free APIs only.
- Scheduled-runner IPs **will** get throttled by Yahoo. On throttle, raise/return
  `DataUnavailable` and **serve cache** — degrade gracefully, never crash.
- **Incremental updates only:** `cache.get_price_history` reads the cached frame
  and fetches just the missing tail (day after last cached row). Never
  re-download a full history. Fundamentals refresh at most weekly.
- Universe is cached and refreshed weekly (`universe.refresh_days`).

## Fallback ladder when a source is missing/throttled
1. Serve the cached value if present (prices/fundamentals/FX/universe).
2. If no cache and throttled → skip the ticker (log), keep the run alive.
3. If `financedatabase` is unavailable → use the built-in seed universe.
4. If FX rate unavailable → return None and lower `data_confidence` (never 1.0).
5. If SMTP creds missing → write the email to `data/results/` instead of sending.

## IFRS vs US-GAAP
- `data/fundamentals.py::accounting_standard_for` tags non-US as IFRS.
- Be alert to lease capitalization, impairments, and provisions producing false
  red flags. Favour EBIT-based metrics for cross-region comparability.
- Record durable data-quality findings in `KNOWLEDGE/lessons.md`.
