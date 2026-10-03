import type { JSX } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { API_BASE, api, fmt, fmtDate, fmtFull, navigate, shareUrl, type Leaderboards, hrefOf } from "./api";
import { LikeCta } from "./Like";
import { Logo } from "./Logo";

export type WrappedData = {
  author: string;
  period: { from: string; to: string };
  downloads: number;
  every_seconds: number;
  per_minute: number;
  rank: number;
  authors_ranked: number;
  top_pct: number | null;
  likes_gained: number;
  likes_total: number;
  models_total: number;
  models_new: number;
  top_model: { id: string; downloads: number; task: string | null; share: number } | null;
  top_models: { id: string; downloads: number }[];
  best_week: { week_of: string; downloads: number } | null;
  weeks: { week_of: string; downloads: number }[];
  months: { month: string; downloads: number }[];
  ripple: { models: number; downloads_30d: number; top: { id: string; downloads_30d: number; relation: string } | null };
};

const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Counts up to `to` when `run` turns true. */
function Count({ to, run, format = fmtFull }: { to: number; run: boolean; format?: (n: number) => string }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) { setV(0); return; }
    if (reduceMotion()) { setV(to); return; }
    let raf = 0;
    const t0 = performance.now(), dur = 1300;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      setV(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, run]);
  return <>{format(Math.round(v))}</>;
}

const cadence = (d: WrappedData) => {
  if (d.every_seconds >= 1) {
    const s = d.every_seconds;
    if (s < 60) return `one download every ${s.toFixed(s < 10 ? 1 : 0)} seconds`;
    if (s < 3600) return `one download every ${Math.round(s / 60)} minutes`;
    return `one download every ${Math.round(s / 3600)} hours`;
  }
  return d.per_minute >= 1000 ? `${fmt(d.per_minute)} downloads every minute` : `${Math.round(d.per_minute)} downloads every minute`;
};

const short = (id: string) => id.split("/").slice(1).join("/") || id;

/** "A top-10 publisher", "top 3%"… never "top 0.00%". */
const standing = (d: WrappedData) => {
  if (d.rank <= 10) return "top 10";
  if (d.rank <= 100) return "top 100";
  if (d.rank <= 1000) return "top 1,000";
  if (d.top_pct == null || d.top_pct > 50) return null;
  return `top ${d.top_pct < 1 ? d.top_pct.toFixed(1) : Math.ceil(d.top_pct)}%`;
};
/** The 12 months before the current one, zero where there were no downloads (every author gets the same rhythm). */
const fullMonths = (d: WrappedData) => {
  const end = new Date(d.period.to.slice(0, 7) + "-01T00:00:00Z");
  const have = new Map(d.months.map((m) => [m.month.slice(0, 7), m.downloads]));
  return Array.from({ length: 12 }, (_, k) => {
    const t = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - 12 + k, 1));
    const key = t.toISOString().slice(0, 7);
    return { month: key, downloads: have.get(key) ?? 0 };
  });
};
const period = (d: WrappedData) => `${fmtDate(d.period.from, { month: "short", year: "numeric" })} – ${fmtDate(d.period.to, { month: "short", year: "numeric" })}`;

function Bars({ values, highlight, light }: { values: number[]; highlight?: number; light?: boolean }) {
  const max = Math.max(...values, 1);
  return (
    <div class={`w-bars${light ? " light" : ""}`} aria-hidden="true">
      {values.map((v, i) => <span key={i} class={i === highlight ? "hi" : ""} style={{ height: `${Math.max(3, (v / max) * 100)}%` }} />)}
    </div>
  );
}

// ---------- slides ----------

function slides(d: WrappedData, active: number) {
  const on = (i: number) => active === i;
  const weekVals = d.weeks.map((w) => w.downloads);
  const bestIdx = d.best_week ? d.weeks.findIndex((w) => w.week_of === d.best_week!.week_of) : -1;
  const list: { key: string; tone: string; body: JSX.Element }[] = [
    {
      key: "intro", tone: "yellow",
      body: (
        <>
          <div class="w-kicker">Model Pulse Wrapped</div>
          <div class="w-logo"><Logo size={88} /></div>
          <h2 class="w-title"><span class="w-name">{d.author}</span><br />on the Hub</h2>
          <p class="w-sub">Your last 12 months, in six cards.</p>
          <p class="w-mono">{period(d)}</p>
        </>
      ),
    },
    {
      key: "downloads", tone: "blue",
      body: (
        <>
          <div class="w-kicker">Your models were downloaded</div>
          <div class="w-big"><Count to={d.downloads} run={on(1)} /></div>
          <p class="w-sub">times. That's {cadence(d)}.</p>
          <Bars values={fullMonths(d).map((m) => m.downloads)} light />
          <p class="w-mono">downloads by month</p>
        </>
      ),
    },
    {
      key: "top", tone: "paper",
      body: d.top_model ? (
        <>
          <div class="w-kicker">Your #1 model this year</div>
          <h2 class="w-model"><span>{short(d.top_model.id)}</span></h2>
          <div class="w-big sm"><Count to={d.top_model.downloads} run={on(2)} format={fmt} /> <small>downloads</small></div>
          <p class="w-sub">{Math.round(d.top_model.share * 100)}% of everything you served{d.top_model.task ? `, as ${d.top_model.task.replace(/-/g, " ")}` : ""}.</p>
          {d.top_models.length > 1 && (
            <ol class="w-list" start={2}>
              {d.top_models.slice(1, 5).map((m) => <li key={m.id}><span>{short(m.id)}</span><b>{fmt(m.downloads)}</b></li>)}
            </ol>
          )}
        </>
      ) : <p class="w-sub">No single model stood out this year.</p>,
    },
    {
      key: "week", tone: "orange",
      body: d.best_week ? (
        <>
          <div class="w-kicker">Your biggest week</div>
          <h2 class="w-title sm">Week of {fmtDate(d.best_week.week_of, { month: "long", day: "numeric", year: "numeric" })}</h2>
          <div class="w-big"><Count to={d.best_week.downloads} run={on(3)} /></div>
          <p class="w-sub">downloads in seven days.</p>
          <Bars values={weekVals} highlight={bestIdx} />
        </>
      ) : <p class="w-sub">Not enough weeks of data yet.</p>,
    },
    {
      key: "ripple", tone: "green",
      body: d.ripple.models > 0 ? (
        <>
          <div class="w-kicker">Your ripple effect</div>
          <div class="w-big"><Count to={d.ripple.models} run={on(4)} /></div>
          <p class="w-sub">models by other people build on yours. Together they were downloaded <b>{fmt(d.ripple.downloads_30d)}</b> times last month.</p>
          {d.ripple.top && (
            <p class="w-mono">the biggest: {d.ripple.top.id} ({d.ripple.top.relation})</p>
          )}
        </>
      ) : (
        <>
          <div class="w-kicker">Your ripple effect</div>
          <h2 class="w-title sm">No derivatives yet.</h2>
          <p class="w-sub">When someone quantizes or fine-tunes one of your models, it shows up here. You published <b>{d.models_new}</b> new model{d.models_new === 1 ? "" : "s"} this year; one of them could be next.</p>
        </>
      ),
    },
    {
      key: "rank", tone: "red",
      body: (
        <>
          <div class="w-kicker">Among {fmtFull(d.authors_ranked)} publishers on the Hub</div>
          <div class="w-big xl">#<Count to={d.rank} run={on(5)} /></div>
          <p class="w-sub">{standing(d) ? (d.rank <= 1000 ? `A ${standing(d)} publisher by downloads this year.` : `That's the ${standing(d)} by downloads.`) : "by downloads this year."}</p>
          <div class="w-chips">
            <span>+{fmtFull(d.likes_gained)} likes</span>
            <span>{fmtFull(d.models_new)} new models</span>
            <span>{fmtFull(d.models_total)} models in total</span>
          </div>
        </>
      ),
    },
  ];
  return list;
}

// ---------- share image ----------

async function shareImage(d: WrappedData) {
  await Promise.all(["600 80px 'Fredoka'", "500 20px 'IBM Plex Mono'", "400 20px 'Source Sans 3'"].map((f) => document.fonts.load(f)));
  const W = 1080, H = 1350, c = document.createElement("canvas");
  c.width = W; c.height = H;
  const x = c.getContext("2d")!;
  const INK = "#1B1B1F", PAPER = "#ECE9E2", SURF = "#FBFAF5", MARK = "#FFD21E";
  const card = (cx: number, cy: number, w: number, h: number, fill: string) => {
    x.fillStyle = INK; x.beginPath(); x.roundRect(cx + 8, cy + 8, w, h, 26); x.fill();
    x.fillStyle = fill; x.beginPath(); x.roundRect(cx, cy, w, h, 26); x.fill();
    x.lineWidth = 4; x.strokeStyle = INK; x.stroke();
  };
  const text = (t: string, tx: number, ty: number, font: string, color = INK, max?: number) => {
    x.font = font; x.fillStyle = color;
    if (max && x.measureText(t).width > max) { while (t.length > 3 && x.measureText(t + "…").width > max) t = t.slice(0, -1); t += "…"; }
    x.fillText(t, tx, ty);
  };
  x.fillStyle = PAPER; x.fillRect(0, 0, W, H);
  // logo
  x.fillStyle = INK; x.beginPath(); x.roundRect(68, 68, 76, 76, 20); x.fill();
  x.fillStyle = MARK; x.beginPath(); x.roundRect(62, 62, 72, 72, 18); x.fill(); x.lineWidth = 6; x.strokeStyle = INK; x.stroke();
  x.beginPath(); x.lineWidth = 6; x.lineJoin = "round"; x.lineCap = "round";
  x.moveTo(74, 100); x.lineTo(87, 100); x.lineTo(94, 81); x.lineTo(106, 117); x.lineTo(113, 100); x.lineTo(124, 100); x.stroke();
  text("Model Pulse Wrapped", 156, 116, "600 44px 'Fredoka'");
  text(period(d), 62, 196, "500 26px 'IBM Plex Mono'", "#6E6C66");
  // author
  x.font = "600 92px 'Fredoka'";
  const name = d.author.length > 20 ? d.author.slice(0, 19) + "…" : d.author;
  const nw = Math.min(W - 124, x.measureText(name).width + 44);
  x.fillStyle = MARK; x.beginPath(); x.roundRect(54, 222, nw, 120, 18); x.fill();
  text(name, 76, 314, "600 92px 'Fredoka'", INK, W - 170);
  // big stat
  card(62, 386, W - 124, 250, "#3B6FF5");
  text("downloads in 12 months", 100, 446, "500 28px 'IBM Plex Mono'", "#fff");
  text(fmtFull(d.downloads), 96, 572, "600 118px 'Fredoka'", "#fff", W - 200);
  // tiles
  const tiles: [string, string, string][] = [
    ["#1 model", d.top_model ? short(d.top_model.id) : "–", d.top_model ? `${fmt(d.top_model.downloads)} downloads` : ""],
    ["biggest week", d.best_week ? fmt(d.best_week.downloads) : "–", d.best_week ? `week of ${fmtDate(d.best_week.week_of, { month: "short", day: "numeric" })}` : ""],
    ["publisher rank", `#${fmtFull(d.rank)}`, standing(d) ?? `of ${fmt(d.authors_ranked)}`],
    d.ripple.models > 0 ? ["built on yours", fmtFull(d.ripple.models), "models by others"] : ["published", fmtFull(d.models_new), d.models_new === 1 ? "new model this year" : "new models this year"],
  ];
  const tw = (W - 124 - 32) / 2, th = 230;
  tiles.forEach(([k, v, s], i) => {
    const cx = 62 + (i % 2) * (tw + 32), cy = 676 + Math.floor(i / 2) * (th + 32);
    card(cx, cy, tw, th, i === 0 ? MARK : SURF);
    text(k, cx + 30, cy + 54, "500 24px 'IBM Plex Mono'", "#6E6C66");
    text(v, cx + 28, cy + 136, `600 ${v.length > 14 ? 46 : 70}px 'Fredoka'`, INK, tw - 56);
    text(s, cx + 30, cy + 190, "400 26px 'Source Sans 3'", "#3D3D45", tw - 60);
  });
  // monthly bars strip
  const ms = fullMonths(d).map((m) => m.downloads), mx = Math.max(...ms, 1);
  const bx = 62, by = 1196, bw2 = W - 124, bh = 64, gap = 6, w1 = (bw2 - gap * (ms.length - 1)) / Math.max(1, ms.length);
  ms.forEach((v, k) => {
    const h = Math.max(4, (v / mx) * bh), xx = bx + k * (w1 + gap);
    x.fillStyle = k === ms.indexOf(mx) ? MARK : SURF; x.beginPath(); x.roundRect(xx, by + bh - h, w1, h, 4); x.fill();
    x.lineWidth = 3; x.strokeStyle = INK; x.stroke();
  });
  text("modelpulse.ifsp.dev", 62, H - 40, "500 24px 'IBM Plex Mono'", "#6E6C66");
  return new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/png"));
}

// ---------- page ----------

function Entry({ initial }: { initial?: string }) {
  const [v, setV] = useState(initial ?? "");
  const [lb, setLb] = useState<Leaderboards | null>(null);
  useEffect(() => { api.leaderboards().then(setLb).catch(() => {}); }, []);
  const go = (a: string) => { const t = a.trim().replace(/^https?:\/\/huggingface\.co\//, "").split("/")[0]; if (t) navigate({ view: "wrapped", author: t }); };
  return (
    <div class="wrap w-entry">
      <h1><Logo size={72} />Model Pulse <span class="hl">Wrapped</span></h1>
      <p class="lede">Your last 12 months on the Hugging Face Hub, in six cards: total downloads, your #1 model, your biggest week, the models built on yours, and where you rank.</p>
      <form class="w-form" onSubmit={(e) => { e.preventDefault(); go(v); }}>
        <div class="search big"><input value={v} onInput={(e) => setV((e.target as HTMLInputElement).value)} placeholder="Username or org, e.g. Qwen" aria-label="Username or organization" autoFocus spellcheck={false} /></div>
        <button class="btn primary" type="submit">Get my Wrapped</button>
      </form>
      {lb && (
        <div class="examples">
          <span class="muted">or try</span>
          {(lb.authors_7d as any[]).slice(0, 10).map((r) => (
            <a key={r.author} class="chip" href={hrefOf({ view: "wrapped", author: r.author })} onClick={(e) => { e.preventDefault(); go(r.author); }}>{r.author}</a>
          ))}
        </div>
      )}
    </div>
  );
}

export function Wrapped({ author }: { author?: string }) {
  const [d, setD] = useState<WrappedData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [saving, setSaving] = useState(false);
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = author ? `${author}'s last 12 months on Hugging Face · Model Pulse Wrapped` : "Model Pulse Wrapped: your last 12 months on Hugging Face";
    setD(null); setErr(null); setI(0);
    if (!author) return;
    fetch(`${API_BASE}/api/wrapped/${encodeURIComponent(author)}`)
      .then(async (r) => { const b = await r.json(); if (!r.ok) throw new Error(b.detail || "Something went wrong"); return b; })
      .then(setD).catch((e) => setErr(e.message));
  }, [author]);

  const total = d ? slides(d, i).length + 1 : 0;
  const next = () => setI((v) => Math.min(total - 1, v + 1));
  const prev = () => setI((v) => Math.max(0, v - 1));

  useEffect(() => {
    if (!d) return;
    const k = (e: KeyboardEvent) => { if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); next(); } if (e.key === "ArrowLeft") prev(); };
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [d, total]);

  if (!author) return <Entry />;
  if (err) return (
    <div class="wrap w-entry">
      <h1 class="w-err">No Wrapped for {author} yet</h1>
      <p class="lede">{err}</p>
      <Entry initial="" />
    </div>
  );
  if (!d) return (
    <div class="wrap w-loading">
      <Logo size={64} />
      <p>Crunching 12 months of downloads for <b>{author}</b>…</p>
    </div>
  );

  const list = slides(d, i);
  const url = shareUrl({ view: "wrapped", author: d.author });
  const post = `My last 12 months on the Hugging Face Hub: ${fmt(d.downloads)} downloads${standing(d) && (d.rank <= 1000 || (d.top_pct ?? 100) <= 10) ? `, ${standing(d)} of publishers` : ""}. Get your Model Pulse Wrapped:`;
  const isSummary = i === list.length;

  return (
    <div class="wrap w-page">
      <div class="w-stage" ref={stage}>
        <div class="w-progress" aria-hidden="true">
          {Array.from({ length: total }, (_, k) => <span key={k} class={k < i ? "done" : k === i ? "now" : ""} />)}
        </div>
        {!isSummary ? (
          <div class={`w-card tone-${list[i].tone}`} key={list[i].key} aria-live="polite">
            {list[i].body}
            <button class="w-tap left" aria-label="Previous card" onClick={prev} />
            <button class="w-tap right" aria-label="Next card" onClick={next} />
          </div>
        ) : (
          <div class="w-card tone-paper w-summary" key="summary">
            <div class="w-kicker">{period(d)}</div>
            <h2 class="w-title sm"><span class="w-name">{d.author}</span></h2>
            <div class="w-grid">
              <div class="t blue"><span>downloads</span><b>{fmt(d.downloads)}</b></div>
              <div class="t"><span>#1 model</span><b class="s">{d.top_model ? short(d.top_model.id) : "–"}</b></div>
              <div class="t"><span>biggest week</span><b>{d.best_week ? fmt(d.best_week.downloads) : "–"}</b></div>
              <div class="t yellow"><span>publisher rank</span><b>#{fmtFull(d.rank)}</b></div>
              {d.ripple.models > 0
                ? <div class="t"><span>built on yours</span><b>{fmtFull(d.ripple.models)}</b></div>
                : <div class="t"><span>new models</span><b>{fmtFull(d.models_new)}</b></div>}
              <div class="t"><span>likes gained</span><b>+{fmt(d.likes_gained)}</b></div>
            </div>
            <div class="w-actions">
              <button class="btn primary" disabled={saving} onClick={async () => {
                setSaving(true);
                try {
                  const b = await shareImage(d);
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(b); a.download = `${d.author}-model-pulse-wrapped.png`; a.click();
                  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
                } finally { setSaving(false); }
              }}>{saving ? "Drawing…" : "Download image"}</button>
              <a class="btn" target="_blank" rel="noopener" href={`https://x.com/intent/post?text=${encodeURIComponent(post)}&url=${encodeURIComponent(url)}`}>Post on X</a>
              <a class="btn" target="_blank" rel="noopener" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}>LinkedIn</a>
              <button class="btn" onClick={() => navigator.clipboard?.writeText(url)}>Copy link</button>
            </div>
            <div class="w-more">
              <a href={hrefOf({ author: d.author })} onClick={(e) => { e.preventDefault(); navigate({ author: d.author }); }}>See {d.author}'s models</a>
              <a href={hrefOf({ view: "wrapped" })} onClick={(e) => { e.preventDefault(); navigate({ view: "wrapped" }); }}>Try another name</a>
            </div>
            <div class="w-like"><LikeCta /></div>
          </div>
        )}
        <div class="w-nav">
          <button class="btn" onClick={prev} disabled={i === 0}>Back</button>
          <span class="w-mono">{i + 1} / {total}</span>
          <button class="btn primary" onClick={next} disabled={isSummary}>{i === list.length - 1 ? "Summary" : "Next"}</button>
        </div>
      </div>
    </div>
  );
}

if ((import.meta as any).env?.DEV) (window as any).__wrappedImage = shareImage;
