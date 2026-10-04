import { useEffect, useMemo, useState } from "preact/hooks";
import { api, fmt, fmtDate, fmtFull, fmtPct, navigate, smooth, taskLabel, ts, type Hub, type Leaderboards, type Row, hrefOf } from "./api";
import { Logo } from "./Logo";
import { Chart, Sparkline, type Line } from "./Chart";
import { Search } from "./Search";

// on a phone the tab row scrolls sideways: once the new board has rendered, bring the tapped tab to the middle of the
// row so its neighbours show (scrolling only the row, never the page)
const showTab = (e: { currentTarget: EventTarget | null }) => {
  const el = e.currentTarget as HTMLElement | null, row = el?.parentElement;
  if (!el || !row || row.scrollWidth <= row.clientWidth) return;
  setTimeout(() => {
    const d = el.getBoundingClientRect().left - row.getBoundingClientRect().left;
    row.scrollTo({ left: row.scrollLeft + d - (row.clientWidth - el.offsetWidth) / 2, behavior: "smooth" });
  }, 0);
};

const BOARDS: { key: string; label: string; note: string; author?: boolean }[] = [
  { key: "gainers_7d", label: "Most downloaded this week", note: "Downloads in the last 7 days." },
  { key: "growth_7d", label: "Fastest growing", note: "Downloads this week compared with the average of the three weeks before, among models with at least 1,000 weekly downloads." },
  { key: "breakouts", label: "New this month", note: "Models created in the last 30 days, by downloads this week." },
  { key: "likes_7d", label: "Most liked this week", note: "Likes gained in the last 7 days, among models with at least 1,000 downloads this month." },
  { key: "families", label: "Biggest families", note: "Base models ranked by the 30-day downloads of the model plus all its derivatives." },
  { key: "authors_7d", label: "Organizations", note: "Authors ranked by downloads across all their models this week.", author: true },
];

type RepoKind = "models" | "datasets" | "spaces";
const REPO_BOARDS: Record<"datasets" | "spaces", { key: string; label: string; note: string }[]> = {
  datasets: [
    { key: "gainers_7d", label: "Most downloaded this week", note: "Dataset downloads in the last 7 days." },
    { key: "growth_7d", label: "Fastest growing", note: "Downloads this week compared with the average of the three weeks before, among datasets with at least 1,000 weekly downloads." },
    { key: "breakouts", label: "New this month", note: "Datasets created in the last 30 days, by downloads this week." },
    { key: "used_by_models", label: "Most used for training", note: "Datasets listed as training data by the most models." },
  ],
  spaces: [
    { key: "likes_7d", label: "Most liked this week", note: "Likes gained in the last 7 days. The Hub doesn't publish visits for Spaces, so likes are the measure." },
    { key: "trending", label: "Trending", note: "The Hub's own trending score, from the latest snapshot." },
    { key: "breakouts", label: "New this month", note: "Spaces created in the last 30 days, by likes gained this week." },
    { key: "most_liked", label: "Most liked", note: "All-time likes." },
  ],
};

const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = ["--c1", "--c2", "--c3", "--c4", "--c5"];

export function Home() {
  const [lb, setLb] = useState<Leaderboards | null>(null);
  const [hub, setHub] = useState<Hub | null>(null);
  const [meta, setMeta] = useState<{ models: number; first: string; last: string } | null>(null);
  const [board, setBoard] = useState(BOARDS[0].key);
  const [repo, setRepo] = useState<RepoKind>("models");

  useEffect(() => {
    document.title = "Model Pulse · Download history for every Hugging Face model";
    api.leaderboards().then(setLb);
    api.hub().then(setHub);
    api.meta().then(setMeta);
  }, []);

  const hubLines: Line[] = useMemo(() => {
    if (!hub) return [];
    const days = [...new Set(hub.day)];
    const idx = new Map(days.map((d, i) => [d, i]));
    const series = hub.tags.map(() => new Array(days.length).fill(0));
    hub.day.forEach((d, i) => { series[hub.tags.indexOf(hub.tag[i])][idx.get(d)!] += hub.dl[i]; });
    // spread multi-day gaps already handled server-side (per-day averages); smooth weekly cycles
    const t = days.map(ts);
    const colors = [...PALETTE.map(css), "#9aa0bd", "#c1c5d8", "#7f86a8"];
    const order = hub.tags.map((tag, i) => ({ tag, v: smooth(series[i], 7) }));
    return order.map((o, i) => ({ label: taskLabel(o.tag), color: o.tag === "other" ? css("--rule") : colors[i], t, v: o.v }));
  }, [hub]);

  const examples = lb?.gainers_7d.slice(0, 5).map((r) => r.id!) ?? [];
  const cur = BOARDS.find((b) => b.key === board)!;
  const rows: Row[] = lb?.[board] ?? [];

  return (
    <>
      <div class="wrap home-hero">
        <div class="sticker" aria-hidden="true">
          <svg viewBox="0 0 100 100"><path fill="#E5484D" stroke="#1B1B1F" stroke-width="3" d="M50 3l7.6 11.5 13.2-4.3 1.8 13.7 13.7 1.8-4.3 13.2L97 50l-11.5 7.6 4.3 13.2-13.7 1.8-1.8 13.7-13.2-4.3L50 97l-7.6-11.5-13.2 4.3-1.8-13.7-13.7-1.8 4.3-13.2L3 50l11.5-7.6-4.3-13.2 13.7-1.8 1.8-13.7 13.2 4.3z" /></svg>
          <span>{meta ? fmt(meta.models) : "1.6M"}<br />models</span>
        </div>
        <h1><Logo size={80} />Model <span class="hl">Pulse</span></h1>
        <p class="lede">
          The daily download history of every model and dataset on the Hugging Face Hub, and likes for every Space. Search one or paste its link to see how it grew, how it compares, and who builds on it.
        </p>
        <div class="meta">
          {meta ? `${fmtFull(meta.models)} models · daily since ${fmtDate(meta.first, { month: "short", year: "numeric" })} · updated ${fmtDate(meta.last)}` : "\u00a0"}
        </div>
        <Search big autoFocus all placeholder="A model, dataset or Space, or paste its link" onPick={(id, kind) => navigate({ [kind]: id })} />
        {/* always rendered, so the chips arriving later don't push the chart down */}
        <div class="examples">
          {examples.length > 0 && <span class="muted">popular this week</span>}
          {examples.map((id) => (
            <a key={id} class="chip" href={hrefOf({ model: id })} onClick={(e) => { e.preventDefault(); navigate({ model: id }); }}>{id}</a>
          ))}
        </div>
      </div>

      <div class="wrap hub-chart">
       <div class="card">
        <h2>Daily downloads across the Hub</h2>
        <p class="muted" style={{ margin: "4px 0 14px" }}>All public models, by task, 7-day average.</p>
        {hubLines.length ? (
          <>
            <div class="legend" style={{ marginBottom: 10 }}>
              {hubLines.map((l) => <span class="chip" key={l.label}><i class="sw" style={{ background: l.color, height: 10 }} />{l.label}</span>)}
            </div>
            <Chart lines={hubLines} stacked height={300} valueLabel={(v) => fmtFull(v)} />
          </>
        ) : <div class="skeleton" style={{ height: 300 }} />}
       </div>
      </div>

      <section class="section">
        <div class="wrap">
         <div class="card">
          <div class="seg repo-tabs" role="tablist" aria-label="Rankings for">
            {(["models", "datasets", "spaces"] as RepoKind[]).map((k) => (
              <button key={k} role="tab" aria-selected={repo === k} onClick={() => setRepo(k)}>{k[0].toUpperCase() + k.slice(1)}</button>
            ))}
          </div>
          {repo === "models" ? (
            <>
              <div class="section-head">
                <div>
                  <h2>{cur.label}</h2>
                  <p>{cur.note}{lb ? ` Week ending ${fmtDate(lb.updated)}.` : ""}</p>
                </div>
              </div>
              <div class="seg lb-tabs" role="tablist">
                {BOARDS.map((b) => (
                  <button key={b.key} role="tab" aria-selected={board === b.key} onClick={(e) => { setBoard(b.key); showTab(e); }}>{b.label}</button>
                ))}
              </div>
              {lb ? <Board rows={rows} kind={board} author={!!cur.author} /> : <div class="skeleton" />}
            </>
          ) : <RepoBoards kind={repo} key={repo} />}
         </div>
        </div>
      </section>
    </>
  );
}

function Board({ rows, kind, author }: { rows: Row[]; kind: string; author: boolean }) {
  const [n, setN] = useState(25);
  const go = (r: Row) => (author ? navigate({ author: r.author }) : navigate({ model: r.id }));
  const href = (r: Row) => hrefOf(author ? { author: r.author } : { model: r.id });
  return (
    <>
      <div class="table-scroll">
        <table class="list">
          <thead>
            <tr>
              <th>{author ? "Organization" : "Model"}</th>
              {!author && <th>Last 4 weeks</th>}
              {kind === "likes_7d" ? <th>Likes this week</th> : <th>This week</th>}
              <th>Change</th>
              <th>{kind === "families" ? "Family, 30 days" : "30 days"}</th>
              <th>{author ? "Models" : kind === "likes_7d" ? "Likes" : "All time"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, n).map((r, i) => (
              <tr key={r.id ?? r.author}>
                <td class="name">
                  <span class="rank">{i + 1}</span>
                  <a href={href(r)} onClick={(e) => { e.preventDefault(); go(r); }}>{author ? r.author : r.id}</a>
                  {!author && <span class="sub" style={{ paddingLeft: "2.5em" }}>{taskLabel(r.pipeline_tag)}{kind === "families" && r.fam_members ? `, ${fmtFull(r.fam_members)} derivatives` : ""}</span>}
                </td>
                {!author && <td><Sparkline v={r.spark ?? []} /></td>}
                <td><b>{kind === "likes_7d" ? `+${fmtFull(r.likes_7d)}` : fmt(r.dl_7d)}</b></td>
                <td class={r.growth_7d == null ? "muted" : r.growth_7d >= 0 ? "up" : "down"}>{fmtPct(r.growth_7d)}</td>
                <td>{fmt(kind === "families" ? r.fam_dl30 : r.dl30)}</td>
                <td>{author ? fmtFull(r.models) : kind === "likes_7d" ? fmt(r.likes) : fmt(r.dl_all)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > n && <button class="btn" style={{ marginTop: 16 }} onClick={() => setN(n + 25)}>Show 25 more</button>}
    </>
  );
}

/** Spaces created each week, stacked by SDK: how people build on the Hub. */
function NewSpaces() {
  const [d, setD] = useState<{ sdks: string[]; week: string[]; sdk: string[]; n: number[] } | null>(null);
  useEffect(() => { api.newSpaces().then(setD).catch(() => {}); }, []);
  const lines: Line[] = useMemo(() => {
    if (!d) return [];
    const weeks = [...new Set(d.week)].filter((w) => w >= "2023-01-01").sort();
    const idx = new Map(weeks.map((w, i) => [w, i]));
    const cols = ["--c1", "--c2", "--c3", "--c4", "--c5"].map(css);
    return d.sdks.map((sdk, k) => {
      const v = new Array(weeks.length).fill(0);
      d.week.forEach((w, i) => { if (d.sdk[i] === sdk && idx.has(w)) v[idx.get(w)!] += d.n[i]; });
      // the week in progress is partial; leave it out
      return { label: sdk, color: sdk === "other" ? css("--rule") : cols[k % cols.length], t: weeks.slice(0, -1).map((w) => ts(w) + 3.5 * 86400), v: v.slice(0, -1) };
    });
  }, [d]);
  if (!d || !lines.length) return null;
  return (
    <div class="new-spaces">
      <h3>New Spaces per week, by SDK</h3>
      <div class="legend" style={{ marginBottom: 8 }}>
        {lines.map((l) => <span class="chip" key={l.label}><i class="sw" style={{ background: l.color, height: 10 }} />{l.label}</span>)}
      </div>
      <Chart lines={lines} stacked height={220} valueLabel={(v) => fmtFull(v)} />
      <p class="chart-note">Counted from the Spaces that exist today, by the week they were created.</p>
    </div>
  );
}

function RepoBoards({ kind }: { kind: "datasets" | "spaces" }) {
  const boards = REPO_BOARDS[kind];
  const [lb, setLb] = useState<Leaderboards | null>(null);
  const [board, setBoard] = useState(boards[0].key);
  const [n, setN] = useState(25);
  useEffect(() => { api.boards(kind).then(setLb).catch(() => {}); }, [kind]);
  const cur = boards.find((b) => b.key === board)!;
  const rows = ((lb?.[board] ?? []) as any[]);
  const route = (r: any) => (kind === "datasets" ? { dataset: r.id } : { space: r.id });
  return (
    <>
      {kind === "spaces" && <NewSpaces />}
      <div class="section-head">
        <div>
          <h2>{cur.label}</h2>
          <p>{cur.note}{lb ? ` Week ending ${fmtDate(lb.updated)}.` : ""}</p>
        </div>
      </div>
      <div class="seg lb-tabs" role="tablist">
        {boards.map((b) => <button key={b.key} role="tab" aria-selected={board === b.key} onClick={(e) => { setBoard(b.key); setN(25); showTab(e); }}>{b.label}</button>)}
      </div>
      {!lb ? <div class="skeleton" /> : (
        <>
          <div class="table-scroll">
            <table class="list">
              <thead>
                {kind === "datasets" ? (
                  <tr><th>Dataset</th><th>Last 4 weeks</th><th>This week</th><th>Change</th><th>30 days</th><th>{board === "used_by_models" ? "Models trained on it" : "All time"}</th></tr>
                ) : (
                  <tr><th>Space</th><th>Last 4 weeks</th><th>Likes this week</th><th>30 days</th><th>Likes</th><th>SDK</th></tr>
                )}
              </thead>
              <tbody>
                {rows.slice(0, n).map((r, i) => (
                  <tr key={r.id}>
                    <td class="name">
                      <span class="rank">{i + 1}</span>
                      <a href={hrefOf(route(r))} onClick={(e) => { e.preventDefault(); navigate(route(r)); }}>
                        {kind === "spaces" && r.emoji ? `${r.emoji} ` : ""}{kind === "spaces" && r.title ? r.title : r.id}
                      </a>
                      <span class="sub" style={{ paddingLeft: "2.5em" }}>{kind === "spaces" ? r.id : taskLabel(r.pipeline_tag)}</span>
                    </td>
                    <td><Sparkline v={r.spark ?? []} color={kind === "spaces" ? "var(--c3)" : undefined} /></td>
                    {kind === "datasets" ? (
                      <>
                        <td><b>{fmt(r.dl_7d)}</b></td>
                        <td class={r.growth_7d == null ? "muted" : r.growth_7d >= 0 ? "up" : "down"}>{fmtPct(r.growth_7d)}</td>
                        <td>{fmt(r.dl30)}</td>
                        <td>{board === "used_by_models" ? fmtFull(r.used_by_models) : fmt(r.dl_all)}</td>
                      </>
                    ) : (
                      <>
                        <td><b>+{fmtFull(r.likes_7d)}</b></td>
                        <td>+{fmtFull(r.likes_30d)}</td>
                        <td>{fmt(r.likes)}</td>
                        <td class="muted">{r.sdk ?? "–"}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > n && <button class="btn" style={{ marginTop: 16 }} onClick={() => setN(n + 25)}>Show 25 more</button>}
        </>
      )}
    </>
  );
}
