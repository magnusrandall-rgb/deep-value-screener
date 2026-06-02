import { TIER } from "../lib/format.js";

// tier -> text/bg/border classes for the quality pill & metric values
export const tierText = {
  good: "text-green",
  ok: "text-amber",
  bad: "text-red",
  none: "text-faint",
};

export const tierPill = {
  good: "text-green bg-green/10 border-green/25",
  ok: "text-amber bg-amber/10 border-amber/25",
  bad: "text-red bg-red/10 border-red/25",
  none: "text-faint bg-line/40 border-line",
};

export const toneClasses = {
  red: "text-red bg-red/10 border-red/25",
  amber: "text-amber bg-amber/10 border-amber/25",
  blue: "text-blue bg-blue/10 border-blue/25",
  green: "text-green bg-green/10 border-green/25",
  neutral: "text-muted bg-line/40 border-line",
};

export function Pill({ tier = TIER.none, children }) {
  return (
    <span
      className={`nums inline-flex min-w-[34px] items-center justify-center rounded-[5px] border px-1.5 py-0.5 text-[11px] font-semibold ${tierPill[tier]}`}
    >
      {children}
    </span>
  );
}

export function Tag({ tone = "neutral", children, title }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-[1px] text-[10px] font-medium uppercase tracking-wide ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

export function Stat({ label, value, tone = "ink" }) {
  const color =
    tone === "green" ? "text-green-bright" : tone === "amber" ? "text-amber" : "text-ink";
  return (
    <div className="flex flex-col">
      <span className={`nums text-[19px] font-semibold leading-none ${color}`}>{value}</span>
      <span className="mt-1 text-[10px] font-medium uppercase tracking-[0.12em] text-faint">
        {label}
      </span>
    </div>
  );
}
