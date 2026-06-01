---
name: value-screening-methodology
description: The analytical house method for the deep-value screener — how ROIC/ROCE, normalized margin and multiple, bear/base/bull, IFRS-vs-US-GAAP adjustments, and ATH/data-confidence are computed. Load when editing scoring, valuation, quality, or write-up logic, or when an LLM write-up must follow house rules.
---

# Value-screening methodology (house method)

Apply this consistently across `scoring.py`, `stages/quality.py`,
`stages/valuation.py`, and `stages/writeup.py`. The philosophy: **good
businesses at great prices** — long operating histories going through
temporary, fixable problems. Bias toward **false positives** (review and reject)
over false negatives (silently filtered). This is idea generation, not advice.

## Returns on capital
- **ROIC** ≈ NOPAT / invested capital, with NOPAT ≈ EBIT × (1 − ~21% tax) and
  invested capital ≈ total assets − current liabilities (coarse with free data).
- **ROCE** ≈ EBIT / capital employed (same denominator proxy).
- A "good sign" is ROIC mostly ≳ `quality.min_roic` (~7%) **over time**; always
  report the trend (improving / declining), not a single year.

## Margins
- Track gross, EBIT, operating-cash-flow, and FCF margins as histories.
- **Lean on EBIT margins for non-US names** — IFRS distorts gross/net via lease,
  impairment, and provision treatment. See `free-data-handling`.

## Normalized valuation (Stage 4 — ranking input, NEVER a gate)
- **Normalized margin** = median of the company's own EBIT-margin history (or
  EBITDA-margin history when the multiple is computed on an EV/EBITDA basis — the
  margin basis MUST match the multiple basis).
- **Normalized multiple** = the **median of the company's OWN historical
  EV/EBIT** over available years, with the single highest and lowest year trimmed
  (when ≥ 5 points). For each fiscal year, `EV_t = price_t × shares_t +
  net_debt_t`, pairing the period-end date to the cached price. If EV/EBIT has
  fewer than `valuation.min_years_for_historical_multiple` (3) usable years
  (positive EBIT + known price), try **EV/EBITDA** the same way.
  - **The multiple is NEVER a pure function of the quality score.**
  - Only if NEITHER EV/EBIT nor EV/EBITDA has ≥ 3 usable years do we fall back to
    a `valuation.fallback_multiple_band` (sector/quality) band — and when we do we
    set `multiple_from_fallback=True`, flag it in the assumptions, and **lower
    `data_confidence`** by `valuation.fallback_multiple_confidence_penalty`.
  - `multiple_basis` records which was used: `EV/EBIT` | `EV/EBITDA` |
    `fallback-band`.
- Fair value = normalized margin × revenue × normalized multiple → EV, **less
  current net debt**, ÷ shares.
- Always emit **bear / base / bull** on BOTH the margin and the multiple (deltas
  from `valuation.bear_base_bull_deltas`). Never a single point estimate.
- A **negative/zero normalized margin** means no positive earnings history to
  normalize from → the method does not apply; flag it and leave upside
  unestimated rather than emitting a bogus 0 fair value / −100%.
- Express upside as an **annualized** return over `valuation.horizon_years`.
- The `annual_return_hurdle` (~30%) **orders** the list; it must never drop a
  name. A noisy fair value used as a gate silently kills good ideas.
- **Mandatory caveat on every record:** "normalized from history" misleads
  during a genuine structural de-rating — the market may have re-rated the name
  correctly and permanently.

## Chart context (Stage 5)
Classify the decline: **popped hype** (expectations outran fundamentals — often
needs to fall well past 50%), **cyclical/commodity**, or **genuinely mispriced
quality**. Note how long public and what the drawdown looks like.

## ATH & data confidence
- Prefer a **true ATH** from the longest dense history. Otherwise use max over
  available history, set `ath_is_approx=True`, and never present it as hard.
- **Score `ath_confidence` per ticker** from history length and density (old /
  international tickers have truncated or badly split-adjusted histories).
- Every row carries a 0..1 `data_confidence` blending region prior, ATH
  confidence, and fundamentals coverage.

## Hard rules
- The only Stage-3 auto-drop is "never profitable in last N years". Everything
  else is **scored and flagged**, not excluded — including high leverage (it is
  often *why* a name is cheap; surface it prominently).
- All thresholds come from `config.yaml` — never hard-code them.
