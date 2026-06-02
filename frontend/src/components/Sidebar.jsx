// LEFT: the wordmark + run history. Active run gets a green left border.
export default function Sidebar({ runs, activeDate, onSelect }) {
  return (
    <aside className="flex w-[175px] shrink-0 flex-col border-r border-line bg-panel">
      <div className="flex items-center gap-2 border-b border-line px-4 py-[14px]">
        <span className="h-[14px] w-[3px] rounded-full bg-green-bright shadow-[0_0_8px] shadow-green/60" />
        <h1 className="font-sans text-[15px] font-extrabold tracking-tight text-green-bright">
          Deep Value
        </h1>
      </div>

      <div className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
        Run history
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {runs.length === 0 && (
          <p className="px-2 py-4 text-[12px] text-faint">No runs yet.</p>
        )}
        {runs.map((r) => {
          const active = r.date === activeDate;
          return (
            <button
              key={r.date}
              onClick={() => onSelect(r.date)}
              className={`group relative mb-1 block w-full rounded-[6px] px-3 py-2 text-left transition-colors ${
                active ? "bg-raised" : "hover:bg-panel-2"
              }`}
            >
              <span
                className={`absolute left-0 top-1.5 bottom-1.5 w-[2.5px] rounded-full transition-colors ${
                  active ? "bg-green-bright" : "bg-transparent group-hover:bg-line-bright"
                }`}
              />
              <div
                className={`nums text-[12.5px] font-semibold ${active ? "text-ink" : "text-muted"}`}
              >
                {r.date}
              </div>
              <div className="mt-0.5 flex items-baseline gap-1.5">
                <span className="nums text-[11px] text-faint">{r.count} names</span>
                {r.new > 0 && (
                  <span className="nums text-[11px] font-medium text-green">· {r.new} new</span>
                )}
              </div>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-line px-4 py-2.5 text-[10px] leading-relaxed text-faint">
        Research tool — not advice. False-positive biased by design.
      </div>
    </aside>
  );
}
