import { Tag } from "./ui.jsx";
import DecisionButtons from "./DecisionButtons.jsx";
import {
  firstNum,
  pctFrac,
  pctRaw,
  fixed,
  money,
  summarize,
  whyCheap,
  roicTier,
  marginTier,
  leverageTier,
  primaryFlag,
} from "../lib/format.js";
import { tierText } from "./ui.jsx";

function SectionTitle({ children }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
      {children}
    </h3>
  );
}

function Metric({ label, value, tier = "none", sub }) {
  return (
    <div className="flex items-baseline justify-between border-b border-line/60 py-1.5">
      <span className="text-[11.5px] text-muted">{label}</span>
      <span className="text-right">
        <span className={`nums text-[12.5px] font-semibold ${tierText[tier]}`}>{value}</span>
        {sub && <span className="ml-1 nums text-[10px] text-faint">{sub}</span>}
      </span>
    </div>
  );
}

function growthTier(t) {
  const s = String(t || "").toLowerCase();
  if (s.includes("grow")) return "good";
  if (s.includes("stab")) return "ok";
  if (s.includes("declin")) return "bad";
  return "none";
}

function Empty() {
  return (
    <div className="grid-texture flex flex-1 flex-col items-center justify-center gap-2 text-center">
      <span className="h-[10px] w-[10px] rounded-full bg-line-bright" />
      <p className="text-[12px] text-faint">Select a name to inspect.</p>
    </div>
  );
}

export default function DetailPanel({ rec, decision, onDecide, busy }) {
  if (!rec) return <aside className="flex w-[280px] shrink-0 border-l border-line bg-panel">{Empty()}</aside>;

  const roic = firstNum(rec.roic_history);
  const ebitM = firstNum(rec.ebit_margin_history);
  const grossM = firstNum(rec.gross_margin_history);
  const flags = Array.isArray(rec.quality_flags) ? rec.quality_flags : [];
  const trueAth = rec.ath_is_approx === false;

  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-l border-line bg-panel">
      <div className="flex-1 overflow-y-auto">
        {/* header */}
        <div className="border-b border-line px-4 pb-3 pt-4">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="nums text-[22px] font-bold tracking-tight text-ink">{rec.ticker}</h2>
            <span className="nums text-[12px] text-muted">{money(rec.price, rec.currency)}</span>
          </div>
          <p className="mt-0.5 text-[12px] font-medium text-ink">{rec.name || "—"}</p>
          <p className="nums mt-0.5 text-[10.5px] uppercase tracking-wide text-faint">
            {[rec.exchange, rec.sector, rec.currency].filter(Boolean).join(" · ")}
          </p>

          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {rec.is_new_entrant && <Tag tone="green">New today</Tag>}
            {trueAth ? <Tag tone="blue">True ATH</Tag> : null}
            <Tag tone="neutral">{rec.multiple_from_fallback ? "Fallback band" : "Hist. multiple"}</Tag>
            {flags.slice(0, 2).map((f) => (
              <Tag key={f} tone="amber" title={f}>
                {String(f).length > 18 ? String(f).slice(0, 17) + "…" : f}
              </Tag>
            ))}
          </div>
        </div>

        {/* a) summary card */}
        <div className="px-4 py-3">
          <div className="rounded-[8px] border border-line bg-panel-2 px-3 py-2.5">
            <p className="text-[12px] leading-relaxed text-muted">{summarize(rec)}</p>
          </div>
        </div>

        {/* b) quality metrics */}
        <div className="px-4 pb-3">
          <SectionTitle>Quality</SectionTitle>
          <Metric label="ROIC" value={pctFrac(roic, { digits: 1 })} tier={roicTier(roic)} />
          <Metric label="EBIT margin" value={pctFrac(ebitM, { digits: 1 })} tier={marginTier(ebitM)} />
          <Metric label="Gross margin" value={pctFrac(grossM, { digits: 1 })} tier={marginTier(grossM)} />
          <Metric
            label="Net debt / EBITDA"
            value={rec.net_debt_to_ebitda != null ? `${fixed(rec.net_debt_to_ebitda, 1)}×` : "—"}
            tier={leverageTier(rec.net_debt_to_ebitda)}
          />
          <Metric
            label="Growth"
            value={rec.growth_trend || "—"}
            tier={growthTier(rec.growth_trend)}
          />
          <Metric label="Dilution" value={rec.dilution_note || "—"} />
          <Metric label="Market cap" value={money(rec.market_cap, rec.currency)} />
          <Metric
            label="Data confidence"
            value={rec.data_confidence != null ? fixed(rec.data_confidence, 2) : "—"}
            tier={rec.data_confidence >= 0.8 ? "good" : rec.data_confidence >= 0.5 ? "ok" : "bad"}
          />
        </div>

        {/* c) upside box */}
        <div className="px-4 pb-3">
          <SectionTitle>Upside · annualized</SectionTitle>
          <div className="rounded-[8px] border border-line bg-panel-2 px-3 py-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] text-faint">Base case</span>
              <span
                className={`nums text-[26px] font-bold leading-none ${
                  rec.upside_base > 0 ? "text-green-bright" : rec.upside_base < 0 ? "text-red" : "text-muted"
                }`}
              >
                {pctFrac(rec.upside_base, { signed: true })}
              </span>
            </div>
            {/* bear / base / bull strip */}
            <div className="mt-3 grid grid-cols-3 overflow-hidden rounded-[5px] border border-line text-center">
              <div className="bg-red/10 py-1.5">
                <div className="text-[9px] uppercase tracking-wide text-faint">Bear</div>
                <div className="nums text-[12px] font-semibold text-red">
                  {pctFrac(rec.upside_bear, { signed: true })}
                </div>
              </div>
              <div className="border-x border-line bg-line/30 py-1.5">
                <div className="text-[9px] uppercase tracking-wide text-faint">Base</div>
                <div className="nums text-[12px] font-semibold text-ink">
                  {pctFrac(rec.upside_base, { signed: true })}
                </div>
              </div>
              <div className="bg-green/10 py-1.5">
                <div className="text-[9px] uppercase tracking-wide text-faint">Bull</div>
                <div className="nums text-[12px] font-semibold text-green-bright">
                  {pctFrac(rec.upside_bull, { signed: true })}
                </div>
              </div>
            </div>
            <p className="nums mt-2 text-[10px] text-faint">
              {rec.multiple_basis || "—"} · {rec.norm_multiple != null ? `${fixed(rec.norm_multiple, 1)}× mult` : "—"} ·{" "}
              {pctRaw(rec.pct_off_ath)} off ATH
            </p>
          </div>
        </div>

        {/* d) why it's cheap */}
        <div className="px-4 pb-4">
          <SectionTitle>Why it's cheap</SectionTitle>
          <p className="text-[12px] leading-relaxed text-muted">{whyCheap(rec)}</p>
        </div>
      </div>

      {/* footer: decision buttons */}
      <div className="border-t border-line bg-panel px-4 py-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
            Your call
          </span>
          {decision && (
            <span className="text-[10px] text-faint">logged · {decision}</span>
          )}
        </div>
        <DecisionButtons current={decision} onDecide={onDecide} busy={busy} />
      </div>
    </aside>
  );
}
