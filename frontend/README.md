# Deep Value — frontend dashboard

A dense, dark "trading-terminal" dashboard for the screener. Three columns:
**run history** (left) · **ranked table grouped by region** (center) · **stock
detail with decision buttons** (right). Built with Vite + React + Tailwind v4.

## Run it

The dashboard reads from the FastAPI backend, so start that first (from the
project root):

```bash
uvicorn src.api.main:app --reload      # serves http://localhost:8000
```

Then, in this `frontend/` folder:

```bash
npm install
npm run dev                            # http://localhost:5173
```

## Configuration

The API base URL comes from `VITE_API_URL` (default `http://localhost:8000`).
To point elsewhere, copy `.env.example` to `.env` and edit it:

```bash
cp .env.example .env
```

## What it does

- **Left** — past runs with name + "X new" counts; click to load a day.
- **Center** — ranked names grouped by region, with search and the client-side
  toggles *New only · Quality 60+ · Hide rejected*. Quality is a colour-coded
  pill; % off ATH is red; base upside shows its bear/bull range.
- **Right** — the selected name: plain-English summary, colour-coded quality
  metrics, a bear/base/bull upside strip, "why it's cheap", and four decision
  buttons (Reject / Watch / Research / Bought) that `POST /api/decisions` and
  update the label live.

Decision writes go to the same `data/decisions.csv` the CLI uses.
