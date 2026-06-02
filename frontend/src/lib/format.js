// Pure helpers that turn a raw StockRecord (from the API) into display values.
// Kept dumb and defensive — free data is often missing, so everything degrades
// to "—" rather than throwing.

export const REGION_ORDER = ["US", "Japan", "Europe", "China"];
export const REGION_LABEL = {
  US: "United States",
  Japan: "Japan",
  Europe: "Europe",
  China: "China",
};

export const DASH = "—";

export const firstNum = (arr) =>
  Array.isArray(arr) ? arr.find((x) => typeof x === "number" && !Number.isNaN(x)) ?? null : null;

const num = (x) => (typeof x === "number" && !Number.isNaN(x) ? x : null);

// fraction (0.42) -> "+42%"  /  signed optional
export const pctFrac = (x, { signed = false, digits = 0 } = {}) => {
  const v = num(x);
  if (v === null) return DASH;
  const s = (v * 100).toFixed(digits);
  return signed && v > 0 ? `+${s}%` : `${s}%`;
};

// already a 0..100 number (e.g. pct_off_ath) -> "74.2%"
export const pctRaw = (x, digits = 1) => {
  const v = num(x);
  return v === null ? DASH : `${v.toFixed(digits)}%`;
};

export const fixed = (x, digits = 2) => {
  const v = num(x);
  return v === null ? DASH : v.toFixed(digits);
};

const CUR_SYMBOL = { USD: "$", EUR: "€", GBP: "£", JPY: "¥", HKD: "HK$", CNY: "¥", CHF: "CHF " };

export function money(x, cur = "USD") {
  const v = num(x);
  if (v === null) return DASH;
  const sym = CUR_SYMBOL[cur] || `${cur} `;
  const abs = Math.abs(v);
  let s;
  if (abs >= 1e12) s = `${(v / 1e12).toFixed(2)}T`;
  else if (abs >= 1e9) s = `${(v / 1e9).toFixed(2)}B`;
  else if (abs >= 1e6) s = `${(v / 1e6).toFixed(1)}M`;
  else s = v.toFixed(0);
  return `${sym}${s}`;
}

// ---- semantic tiers (drive green / amber / red) ----------------------------
export const TIER = { good: "good", ok: "ok", bad: "bad", none: "none" };

export const qualityTier = (q) => {
  const v = num(q);
  if (v === null) return TIER.none;
  if (v >= 65) return TIER.good;
  if (v >= 40) return TIER.ok;
  return TIER.bad;
};

export const roicTier = (r) => {
  const v = num(r);
  if (v === null) return TIER.none;
  if (v >= 0.12) return TIER.good;
  if (v >= 0.07) return TIER.ok;
  return TIER.bad;
};

export const marginTier = (m) => {
  const v = num(m);
  if (v === null) return TIER.none;
  if (v >= 0.15) return TIER.good;
  if (v >= 0.06) return TIER.ok;
  return TIER.bad;
};

export const leverageTier = (nd) => {
  const v = num(nd);
  if (v === null) return TIER.none;
  if (v < 1.5) return TIER.good; // includes net cash (negative)
  if (v <= 3) return TIER.ok;
  return TIER.bad;
};

export const confTier = (c) => {
  const v = num(c);
  if (v === null) return TIER.none;
  if (v >= 0.8) return TIER.good;
  if (v >= 0.5) return TIER.ok;
  return TIER.bad;
};

// ---- flags -----------------------------------------------------------------
// Pick the single most important flag to surface in the table.
const FLAG_WEIGHT = [
  ["never profitable", 100],
  ["leverage", 90],
  ["debt", 88],
  ["dilut", 80],
  ["declin", 70],
  ["margin", 60],
  ["short history", 40],
  ["ath", 30],
  ["confidence", 20],
];
export function primaryFlag(flags) {
  if (!Array.isArray(flags) || flags.length === 0) return null;
  let best = flags[0];
  let bestW = -1;
  for (const f of flags) {
    const lc = String(f).toLowerCase();
    const w = FLAG_WEIGHT.find(([k]) => lc.includes(k))?.[1] ?? 10;
    if (w > bestW) {
      bestW = w;
      best = f;
    }
  }
  return best;
}

// ---- decisions -------------------------------------------------------------
// API decision value -> label + accent color key
export const DECISIONS = [
  { value: "reject", label: "Reject", tone: "red" },
  { value: "watch", label: "Watch", tone: "amber" },
  { value: "researching", label: "Research", tone: "blue" },
  { value: "bought", label: "Bought", tone: "green" },
];
export const decisionMeta = (value) => DECISIONS.find((d) => d.value === value) || null;

// ---- derived prose ---------------------------------------------------------
export function summarize(r) {
  const name = r.name || r.ticker;
  const off = pctRaw(r.pct_off_ath);
  const above = num(r.pct_above_52w_low);
  const q = num(r.quality_score);
  const up = pctFrac(r.upside_base, { signed: true });
  const s1 =
    `${name} is down ${off} from its all-time high` +
    (above !== null ? `, trading ${above.toFixed(0)}% above its 52-week low.` : ".");
  const s2 =
    (q !== null ? `Quality scores ${q.toFixed(0)}/100` : "Quality is unscored") +
    (up !== DASH ? ` with a base-case ${up} annualized upside.` : ".");
  return `${s1} ${s2}`;
}

export function whyCheap(r) {
  const off = pctRaw(r.pct_off_ath);
  const flag = primaryFlag(r.quality_flags);
  const lead = `The market has marked ${r.ticker} down ${off} from its peak`;
  const mid = flag ? ` — the headline concern is "${String(flag).toLowerCase()}".` : ".";
  const conf = num(r.data_confidence);
  const tail =
    conf !== null && conf < 0.55
      ? " Free-data confidence here is low, so treat the figures as directional and verify before acting."
      : r.multiple_from_fallback
        ? " Too few clean history years for a self-referenced multiple, so a sector band was used — flagged."
        : " The valuation is normalized from the company's own history, which can mislead through a genuine structural de-rating.";
  return lead + mid + tail;
}

export const cmpRank = (a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9);
