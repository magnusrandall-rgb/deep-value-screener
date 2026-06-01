# Deep-Value Stock Screener

A fully automated daily screener over **US, China, Japan, and Europe** equities.
It surfaces beaten-down quality businesses (long track records, temporary &
fixable problems) that may be mispriced, ranks them, writes a short analysis of
each, and emails you a skimmable shortlist with a full CSV attached.

> **This is a research / idea-generation tool, not investment advice.** It never
> auto-trades and never rank-and-forgets. It is deliberately biased toward
> *false positives* — better to review 30 names and reject 25 than to silently
> filter out one great idea. You make every final call.

## How it works (the funnel)

| Stage | What it does |
|------|--------------|
| 1 — Universe | Build & weekly-cache the ticker list for the four regions; drop ETFs/funds; de-dupe cross-listings. |
| 2 — Price screen | Keep names **down ≥ 50% from all-time high** AND **within 20% of the 52-week low**. Scores ATH confidence per ticker (free histories are often truncated). |
| 0 — Hard floor | Drop sub-threshold **market cap / liquidity / years-listed** (runs after Stage 2 fills those numbers). The biggest quality+speed lever. |
| 3 — Quality | Score (don't gate) ROIC/ROCE, margins, growth trend, dilution, leverage. Only hard auto-drop: never profitable in the last N years. |
| 4 — Valuation | Bear/base/bull fair value from a **normalized margin × normalized multiple**, annualized over 2–3 yrs. The return hurdle **ranks**, never cuts. |
| 5 — Write-up | Per-stock note (chart context, business, quality, upside, why it's cheap). Templated (free) or LLM (opt-in). |
| 6 — Feedback | Your `reject/watch/researching/bought` labels, previously-rejected tagging, outcome self-audit, and *suggested* (never auto-applied) calibration. |

Every output row carries a **data-confidence score** (0–1) reflecting per-region
coverage, ATH reliability, and fundamentals completeness.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .              # installs deps from requirements.txt
python -m pytest -q           # offline tests on a synthetic fixture (no network)
python -m screener.run --offline    # dry run, no email, cache/fixture only
python -m screener.run --no-email   # real fetch, persist, skip email
python -m screener.run              # full daily run + email
```

### Credentials (free)
The screener needs no paid data. For email and the optional LLM write-up, set
these as **environment variables / repo secrets** (never in code):

| Secret | Needed for |
|--------|-----------|
| `GMAIL_USER` | sender address |
| `GMAIL_APP_PASSWORD` | Gmail [app password](https://support.google.com/accounts/answer/185833) (not your login password) |
| `ANTHROPIC_API_KEY` | only if `write_up.engine: llm` |

If SMTP creds are missing the email is written to `data/results/` instead of
sent, so local runs never fail.

## Deploy the scheduled job (GitHub Actions)

1. Push to a **public** repo (unlimited free Actions minutes).
2. Add the secrets above under **Settings → Secrets and variables → Actions**.
3. `.github/workflows/daily.yml` runs at **06:00 UTC on weekdays** and on manual
   dispatch. It caches `data/` between runs (so only incremental price updates
   are fetched) and pushes a weekly empty commit (**keepalive**) — GitHub
   silently disables scheduled workflows after 60 days of repo inactivity.
4. **Failure & heartbeat alerts:** GitHub does *not* notify on failed scheduled
   runs, so the screener emails you on failure and on a "0 results" day. A silent
   break can't quietly kill the daily consistency that is the real edge.

## Tuning — everything lives in `config.yaml`

No threshold is hard-coded. Edit `config.yaml` and re-run. Key knobs:

- `price`: `pct_off_ath` (50), `pct_above_52w_low` (20), `ath_mode`.
- `floor`: `min_market_cap`, `min_avg_daily_dollar_volume`, `min_years_listed`.
- `quality`: `min_roic` (~7%), `min_years_history`, `drop_if_never_profitable_last_n_years`.
- `valuation`: `annual_return_hurdle` (30%, **ranking only**), `bear_base_bull_deltas`.
- `universe`: regions on/off, exchange suffixes, `include_a_shares` (+ confidence penalty).
- `write_up`: `engine` (`templated` | `llm`), `model`.
- `feedback`: `suppress_previously_rejected`, `calibration_cadence_days`, paths.
- `reporting_currency`, `email.recipients`, `schedule.cron`.

## The feedback loop (Stage 6)

After a run, label names with the CLI (or edit `data/decisions.csv` directly):

```bash
python -m screener.run decision TENCENT watch "watch HK regulatory overhang"
python -m screener.run decision SOMECO reject "structural decline, not cyclical"
python -m screener.run audit            # compare past estimates to realized prices
```

- **Memory of judgments:** a previously-rejected name resurfaces only with a
  `previously rejected YYYY-MM-DD: <reason>` tag (toggle `suppress_previously_rejected`).
- **Outcome tracking:** `data/outcomes.csv` snapshots price + estimated upside at
  surfacing time; the monthly **self-audit** checks whether the screen's upside
  math is any good.
- **Calibration digests** *propose* config tweaks for you to accept — nothing is
  ever applied automatically, the funnel is never auto-tightened, and there is no
  auto-trading.

## Skills (`.claude/skills/`)

Two committed Claude Code skills keep the methodology consistent (and govern the
LLM write-up if enabled):

- **`value-screening-methodology`** — ROIC/ROCE, normalized margin & multiple,
  bear/base/bull, IFRS-vs-GAAP, ATH & data-confidence rules.
- **`free-data-handling`** — per-region coverage quirks, yfinance gotchas, the
  rate-limit/backoff/incremental-cache pattern, and the source-fallback ladder.

## Known free-data limits per region

- **US** — best coverage (prices + fundamentals).
- **Japan** (`.T`) — good.
- **Europe** — decent; **IFRS distorts gross/net margins** (the screen favours
  EBIT margins for non-US names) and figures span multiple currencies
  (normalized to `reporting_currency`).
- **China** — mainland **A-shares (`.SS`/`.SZ`) are poorly covered** and OFF by
  default; Chinese exposure comes mainly from **Hong Kong (`.HK`)** listings and
  **US ADRs**. Enabling A-shares applies a data-confidence penalty.
- **ATH history** is the least reliable field everywhere — old/international
  tickers are often truncated or mis-split-adjusted, so ATH is scored and flagged
  as approximate, never presented as a hard number.

## Project layout

See `CLAUDE.md` for the full file map and conventions, and
`src/screener/stages/CLAUDE.md` for per-stage detail.
