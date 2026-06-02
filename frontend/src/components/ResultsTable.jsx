import { Pill, Tag } from "./ui.jsx";
import {
  pctRaw,
  pctFrac,
  qualityTier,
  primaryFlag,
  decisionMeta,
  REGION_LABEL,
} from "../lib/format.js";

const COLS =
  "grid-cols-[minmax(150px,1.7fr)_70px_60px_118px_minmax(80px,1.1fr)_86px]";

function HeaderRow() {
  return (
    <div
      className={`grid ${COLS} items-center gap-2 border-b border-line bg-panel px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-faint`}
    >
      <span>Ticker</span>
      <span className="text-right">Off ATH</span>
      <span className="text-center">Qual</span>
      <span className="text-right">Base upside</span>
      <span>Flag</span>
      <span className="text-right">Decision</span>
    </div>
  );
}

function Row({ r, selected, onSelect, decision }) {
  const dm = decisionMeta(decision);
  const flag = primaryFlag(r.quality_flags);
  return (
    <button
      onClick={() => onSelect(r.ticker)}
      className={`relative grid ${COLS} w-full items-center gap-2 border-b border-line/60 px-4 py-2 text-left transition-colors ${
        selected ? "bg-raised" : r.is_new_entrant ? "bg-green/[0.04] hover:bg-green/[0.07]" : "hover:bg-panel-2"
      }`}
    >
      <span
        className={`absolute left-0 top-0 bottom-0 w-[2.5px] ${selected ? "bg-green-bright" : "bg-transparent"}`}
      />
      {/* ticker + company */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="nums text-[13px] font-semibold text-ink">{r.ticker}</span>
          {r.is_new_entrant && (
            <span className="rounded-[3px] bg-green/15 px-1 py-px text-[8.5px] font-bold uppercase tracking-wide text-green">
              New
            </span>
          )}
        </div>
        <div className="truncate text-[11px] text-faint">{r.name || "—"}</div>
      </div>

      {/* % off ATH (red) */}
      <span className="nums text-right text-[12.5px] font-medium text-red">
        {pctRaw(r.pct_off_ath)}
      </span>

      {/* quality pill */}
      <div className="flex justify-center">
        <Pill tier={qualityTier(r.quality_score)}>
          {r.quality_score != null ? Math.round(r.quality_score) : "—"}
        </Pill>
      </div>

      {/* base upside + bear/bull range */}
      <div className="text-right">
        <div
          className={`nums text-[12.5px] font-semibold ${
            r.upside_base > 0 ? "text-green" : r.upside_base < 0 ? "text-red" : "text-muted"
          }`}
        >
          {pctFrac(r.upside_base, { signed: true })}
        </div>
        <div className="nums text-[10px] text-faint">
          {pctFrac(r.upside_bear, { signed: true })} · {pctFrac(r.upside_bull, { signed: true })}
        </div>
      </div>

      {/* most important flag */}
      <div className="min-w-0">
        {flag ? (
          <span className="block truncate text-[11px] text-amber/90" title={flag}>
            {flag}
          </span>
        ) : (
          <span className="text-[11px] text-faint">clean</span>
        )}
      </div>

      {/* decision label */}
      <div className="flex justify-end">
        {dm ? <Tag tone={dm.tone}>{dm.label}</Tag> : <span className="text-[11px] text-faint">—</span>}
      </div>
    </button>
  );
}

export default function ResultsTable({ groups, selected, onSelect, decisionFor }) {
  if (groups.length === 0) {
    return (
      <div className="grid-texture flex flex-1 items-center justify-center">
        <p className="text-[13px] text-faint">No names match the current filters.</p>
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="sticky top-0 z-10">
        <HeaderRow />
      </div>
      {groups.map((g) => (
        <section key={g.region}>
          <div className="flex items-center gap-2 border-b border-line bg-panel-2/70 px-4 py-1.5 backdrop-blur">
            <span className="text-[11px] font-semibold tracking-wide text-ink">
              {REGION_LABEL[g.region] || g.region}
            </span>
            <span className="nums text-[11px] text-faint">· {g.rows.length} names</span>
          </div>
          {g.rows.map((r) => (
            <Row
              key={r.ticker}
              r={r}
              selected={selected === r.ticker}
              onSelect={onSelect}
              decision={decisionFor(r.ticker)}
            />
          ))}
        </section>
      ))}
    </div>
  );
}
