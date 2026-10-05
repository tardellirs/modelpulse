import { useEffect, useMemo, useState } from "preact/hooks";
import { api, daily, fmt, fmtDate, fmtFull, fmtParams, fmtPct, navigate, plain, smooth, taskLabel, weekly, WEEK, type AuthorResponse, type Route, hrefOf } from "./api";
import { Chart, type Line } from "./Chart";

type Metric = "weekly" | "daily" | "month" | "total";

export function AuthorPage({ route }: { route: Route }) {
  const a = route.author!;
  const [d, setD] = useState<AuthorResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric>("weekly");
  const [n, setN] = useState(30);
  const [tab, setTab] = useState<"models" | "datasets" | "spaces">("models");

  useEffect(() => {
    setD(null); setErr(null);
    api.author(a).then((r) => {
      setD(r);
      setTab(r.models.length ? "models" : r.datasets?.length ? "datasets" : "spaces");
      document.title = `${a} on Hugging Face: downloads and rankings · Model Pulse`;
    }).catch((e) => setErr(e.message));
  }, [a]);

  const lines: Line[] = useMemo(() => {
    if (!d) return [];
    const c = getComputedStyle(document.documentElement).getPropertyValue("--c1").trim();
    const s = d.series;
    if (metric === "weekly") {
      const x = daily(s.day, s.dl_all), w = weekly(x.t, x.v);
      return [{ label: a, color: c, t: w.t, v: w.v }];
    }
    if (metric === "daily") {
      const x = daily(s.day, s.dl_all);
      return [{ label: a, color: c, t: x.t, v: smooth(x.v, 7), fill: true }];
    }
    const x = plain(s.day, metric === "month" ? s.dl30 : s.dl_all);
    return [{ label: a, color: c, t: x.t, v: x.v, fill: true }];
  }, [d, metric]);

  if (err) return <div class="wrap err"><h1>Nothing found for {a}</h1><p class="muted">{err}</p></div>;
  // same shape as the loaded page (a row of chips above the name) so nothing jumps when data arrives
  if (!d) return <div class="wrap hero"><div class="crumbs" style={{ visibility: "hidden" }}><span class="chip">loading</span></div><h1 class="model-name">{a}</h1><div class="skeleton" style={{ marginTop: 24 }} /></div>;

  // totals over every model of the author, not just the listed ones
  const mt = d.model_totals;
  const tot = mt
    ? { all: mt.dl_all ?? 0, m30: mt.dl30 ?? 0, w: mt.dl_7d ?? 0, likes: mt.likes ?? 0, n: mt.models }
    : d.models.reduce(
      (acc, m) => ({ ...acc, all: acc.all + (m.dl_all ?? 0), m30: acc.m30 + (m.dl30 ?? 0), w: acc.w + (m.dl_7d ?? 0), likes: acc.likes + (m.likes ?? 0) }),
      { all: 0, m30: 0, w: 0, likes: 0, n: d.models.length },
    );

  return (
    <>
      <div class="wrap hero">
        <div class="crumbs">
          {d.models.length > 0 && <span class="chip">{fmtFull(tot.n)} tracked models</span>}
          {!!d.totals?.datasets && <span class="chip">{fmtFull(d.totals.datasets)} datasets</span>}
          {!!d.totals?.spaces && <span class="chip">{fmtFull(d.totals.spaces)} Spaces</span>}
          <a class="chip" href={`https://huggingface.co/${a}`} target="_blank" rel="noopener">Open on Hugging Face ↗</a>
          <a class="chip chip-hot" href={hrefOf({ view: "wrapped", author: a })} onClick={(e) => { e.preventDefault(); navigate({ view: "wrapped", author: a }); }}>See {a}'s Wrapped</a>
        </div>
        <h1 class="model-name">{a}</h1>
        {d.models.length > 0 ? (<>
        <div class="card stats" style={{ padding: 0 }}>
          <div class="fig fig-main"><div class="num">{fmtFull(tot.all)}</div><div class="label">downloads all time, across all models</div></div>
          <div class="fig"><div class="val">{fmt(tot.m30)}</div><div class="label">last 30 days</div></div>
          <div class="fig"><div class="val">{fmt(tot.w)}</div><div class="label">last 7 days</div></div>
          <div class="fig"><div class="val">{fmt(tot.likes)}</div><div class="label">likes</div></div>
        </div>
        <div class="card chart-card">
        <div class="chart-bar">
          <div class="left">
            <div class="seg" role="group" aria-label="Metric">
              <button aria-pressed={metric === "weekly"} onClick={() => setMetric("weekly")}>Weekly</button>
              <button aria-pressed={metric === "daily"} onClick={() => setMetric("daily")}>Daily</button>
              <button aria-pressed={metric === "month"} onClick={() => setMetric("month")}>Rolling 30 days</button>
              <button aria-pressed={metric === "total"} onClick={() => setMetric("total")}>All time</button>
            </div>
          </div>
        </div>
        <Chart lines={lines} height={340} bars={metric === "weekly"} endLabel={metric !== "weekly"}
          tipDate={metric === "weekly" ? (t) => `Week of ${fmtDate(new Date((t - WEEK / 2) * 1000), { month: "short", day: "numeric", year: "numeric" })}` : undefined} />
        </div>
        </>) : (
          <div class="card stats" style={{ padding: 0 }}>
            <div class="fig fig-main"><div class="num">{fmtFull(d.totals?.datasets_dl30 ?? 0)}</div><div class="label">dataset downloads, last 30 days</div></div>
            <div class="fig"><div class="val">{fmtFull(d.totals?.datasets ?? 0)}</div><div class="label">datasets</div></div>
            <div class="fig"><div class="val">{fmtFull(d.totals?.spaces ?? 0)}</div><div class="label">Spaces</div></div>
            <div class="fig"><div class="val">{fmt(d.totals?.spaces_likes ?? 0)}</div><div class="label">Space likes</div></div>
          </div>
        )}
      </div>
      <section class="section">
        <div class="wrap">
          <div class="card">
          <div class="seg repo-tabs" role="tablist" aria-label={`What ${a} publishes`}>
            {d.models.length > 0 && <button role="tab" aria-selected={tab === "models"} onClick={() => { setTab("models"); setN(30); }}>Models</button>}
            {!!d.datasets?.length && <button role="tab" aria-selected={tab === "datasets"} onClick={() => { setTab("datasets"); setN(30); }}>Datasets {fmtFull(d.totals?.datasets)}</button>}
            {!!d.spaces?.length && <button role="tab" aria-selected={tab === "spaces"} onClick={() => { setTab("spaces"); setN(30); }}>Spaces {fmtFull(d.totals?.spaces)}</button>}
          </div>
          {tab === "models" && (<>
          <div class="section-head"><div><h2>Models by {a}</h2><p>Sorted by downloads in the last 30 days.</p></div></div>
          <div class="table-scroll">
            <table class="list">
              <thead><tr><th>Model</th><th>This week</th><th>Change</th><th>30 days</th><th>All time</th><th>Likes</th></tr></thead>
              <tbody>
                {d.models.slice(0, n).map((m) => (
                  <tr key={m.id}>
                    <td class="name">
                      <a href={hrefOf({ model: m.id })} onClick={(e) => { e.preventDefault(); navigate({ model: m.id }); }}>{m.id.split("/").slice(1).join("/")}</a>
                      <span class="sub">{[taskLabel(m.pipeline_tag), fmtParams(m.params)].filter(Boolean).join(", ")}</span>
                    </td>
                    <td><b>{fmt(m.dl_7d)}</b></td>
                    <td class={m.growth_7d == null ? "muted" : m.growth_7d >= 0 ? "up" : "down"}>{fmtPct(m.growth_7d)}</td>
                    <td>{fmt(m.dl30)}</td>
                    <td>{fmt(m.dl_all)}</td>
                    <td>{fmt(m.likes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {d.models.length > n && <button class="btn" style={{ marginTop: 16 }} onClick={() => setN(n + 30)}>Show 30 more</button>}
          </>)}
          {tab === "datasets" && d.datasets && (<>
            <div class="section-head"><div><h2>Datasets by {a}</h2><p>Sorted by downloads in the last 30 days.</p></div></div>
            <div class="table-scroll">
              <table class="list">
                <thead><tr><th>Dataset</th><th>This week</th><th>Change</th><th>30 days</th><th>All time</th><th>Models trained on it</th></tr></thead>
                <tbody>
                  {d.datasets.slice(0, n).map((x) => (
                    <tr key={x.id}>
                      <td class="name">
                        <a href={hrefOf({ dataset: x.id })} onClick={(e) => { e.preventDefault(); navigate({ dataset: x.id }); }}>{x.id.split("/").slice(1).join("/")}</a>
                        <span class="sub">{[x.pipeline_tag ? taskLabel(x.pipeline_tag) : null, x.size].filter(Boolean).join(", ")}</span>
                      </td>
                      <td><b>{fmt(x.dl_7d)}</b></td>
                      <td class={x.growth_7d == null ? "muted" : x.growth_7d >= 0 ? "up" : "down"}>{fmtPct(x.growth_7d)}</td>
                      <td>{fmt(x.dl30)}</td>
                      <td>{fmt(x.dl_all)}</td>
                      <td>{x.used_by_models ? fmtFull(x.used_by_models) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {d.datasets.length > n && <button class="btn" style={{ marginTop: 16 }} onClick={() => setN(n + 30)}>Show 30 more</button>}
          </>)}
          {tab === "spaces" && d.spaces && (<>
            <div class="section-head"><div><h2>Spaces by {a}</h2><p>Sorted by likes. The Hub doesn't publish visits for Spaces.</p></div></div>
            <div class="table-scroll">
              <table class="list">
                <thead><tr><th>Space</th><th>Likes this week</th><th>30 days</th><th>Likes</th><th>SDK</th></tr></thead>
                <tbody>
                  {d.spaces.slice(0, n).map((x) => (
                    <tr key={x.id}>
                      <td class="name">
                        <a href={hrefOf({ space: x.id })} onClick={(e) => { e.preventDefault(); navigate({ space: x.id }); }}>{x.emoji ? `${x.emoji} ` : ""}{x.title || x.id.split("/").slice(1).join("/")}</a>
                        <span class="sub">{x.id}</span>
                      </td>
                      <td><b>+{fmtFull(x.likes_7d)}</b></td>
                      <td>+{fmtFull(x.likes_30d)}</td>
                      <td>{fmt(x.likes)}</td>
                      <td class="muted">{x.sdk ?? "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {d.spaces.length > n && <button class="btn" style={{ marginTop: 16 }} onClick={() => setN(n + 30)}>Show 30 more</button>}
          </>)}
          </div>
        </div>
      </section>
    </>
  );
}
