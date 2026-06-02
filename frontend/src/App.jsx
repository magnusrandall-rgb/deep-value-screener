import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { REGION_ORDER, cmpRank } from "./lib/format.js";
import Sidebar from "./components/Sidebar.jsx";
import FilterBar from "./components/FilterBar.jsx";
import ResultsTable from "./components/ResultsTable.jsx";
import DetailPanel from "./components/DetailPanel.jsx";
import { Stat } from "./components/ui.jsx";

const FILTERS0 = { search: "", newOnly: false, q60: false, hideRejected: false };

export default function App() {
  const [runs, setRuns] = useState([]);
  const [activeDate, setActiveDate] = useState(null);
  const [records, setRecords] = useState([]);
  const [screened, setScreened] = useState(null); // universe_size for the active run
  const [decisions, setDecisions] = useState({}); // ticker -> {decision,note,date}
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState(FILTERS0);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // initial load: runs + decisions, then the newest run
  useEffect(() => {
    (async () => {
      try {
        const [rs, ds] = await Promise.all([api.listRuns(), api.decisions()]);
        setRuns(rs);
        setDecisions(ds);
        if (rs.length) setActiveDate(rs[0].date);
        else setLoading(false);
      } catch (e) {
        setError(e.message);
        setLoading(false);
      }
    })();
  }, []);

  // load a run when the active date changes
  useEffect(() => {
    if (!activeDate) return;
    setLoading(true);
    (async () => {
      try {
        const data = await api.run(activeDate);
        const recs = [...data.records].sort(cmpRank);
        setRecords(recs);
        setScreened(data.universe_size ?? null);
        setSelected(recs[0]?.ticker ?? null);
        setError(null);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [activeDate]);

  const decisionFor = (ticker) =>
    decisions[ticker]?.decision ||
    records.find((r) => r.ticker === ticker)?.prior_decision ||
    "";

  async function handleDecide(ticker, value) {
    setBusy(ticker);
    // optimistic; revert on failure
    const prev = decisions[ticker];
    setDecisions((d) => ({ ...d, [ticker]: { decision: value, note: "", date: "today" } }));
    try {
      await api.postDecision({ ticker, decision: value });
    } catch (e) {
      setDecisions((d) => ({ ...d, [ticker]: prev }));
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  // ---- filter + group --------------------------------------------------------
  const { groups, shown } = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    const keep = records.filter((r) => {
      if (q && !(`${r.ticker} ${r.name || ""}`.toLowerCase().includes(q))) return false;
      if (filters.newOnly && !r.is_new_entrant) return false;
      if (filters.q60 && !(r.quality_score >= 60)) return false;
      if (filters.hideRejected && decisionFor(r.ticker) === "reject") return false;
      return true;
    });
    const byRegion = REGION_ORDER.map((region) => ({
      region,
      rows: keep.filter((r) => r.region === region).sort(cmpRank),
    })).filter((g) => g.rows.length > 0);
    // any unexpected regions not in the canonical order
    const extra = keep.filter((r) => !REGION_ORDER.includes(r.region));
    if (extra.length) byRegion.push({ region: "Other", rows: extra.sort(cmpRank) });
    return { groups: byRegion, shown: keep.length };
  }, [records, filters, decisions]);

  const surfaced = records.length;
  const newCount = records.filter((r) => r.is_new_entrant).length;
  const watching = records.filter((r) => decisionFor(r.ticker) === "watch").length;
  const selectedRec = records.find((r) => r.ticker === selected) || null;

  return (
    <div className="flex h-full w-full overflow-hidden bg-bg text-ink">
      <Sidebar runs={runs} activeDate={activeDate} onSelect={setActiveDate} />

      {/* MAIN PANEL */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* top bar */}
        <header className="flex items-center justify-between border-b border-line bg-panel px-5 py-3">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="nums text-[16px] font-bold tracking-tight text-ink">
                {activeDate || "—"}
              </span>
              <span className="text-[11px] uppercase tracking-[0.12em] text-faint">
                Deep-value shortlist
              </span>
            </div>
            <div className="nums mt-0.5 text-[11px] text-faint">
              {screened != null
                ? `${screened.toLocaleString()} tickers screened · ${surfaced} surfaced`
                : `${surfaced} surfaced from the daily screen`}
            </div>
          </div>
          <div className="flex items-center gap-6">
            <Stat label="Surfaced" value={surfaced} />
            <span className="h-7 w-px bg-line" />
            <Stat label="New" value={newCount} tone={newCount ? "green" : "ink"} />
            <span className="h-7 w-px bg-line" />
            <Stat label="Watching" value={watching} tone={watching ? "amber" : "ink"} />
          </div>
        </header>

        <FilterBar filters={filters} setFilters={setFilters} shown={shown} total={surfaced} />

        {error ? (
          <div className="grid-texture flex flex-1 items-center justify-center">
            <div className="max-w-sm rounded-[8px] border border-red/30 bg-red/5 px-5 py-4 text-center">
              <p className="text-[13px] font-semibold text-red">Can't reach the API</p>
              <p className="mt-1 text-[12px] text-muted">{error}</p>
              <p className="nums mt-2 text-[11px] text-faint">
                Start it: <span className="text-ink">uvicorn src.api.main:app --reload</span>
                <br />
                ({api.base})
              </p>
            </div>
          </div>
        ) : loading ? (
          <div className="grid-texture flex flex-1 items-center justify-center">
            <p className="nums animate-pulse text-[12px] text-faint">loading run…</p>
          </div>
        ) : (
          <ResultsTable
            groups={groups}
            selected={selected}
            onSelect={setSelected}
            decisionFor={decisionFor}
          />
        )}
      </main>

      {/* RIGHT DETAIL */}
      <DetailPanel
        rec={selectedRec}
        decision={selectedRec ? decisionFor(selectedRec.ticker) : ""}
        onDecide={(value) => selectedRec && handleDecide(selectedRec.ticker, value)}
        busy={busy === selected}
      />
    </div>
  );
}
