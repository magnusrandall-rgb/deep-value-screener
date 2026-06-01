# stages/ — pipeline stage notes (loads only when editing this directory)

Each stage takes `list[StockRecord]` in and returns `list[StockRecord]` out
(defined in `../schema.py`). Stages are wired only in `../pipeline.py`. Never
let one stage call another directly. Never hard-code a threshold — read it from
`cfg` (see `../config.py`).

## Stage contracts
- **floor.py (Stage 0)** — drops sub-threshold market cap / liquidity / age.
  Missing data fails the floor (does not pass). Runs AFTER price_screen has
  filled `market_cap`, `avg_dollar_volume`, `years_listed`.
- **price_screen.py (Stage 2)** — the two price gates (>=`pct_off_ath`,
  <=`pct_above_52w_low`) and fills price-derived fields. Sets `ath_is_approx`
  and `ath_confidence` per ticker; respects `ath_mode: true|approx-allowed`.
  `attach_market_cap()` is separate so the floor has real numbers.
- **quality.py (Stage 3)** — SCORE, don't gate. The ONLY auto-drop is "never
  profitable in last N years". Everything else is a flag. Fills history fields,
  growth trend, dilution note, leverage flag, accounting standard, quality &
  data-confidence scores.
- **valuation.py (Stage 4)** — RANKING ONLY. Bear/base/bull fair values from
  normalized margin x normalized multiple. `annual_return_hurdle` orders the
  list; it never cuts. Carries the structural-de-rating caveat on every record.
- **writeup.py (Stage 5)** — `templated` (free, default) or `llm` (opt-in,
  draft-labelled, metrics-only, cached). Runs only on the final ranked list.

## Conventions
- One bad ticker must never crash a stage — catch, log, skip.
- Histories are lists newest..oldest.
- EBIT margins are emphasised for non-US names (IFRS distorts the rest).
- See the `value-screening-methodology` and `free-data-handling` skills for the
  analytical house method and per-region data quirks.
