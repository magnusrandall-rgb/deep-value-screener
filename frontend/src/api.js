// Thin client for the FastAPI backend. Base URL from VITE_API_URL (default :8000).
const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json();
}

export const api = {
  base: BASE,
  listRuns: () => get("/api/runs"),
  latestRun: () => get("/api/runs/latest"),
  run: (date) => get(`/api/runs/${date}`),
  decisions: () => get("/api/decisions"),
  postDecision: async ({ ticker, decision, note = "" }) => {
    const res = await fetch(`${BASE}/api/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, decision, note }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${res.status} posting decision`);
    }
    return res.json();
  },
};
