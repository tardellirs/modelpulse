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

  useEffect(() => {
    setD(null); setErr(null);
    api.author(a).then((r) => { setD(r); document.title = `${a} on Hugging Face: model downloads and rankings · Model Pulse`; }).catch((e) => setErr(e.message));
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

  if (err) return <div class="wrap err"><h1>No models found for {a}</h1><p class="muted">{err}</p></div>;
  if (!d) return <div class="wrap hero"><div class="model-name">{a}</div><div class="skeleton" style={{ marginTop: 40 }} /></div>;

  const tot = d.models.reduce(
    (acc, m) => ({ all: acc.all + (m.dl_all ?? 0), m30: acc.m30 + (m.dl30 ?? 0), w: acc.w + (m.dl_7d ?? 0), likes: acc.likes + (m.likes ?? 0) }),
    { all: 0, m30: 0, w: 0, likes: 0 },
  );

  return (
    <>
      <div class="wrap hero">
        <div class="crumbs">
          <span class="chip">{d.models.length >= 200 ? "200+" : d.models.length} tracked models</span>
          <a class="chip" href={`https://huggingface.co/${a}`} target="_blank" rel="noopener">Open on Hugging Face ↗</a>
          <a class="chip chip-hot" href={hrefOf({ view: "wrapped", author: a })} onClick={(e) => { e.preventDefault(); navigate({ view: "wrapped", author: a }); }}>See {a}'s Wrapped</a>
        </div>
        <h1 class="model-name">{a}</h1>
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
      </div>
      <section class="section">
        <div class="wrap">
          <div class="card">
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
          </div>
        </div>
      </section>
    </>
  );
}
