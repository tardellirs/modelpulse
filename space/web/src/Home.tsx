import { useEffect, useMemo, useState } from "preact/hooks";
import { api, fmt, fmtDate, fmtFull, fmtPct, navigate, smooth, taskLabel, ts, type Hub, type Leaderboards, type Row } from "./api";
import { Logo } from "./Logo";
import { LivePulse } from "./LivePulse";
import { Chart, Sparkline, type Line } from "./Chart";
import { Search } from "./Search";

const BOARDS: { key: string; label: string; note: string; author?: boolean }[] = [
  { key: "gainers_7d", label: "Most downloaded this week", note: "Downloads in the last 7 days." },
  { key: "growth_7d", label: "Fastest growing", note: "Downloads this week compared with the average of the three weeks before, among models with at least 1,000 weekly downloads." },
  { key: "breakouts", label: "New this month", note: "Models created in the last 30 days, by downloads this week." },
  { key: "likes_7d", label: "Most liked this week", note: "Likes gained in the last 7 days, among models with at least 1,000 downloads this month." },
  { key: "families", label: "Biggest families", note: "Base models ranked by the 30-day downloads of the model plus all its derivatives." },
  { key: "authors_7d", label: "Organizations", note: "Authors ranked by downloads across all their models this week.", author: true },
];

const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = ["--c1", "--c2", "--c3", "--c4", "--c5"];

export function Home() {
  const [lb, setLb] = useState<Leaderboards | null>(null);
  const [hub, setHub] = useState<Hub | null>(null);
  const [meta, setMeta] = useState<{ models: number; first: string; last: string } | null>(null);
  const [board, setBoard] = useState(BOARDS[0].key);

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
          The daily download history of every model on the Hugging Face Hub. Search a model or paste its link to see how it grew, how it compares, and how far its derivatives reach.
        </p>
        <div class="meta">
          {meta ? `${fmtFull(meta.models)} models · daily since ${fmtDate(meta.first, { month: "short", year: "numeric" })} · updated ${fmtDate(meta.last)}` : "\u00a0"}
        </div>
        <Search big autoFocus placeholder="Qwen/Qwen3-8B or https://huggingface.co/…" onPick={(id) => navigate({ model: id })} />
        {examples.length > 0 && (
          <div class="examples">
            <span class="muted">popular this week</span>
            {examples.map((id) => (
              <a key={id} class="chip" href={`?model=${id}`} onClick={(e) => { e.preventDefault(); navigate({ model: id }); }}>{id}</a>
            ))}
          </div>
        )}
      </div>

      <LivePulse hub={hub} />

      <div class="wrap callouts">
        <a class="card report-callout wrapped-callout" href="?view=wrapped" onClick={(e) => { e.preventDefault(); navigate({ view: "wrapped" }); }}>
          <span class="tag">New</span>
          <span class="t">Model Pulse Wrapped</span>
          <span class="d">Your last 12 months on the Hub in six cards: downloads, your #1 model, your biggest week, the models built on yours, and your rank.</span>
          <span class="go">Get your Wrapped</span>
        </a>
        <a class="card report-callout" href="?view=report" onClick={(e) => { e.preventDefault(); navigate({ view: "report" }); }}>
          <span class="tag">Report</span>
          <span class="t">What 19 months of daily downloads say about the Hub</span>
          <span class="d">Qwen's rise, the derivative economy, the quantizers, bigger models, and why likes don't measure use.</span>
          <span class="go">Read the report</span>
        </a>
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
          <div class="section-head">
            <div>
              <h2>{cur.label}</h2>
              <p>{cur.note}{lb ? ` Week ending ${fmtDate(lb.updated)}.` : ""}</p>
            </div>
          </div>
          <div class="seg lb-tabs" role="tablist">
            {BOARDS.map((b) => (
              <button key={b.key} role="tab" aria-pressed={board === b.key} aria-selected={board === b.key} onClick={() => setBoard(b.key)}>{b.label}</button>
            ))}
          </div>
          {lb ? <Board rows={rows} kind={board} author={!!cur.author} /> : <div class="skeleton" />}
         </div>
        </div>
      </section>
    </>
  );
}

function Board({ rows, kind, author }: { rows: Row[]; kind: string; author: boolean }) {
  const [n, setN] = useState(25);
  const go = (r: Row) => (author ? navigate({ author: r.author }) : navigate({ model: r.id }));
  const href = (r: Row) => (author ? `?author=${r.author}` : `?model=${r.id}`);
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
