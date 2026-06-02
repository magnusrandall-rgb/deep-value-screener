// Search input + client-side toggle pills. All state lives in App.
function Toggle({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-[6px] border px-2.5 py-1 text-[11.5px] font-medium transition-colors ${
        active
          ? "border-green/40 bg-green/12 text-green-bright"
          : "border-line bg-panel-2 text-muted hover:border-line-bright hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export default function FilterBar({ filters, setFilters, shown, total }) {
  const set = (patch) => setFilters((f) => ({ ...f, ...patch }));
  return (
    <div className="flex items-center gap-2 border-b border-line bg-panel px-4 py-2.5">
      <div className="relative">
        <svg
          className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          value={filters.search}
          onChange={(e) => set({ search: e.target.value })}
          placeholder="Filter ticker or name…"
          className="nums w-[200px] rounded-[6px] border border-line bg-panel-2 py-1 pl-8 pr-2 text-[12px] text-ink placeholder:font-sans placeholder:text-faint focus:border-green/40 focus:outline-none"
        />
      </div>

      <Toggle active={filters.newOnly} onClick={() => set({ newOnly: !filters.newOnly })}>
        New only
      </Toggle>
      <Toggle active={filters.q60} onClick={() => set({ q60: !filters.q60 })}>
        Quality 60+
      </Toggle>
      <Toggle active={filters.hideRejected} onClick={() => set({ hideRejected: !filters.hideRejected })}>
        Hide rejected
      </Toggle>

      <div className="ml-auto nums text-[11px] text-faint">
        {shown === total ? `${total}` : `${shown} / ${total}`} shown
      </div>
    </div>
  );
}
