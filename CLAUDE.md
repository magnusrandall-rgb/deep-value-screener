# Deep-Value Stock Screener — project context for Claude Code

## Purpose
A fully automated daily screener over **US, China, Japan, Europe** equities that
surfaces beaten-down quality companies (good businesses at great prices going
through temporary, fixable problems), ranks them, writes a per-name analysis, and
logs + saves the shortlist to `data/results/` (CSV/JSON/markdown) for a dashboard
frontend. No email. Free data only. Research/idea-generation — **never
auto-trades, never rank-and-forget.** Deliberate **false-positive bias**: better
to review 30 and reject 25 than silently filter a great idea.

## File map
- `config.yaml` — ALL tunable knobs. **Never hard-code a threshold in code.**
- `src/screener/`
  - `schema.py` — `StockRecord`, the one record passed through every stage.
  - `config.py` — the only config loader + validation.
  - `universe.py` — Stage 1: build/cache ticker universe (4 regions), de-dupe.
  - `cache.py` — price/fundamentals cache + **incremental** updates.
  - `currency.py` — FX normalization to `reporting_currency`.
  - `scoring.py` — quality score + data-confidence score (additive, transparent).
  - `data/{prices,fundamentals,rate_limit}.py` — live fetch + backoff/cache.
  - `stages/{floor,price_screen,quality,valuation,writeup}.py` — Stages 0,2,3,4,5.
  - `pipeline.py` — the ONLY orchestrator (wires the stages).
  - `persist.py` — daily results storage + run-to-run diffing (new entrants).
  - `feedback.py` — Stage 6: decisions log, suppression, outcomes, calibration.
  - `notify.py` — terminal log + on-disk markdown report + new-entrant highlight (no email).
  - `run.py` — the ONLY entrypoint (also `decision` / `audit` subcommands).

## Inter-stage data contract
Every stage takes `list[StockRecord]` in and returns `list[StockRecord]` out,
annotating or filtering. The shape is defined once in `schema.py`. Stages never
call each other — only `pipeline.py` wires them. See `src/screener/stages/CLAUDE.md`
for per-stage detail (loads only when working in that directory).

## Pipeline order
universe → price_screen (+market cap) → **floor (Stage 0)** → quality (3) →
valuation/rank (4) → feedback tag (6) → write-ups (5). Price screen runs before
the floor because it fills the market-cap / liquidity / age figures the floor needs.

## Run / test
- Tests (offline, fast, on a synthetic fixture — no network):
  `python -m pytest -q`  (or `.venv/bin/python -m pytest -q`)
- Full run: `python -m screener.run`  (needs `pip install -e .` or `PYTHONPATH=src`)
- Offline run: `python -m screener.run --offline`
- Log a decision: `python -m screener.run decision DEEPUS reject "too levered"`
- Self-audit: `python -m screener.run audit`

## Per-region free-data quirks (summary — full detail in the skills)
- US best; Japan good; Europe decent (IFRS → favour EBIT margins, FX-normalize).
- China: A-shares (`.SS/.SZ`) poorly covered, OFF by default; use `.HK` + US ADRs.
- yfinance histories are often truncated/mis-split → score `ath_confidence`.
- Throttling expected on CI IPs → serve cache, never crash.

## Hard conventions
- All thresholds live in `config.yaml` — never hard-code them.
- One bad ticker must never crash a run (catch, log, skip).
- Histories are lists newest..oldest.
- Score & flag; the ONLY hard auto-drop is "never profitable in last N years".
- The return hurdle ranks, never gates. Always bear/base/bull, never a point.
- Flag missing/unreliable data; never present an approximation as a hard figure.
- Stage 6 may *propose* config tweaks; it never auto-applies, tightens the
  funnel, or trades.

## Skills (in `.claude/skills/`)
- `value-screening-methodology` — the analytical house method.
- `free-data-handling` — per-region data quirks + the rate-limit/cache pattern.

## Knowledge
Durable data-quality / methodology learnings go in `KNOWLEDGE/lessons.md`;
promote stable ones into this file or the skills.
