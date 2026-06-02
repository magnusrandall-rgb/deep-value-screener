import { DECISIONS } from "../lib/format.js";

const SELECTED = {
  red: "border-red/50 bg-red/15 text-red",
  amber: "border-amber/50 bg-amber/15 text-amber",
  blue: "border-blue/50 bg-blue/15 text-blue",
  green: "border-green/50 bg-green/15 text-green-bright",
};

export default function DecisionButtons({ current, onDecide, busy }) {
  return (
    <div className="grid grid-cols-4 gap-1.5">
      {DECISIONS.map((d) => {
        const active = current === d.value;
        return (
          <button
            key={d.value}
            disabled={busy}
            onClick={() => onDecide(d.value)}
            className={`rounded-[6px] border px-1 py-1.5 text-[11.5px] font-semibold transition-colors disabled:opacity-50 ${
              active
                ? SELECTED[d.tone]
                : "border-line bg-panel-2 text-muted hover:border-line-bright hover:text-ink"
            }`}
          >
            {d.label}
          </button>
        );
      })}
    </div>
  );
}
