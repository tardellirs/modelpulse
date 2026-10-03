export type Model = {
  id: string;
  author: string | null;
  pipeline_tag: string | null;
  library_name: string | null;
  created_at: string | null;
  last_modified: string | null;
  params: number | null;
  license: string | null;
  base_relation: string | null;
  base_ids: string[] | null;
  is_gguf: boolean | null;
  dl30: number | null;
  dl_all: number | null;
  dl_7d: number | null;
  dl_prev7d: number | null;
  growth_7d: number | null;
  likes: number | null;
  likes_7d: number | null;
  trending: number | null;
  rank_dl30: number | null;
  rank_task: number | null;
  rank_7d: number | null;
  first_seen: string | null;
  fam_members: number;
  fam_dl30: number | null;
  fam_all: number | null;
  fam_7d: number | null;
  n_quantized: number | null;
  n_finetune: number | null;
  n_adapter: number | null;
  n_merge: number | null;
};

export type Series = { day: string[]; dl30: (number | null)[]; dl_all: (number | null)[]; likes: (number | null)[] };
export type FamilySeries = { day: string[]; dl30: (number | null)[]; dl_all: (number | null)[]; members: number[] };
export type Child = { id: string; relation: string; author: string; dl30: number; dl_all: number; dl_7d: number; likes: number };
export type ModelResponse = { model: Model; series: Series; children: Child[]; family?: FamilySeries };
export type Row = {
  id?: string; author?: string; pipeline_tag?: string | null; params?: number | null;
  dl30?: number; dl_all?: number; dl_7d?: number; growth_7d?: number | null; likes?: number; likes_7d?: number;
  created_at?: string; fam_members?: number; fam_dl30?: number; models?: number; spark?: number[];
};
export type Leaderboards = Record<string, Row[]> & { updated: string };
export type Hub = { tags: string[]; day: string[]; tag: string[]; dl: number[] };
export type AuthorResponse = {
  author: string;
  series: { day: string[]; dl30: number[]; dl_all: number[]; likes: number[]; models: number[] };
  models: (Row & { id: string })[];
};

export const API_BASE: string = (import.meta as any).env?.VITE_API_BASE ?? "";

const cache = new Map<string, Promise<any>>();

export function get<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const p = fetch(API_BASE + path).then(async (r) => {
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        cache.delete(path);
        throw new Error(body.detail || `Request failed (${r.status})`);
      }
      return r.json();
    });
    cache.set(path, p);
  }
  return cache.get(path)!;
}

export const api = {
  model: (id: string) => get<ModelResponse>(`/api/model/${id}`),
  author: (a: string) => get<AuthorResponse>(`/api/author/${encodeURIComponent(a)}`),
  search: (q: string) => get<{ id: string; pipeline_tag: string | null; dl30: number | null }[]>(`/api/search?q=${encodeURIComponent(q)}`),
  leaderboards: () => get<Leaderboards>("/api/leaderboards"),
  hub: () => get<Hub>("/api/hub"),
  meta: () => get<{ days: number; first: string; last: string; models: number; families: number }>("/api/meta"),
};

// ---------- formatting ----------

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("en");

export const fmt = (n: number | null | undefined) => (n == null ? "–" : compact.format(n));
export const fmtFull = (n: number | null | undefined) => (n == null ? "–" : full.format(Math.round(n)));
export const fmtPct = (p: number | null | undefined) =>
  p == null ? "–" : `${p >= 0 ? "+" : "−"}${Math.abs(p * 100) >= 10 ? Math.abs(p * 100).toFixed(0) : Math.abs(p * 100).toFixed(1)}%`;
export const fmtParams = (n: number | null | undefined) => {
  if (!n) return null;
  if (n >= 1e9) return `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B params`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)}M params`;
  return `${(n / 1e3).toFixed(0)}K params`;
};
export const fmtDate = (d: string | Date, opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric" }) =>
  new Date(typeof d === "string" ? d + (d.length === 10 ? "T00:00:00Z" : "") : d).toLocaleDateString("en", { timeZone: "UTC", ...opts });
export const ord = (n: number | null | undefined) => {
  if (n == null) return "–";
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n.toLocaleString("en") + (s[(v - 20) % 10] || s[v] || s[0]);
};
export const taskLabel = (t: string | null | undefined) => (t ? t.replace(/-/g, " ") : "untagged");

// ---------- series math ----------

const DAY = 86400;
export const ts = (d: string) => Date.parse(d + "T00:00:00Z") / 1000;

/** Daily downloads from cumulative totals, spreading each gap evenly across its days. */
export function daily(day: string[], all: (number | null)[]): { t: number[]; v: number[] } {
  const t: number[] = [], v: number[] = [];
  let pt: number | null = null, pv: number | null = null;
  for (let i = 0; i < day.length; i++) {
    const a = all[i];
    if (a == null) continue;
    const ct = ts(day[i]);
    if (pt != null && pv != null) {
      const gap = Math.max(1, Math.round((ct - pt) / DAY));
      const per = Math.max(0, a - pv) / gap;
      for (let k = 1; k <= gap; k++) { t.push(pt + k * DAY); v.push(per); }
    }
    pt = ct; pv = a;
  }
  return { t, v };
}

export function plain(day: string[], vals: (number | null)[]): { t: number[]; v: (number | null)[] } {
  const t: number[] = [], v: (number | null)[] = [];
  for (let i = 0; i < day.length; i++) if (vals[i] != null) { t.push(ts(day[i])); v.push(vals[i]); }
  return { t, v };
}

export function smooth(v: number[], w = 7): number[] {
  const out: number[] = [];
  let s = 0;
  for (let i = 0; i < v.length; i++) {
    s += v[i];
    if (i >= w) s -= v[i - w];
    out.push(s / Math.min(i + 1, w));
  }
  return out;
}

export type Milestone = { value: number; label: string; day: string | null; before: string | null };

/** First snapshot where the all-time total crossed each power of ten. */
export function milestones(s: Series): Milestone[] {
  const firstIdx = s.dl_all.findIndex((x) => x != null);
  if (firstIdx < 0) return [];
  const total = s.dl_all[s.dl_all.length - 1] ?? 0;
  const out: Milestone[] = [];
  for (const [value, label] of [[1e3, "1K"], [1e4, "10K"], [1e5, "100K"], [1e6, "1M"], [1e7, "10M"], [1e8, "100M"], [1e9, "1B"]] as [number, string][]) {
    if ((s.dl_all[firstIdx] ?? 0) >= value) { out.push({ value, label, day: null, before: s.day[firstIdx] }); continue; }
    const i = s.dl_all.findIndex((x) => x != null && x >= value);
    if (i >= 0) out.push({ value, label, day: s.day[i], before: null });
    else { out.push({ value, label, day: null, before: null }); if (value > total * 10) break; }
  }
  // keep only the most recent "before" milestone to avoid a wall of unknowns
  const lastBefore = out.map((m) => !!m.before).lastIndexOf(true);
  return out.filter((m, i) => !m.before || i === lastBefore);
}

// ---------- url state (synced to the huggingface.co parent page) ----------

export type Route = { model?: string; author?: string; compare?: string[]; view?: string };

export function readRoute(): Route {
  const q = new URLSearchParams(location.search);
  return {
    model: q.get("model") || undefined,
    author: q.get("author") || undefined,
    compare: q.get("compare")?.split(",").filter(Boolean),
    view: q.get("view") || undefined,
  };
}

export function routeToQuery(r: Route) {
  const q = new URLSearchParams();
  if (r.model) q.set("model", r.model);
  if (r.author) q.set("author", r.author);
  if (r.compare?.length) q.set("compare", r.compare.join(","));
  if (r.view) q.set("view", r.view);
  return q.toString().replace(/%2F/g, "/").replace(/%2C/g, ",");
}

export const SPACE_URL = "https://huggingface.co/spaces/modelpulse/model-pulse";

export function shareUrl(r: Route) {
  const q = routeToQuery(r);
  return SPACE_URL + (q ? `?${q}` : "");
}

export function navigate(r: Route, replace = false) {
  const q = routeToQuery(r);
  const url = location.pathname + (q ? `?${q}` : "");
  if (replace) history.replaceState(null, "", url);
  else history.pushState(null, "", url);
  try {
    window.parent?.postMessage({ queryString: q, hash: "" }, "https://huggingface.co");
  } catch {}
  window.dispatchEvent(new Event("routechange"));
  if (!replace) window.scrollTo({ top: 0 });
}

/** Accepts "org/name", a full huggingface.co URL, or an hf.co URL. */
export function parseModelInput(s: string): string | null {
  s = s.trim();
  const m = s.match(/(?:huggingface\.co|hf\.co)\/(?!spaces\/|datasets\/)([^/\s?#]+\/[^/\s?#]+)/);
  if (m) return m[1];
  if (/^[\w.-]+\/[\w.-]+$/.test(s)) return s;
  return null;
}
