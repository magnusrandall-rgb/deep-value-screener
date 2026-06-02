# Deep-Value Stock Screener

A fully automated daily screener over **US, China, Japan, and Europe** equities.
It surfaces beaten-down quality businesses (long track records, temporary &
fixable problems) that may be mispriced, ranks them, writes a short analysis of
each, and logs + saves a skimmable shortlist to `data/results/` (CSV, JSON, and a
markdown report) for a dashboard frontend to consume.

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
python -m screener.run --offline    # cache/fixture only, no network
python -m screener.run              # full daily run: fetch, log, save to data/results/
```

Each run logs a ranked summary to the terminal and writes `data/results/<date>.{csv,json,md}`.
There is no email delivery — a dashboard frontend reads those files.

### API backend (serves results to the frontend)

A small FastAPI app exposes the saved runs and the decisions log to the frontend
(it reads the same `data/` files — no separate database). From the project root:

```bash
pip install -e .                          # installs fastapi + uvicorn too
uvicorn src.api.main:app --reload         # serves on http://127.0.0.1:8000
```

| Endpoint | Returns |
|----------|---------|
| `GET /api/runs` | past run dates with result counts |
| `GET /api/runs/latest` | the most recent run's full results (JSON) |
| `GET /api/runs/{date}` | a specific run's results (`date` = `YYYY-MM-DD`) |
| `GET /api/decisions` | all decisions, keyed by ticker (for labels) |
| `POST /api/decisions` | log a decision `{ticker, decision, note}` |

CORS is enabled for any `localhost`/`127.0.0.1` port so the React dev server can
call it. Interactive docs: <http://127.0.0.1:8000/docs>.

### Frontend dashboard

A dark, dense "trading-terminal" dashboard lives in [`frontend/`](frontend/)
(Vite + React + Tailwind). Start the API above, then:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (reads the API at VITE_API_URL, default :8000)
```

See [`frontend/README.md`](frontend/README.md) for details.

### Credentials (free)
The screener needs no paid data and no email credentials. The only optional
secret is for the LLM write-up engine:

| Secret | Needed for |
|--------|-----------|
| `ANTHROPIC_API_KEY` | only if `write_up.engine: llm` |

## Deploy the scheduled job (GitHub Actions)

1. Push to a **public** repo (unlimited free Actions minutes).
2. (Optional) add `ANTHROPIC_API_KEY` under **Settings → Secrets and variables →
   Actions** if you enable the LLM write-up engine. No email secrets are needed.
3. `.github/workflows/daily.yml` runs at **06:00 UTC on weekdays** and on manual
   dispatch. It caches `data/` between runs (so only incremental price updates
   are fetched), uploads `data/results/` as a build artifact, and pushes a weekly
   empty commit (**keepalive**) — GitHub silently disables scheduled workflows
   after 60 days of repo inactivity.
4. **Failure & heartbeat visibility:** a failed run shows as a red check in the
   Actions UI, and a 0-result day logs a heartbeat line. The dashboard frontend
   is responsible for surfacing results day to day.

## Tuning — everything lives in `config.yaml`

No threshold is hard-coded. Edit `config.yaml` and re-run. Key knobs:

- `price`: `pct_off_ath` (50), `pct_above_52w_low` (20), `ath_mode`.
- `floor`: `min_market_cap`, `min_avg_daily_dollar_volume`, `min_years_listed`.
- `quality`: `min_roic` (~7%), `min_years_history`, `drop_if_never_profitable_last_n_years`.
- `valuation`: `annual_return_hurdle` (30%, **ranking only**), `bear_base_bull_deltas`.
- `universe`: regions on/off, exchange suffixes, `include_a_shares` (+ confidence penalty).
- `write_up`: `engine` (`templated` | `llm`), `model`.
- `feedback`: `suppress_previously_rejected`, `calibration_cadence_days`, paths.
- `reporting_currency`, `schedule.cron`.

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
