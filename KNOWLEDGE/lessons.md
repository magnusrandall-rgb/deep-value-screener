# Lessons — data-quality & methodology learnings

Append durable findings here so the screener stops repeating known mistakes.
Promote stable lessons into `CLAUDE.md` or the two skills. Shared by both the
build side (Claude Code) and the screener's Stage-6 runtime loop.

Format: `- YYYY-MM-DD [scope] finding → action taken`.

## Data quality
- 2026-06-01 [ATH] yfinance histories for old/international tickers are often
  truncated or badly split-adjusted → ATH is scored (`ath_confidence`) and
  flagged `ath_is_approx`, never presented as a hard figure.
- 2026-06-01 [IFRS] Non-US gross/net margins distorted by lease/impairment/
  provision treatment → quality scoring leans on EBIT margins for non-US names.
- 2026-06-01 [China] Mainland A-shares (.SS/.SZ) poorly covered by free sources
  → OFF by default; Chinese exposure via .HK + US ADRs; A-shares carry a
  data-confidence penalty when enabled.

## Methodology
- 2026-06-01 [valuation] A fair-value estimate used as a hard gate silently drops
  good ideas → the 30%/yr hurdle ranks only; bear/base/bull always shown.
- 2026-06-01 [funnel] The Stage-0 floor (market cap / liquidity / years listed)
  is the biggest quality+speed lever; false-positive bias applies only above it.

## Build notes (Claude Code)
- 2026-06-01 [yfinance] yfinance >=1.x uses curl_cffi and REJECTS a requests/
  requests-cache `session=` ("request_cache sessions don't work with curl_cffi")
  → removed the session from `yf.Ticker` in prices.py & fundamentals.py; throttle
  defenses are now the incremental file cache + tenacity backoff only.
- 2026-06-01 Pipeline runs offline against `tests/conftest.py`'s synthetic
  fixture — use `--offline` / `allow_fetch=False` to iterate without the network.
