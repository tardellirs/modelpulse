import { useEffect, useMemo, useState } from "preact/hooks";
import {
  api, daily, weekly, WEEK, fmt, fmtDate, fmtFull, fmtParams, fmtPct, milestones, navigate, ord, plain, shareUrl, smooth, taskLabel, ts,
  type ModelResponse, type Route, hrefOf } from "./api";
import { Chart, type Line, type Marker } from "./Chart";
import { Search } from "./Search";
import { Share } from "./Share";
import { UsedBy } from "./UsedBy";

type Metric = "weekly" | "daily" | "month" | "total" | "likes";
type RangeKey = "1M" | "3M" | "6M" | "1Y" | "All";
const RANGES: Record<RangeKey, number | null> = { "1M": 30, "3M": 91, "6M": 182, "1Y": 365, All: null };
const COLORS = ["--c1", "--c2", "--c3", "--c4", "--c5"];
const color = (i: number) => getComputedStyle(document.documentElement).getPropertyValue(COLORS[i % COLORS.length]).trim();

function lineFor(d: ModelResponse, metric: Metric, family: boolean) {
  const s = family && d.family ? d.family : d.series;
  if (metric === "weekly") {
    const { t, v } = daily(s.day, s.dl_all);
    return weekly(t, v);
  }
  if (metric === "daily") {
    const { t, v } = daily(s.day, s.dl_all);
    return { t, v: smooth(v, 7), raw: v };
  }
  if (metric === "month") return plain(s.day, s.dl30);
  if (metric === "total") return plain(s.day, s.dl_all);
  return plain(d.series.day, d.series.likes);
}

export function ModelPage({ route }: { route: Route }) {
  const id = route.model!;
  const compare = route.compare ?? [];
  const [data, setData] = useState<ModelResponse | null>(null);
  const [others, setOthers] = useState<ModelResponse[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetricRaw] = useState<Metric>("weekly");
  const [rangeKey, setRangeKey] = useState<RangeKey>("1Y");
  const [zoom, setZoom] = useState<[number, number] | null>(null);
  const setMetric = (m: Metric) => { setZoom(null); setMetricRaw(m); };
  const [family, setFamily] = useState(false);
  const [log, setLog] = useState(false);
  const [adding, setAdding] = useState(false);
  // open the compare box toward the side with room: anchored left unless the button sits near the right edge
  const [compareAlign, setCompareAlign] = useState<"left" | "right">("left");

  useEffect(() => {
    setData(null); setErr(null); setFamily(false); setZoom(null);
    api.model(id).then((d) => {
      setData(d);
      if (d.model.id !== id) navigate({ ...route, model: d.model.id }, true);
      document.title = `${d.model.id} downloads: daily history and stats · Model Pulse`;
    }).catch((e) => setErr(e.message));
  }, [id]);

  useEffect(() => {
    Promise.all(compare.map((c) => api.model(c).catch(() => null))).then((r) => setOthers(r.filter(Boolean) as ModelResponse[]));
  }, [compare.join(",")]);

  const m = data?.model;
  const hasDaily = !!data && data.series.dl_all.filter((x) => x != null).length > 7;
  const effMetric: Metric = (metric === "daily" || metric === "weekly") && !hasDaily ? "month" : metric;

  const lines: Line[] = useMemo(() => {
    if (!data) return [];
    const main = lineFor(data, effMetric, family) as { t: number[]; v: (number | null)[]; partial?: boolean };
    const out: Line[] = [];
    out.push({ label: family ? `${data.model.id} + derivatives` : data.model.id, color: color(0), t: main.t, v: main.v, fill: !others.length });
    others.forEach((o, i) => {
      const l = lineFor(o, effMetric, false);
      out.push({ label: o.model.id, color: color(i + 1), t: l.t, v: l.v });
    });
    return out;
  }, [data, others, effMetric, family]);

  const mainPartial = useMemo(() => (data && effMetric === "weekly" ? (lineFor(data, "weekly", family) as { partial?: boolean }).partial : false), [data, effMetric, family]);
  const ms = useMemo(() => (data ? milestones(family && data.family ? { ...data.series, ...data.family, likes: [] } : data.series) : []), [data, family]);
  const markers: Marker[] = useMemo(
    () => (effMetric === "likes" || others.length ? [] : ms.filter((x) => x.day).map((x) => ({ t: ts(x.day!), label: x.label }))),
    [ms, effMetric, others.length],
  );

  const range: [number, number] | null = useMemo(() => {
    if (zoom) return zoom;
    const days = RANGES[rangeKey];
    if (!days || !lines.length) return null;
    const last = Math.max(...lines.map((l) => l.t[l.t.length - 1] ?? 0));
    return [last - days * 86400, last];
  }, [rangeKey, zoom, lines]);

  if (err)
    return (
      <div class="wrap err">
        <h1>No history for {id}</h1>
        <p class="muted">{err}</p>
        <p>Check the spelling, or try one of the models below.</p>
        <Search onPick={(x) => navigate({ model: x })} placeholder="Search another model" autoFocus />
      </div>
    );

  if (!data || !m)
    return (
      <div class="wrap hero">
        <div class="model-name">{id}</div>
        <div class="skeleton" style={{ marginTop: 40 }} />
      </div>
    );

  const [org, name] = m.id.includes("/") ? [m.id.split("/")[0], m.id.split("/").slice(1).join("/")] : [null, m.id];
  const params = fmtParams(m.params);
  const base = m.base_ids?.[0];
  const relWord: Record<string, string> = { quantized: "Quantized from", finetune: "Fine-tuned from", adapter: "Adapter for", merge: "Merged from" };
  const big = family && m.fam_all ? m.fam_all : m.dl_all ?? m.dl30;

  const setCompare = (list: string[]) => navigate({ model: m.id, compare: list.length ? list : undefined }, true);

  return (
    <>
      <div class="wrap hero">
        <div class="crumbs">
          {m.pipeline_tag && <span class="chip">{taskLabel(m.pipeline_tag)}</span>}
          {params && <span class="chip">{params}</span>}
          {m.license && <span class="chip">{m.license}</span>}
          {m.likes != null && (
            <span class="chip" title={m.likes_7d ? `${fmtFull(m.likes_7d)} new likes in the last 7 days` : undefined}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="#ff6b81" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2.1 0 3.6 1.1 5.4 3 1.8-1.9 3.3-3 5.4-3 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z" /></svg>
              {fmtFull(m.likes)} likes{m.likes_7d ? <span class="up">+{fmtFull(m.likes_7d)}</span> : null}
            </span>
          )}
          {base && (
            <a class="chip" href={hrefOf({ model: base })} onClick={(e) => { e.preventDefault(); navigate({ model: base }); }}>
              {relWord[m.base_relation ?? ""] ?? "Based on"} {base}
            </a>
          )}
          {data.datasets?.slice(0, 2).map((x) => (
            <a key={x.id} class="chip" href={hrefOf({ dataset: x.id })} onClick={(e) => { e.preventDefault(); navigate({ dataset: x.id }); }}>Trained on {x.id}</a>
          ))}
          <a class="chip" href={`https://huggingface.co/${m.id}`} target="_blank" rel="noopener">Open on Hugging Face ↗</a>
        </div>
        <h1 class="model-name">
          {org && (
            <a href={hrefOf({ author: org })} onClick={(e) => { e.preventDefault(); navigate({ author: org }); }} class="org">{org}/</a>
          )}
          <span class="hl">{name}</span>
        </h1>

        <div class="card stats" style={{ padding: 0 }}>
          <div class="fig fig-main">
            <div class="num" title={fmtFull(big)}>{fmtFull(big)}</div>
            <div class="label">
              {m.dl_all != null ? "downloads all time" : "downloads in the last 30 days"}
              {family ? `, including ${fmtFull(m.fam_members)} derivatives` : ""}
            </div>
          </div>
          <div class="fig">
            <div class="val">{fmt(family ? m.fam_dl30 : m.dl30)}</div>
            <div class="label">last 30 days</div>
          </div>
          <div class="fig">
            <div class="val">
              {fmt(family ? m.fam_7d : m.dl_7d)}
              {!family && m.growth_7d != null && <small class={m.growth_7d >= 0 ? "up" : "down"}>{fmtPct(m.growth_7d)}</small>}
            </div>
            <div class="label">last 7 days{!family && m.growth_7d != null ? ", vs. 3-week average" : ""}</div>
          </div>
          <div class="fig">
            <div class="val">#{fmtFull(m.rank_dl30)}</div>
            <div class="label">on the Hub{m.rank_task && m.pipeline_tag ? `, ${ord(m.rank_task)} in ${taskLabel(m.pipeline_tag)}` : ""}</div>
          </div>
        </div>

        <div class="card chart-card">
        <div class="chart-bar">
          <div class="left">
            <div class="seg" role="group" aria-label="Metric">
              {hasDaily && <button aria-pressed={effMetric === "weekly"} onClick={() => setMetric("weekly")}>Weekly</button>}
              {hasDaily && <button aria-pressed={effMetric === "daily"} onClick={() => setMetric("daily")}>Daily</button>}
              <button aria-pressed={effMetric === "month"} onClick={() => setMetric("month")}>Rolling 30 days</button>
              {hasDaily && <button aria-pressed={effMetric === "total"} onClick={() => setMetric("total")}>All time</button>}
              <button aria-pressed={effMetric === "likes"} onClick={() => { setMetric("likes"); setFamily(false); }}>Likes</button>
            </div>
            <div class="seg" role="group" aria-label="Time range">
              {(Object.keys(RANGES) as RangeKey[]).map((k) => (
                <button key={k} aria-pressed={!zoom && rangeKey === k} onClick={() => { setZoom(null); setRangeKey(k); }}>{k}</button>
              ))}
            </div>
          </div>
          <div class="right">
            {!!data.family && !others.length && effMetric !== "likes" && (
              <div class="seg"><button aria-pressed={family} onClick={() => setFamily(!family)}>Include {fmtFull(m.fam_members)} derivatives</button></div>
            )}
            {others.length > 0 && <div class="seg"><button aria-pressed={log} onClick={() => setLog(!log)}>Log scale</button></div>}
            <div class={`add-compare align-${compareAlign}`}>
              <button class="btn" onClick={(e) => {
                const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                setCompareAlign(r.left + 440 > window.innerWidth - 16 ? "right" : "left");
                setAdding(!adding);
              }} aria-expanded={adding} disabled={compare.length >= 4}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
                Compare
              </button>
              {adding && (
                <Search autoFocus placeholder="Add a model to compare" exclude={[m.id, ...compare]}
                  onPick={(x) => { setAdding(false); setCompare([...compare, x]); }} />
              )}
            </div>
          </div>
        </div>

        {others.length > 0 && (
          <div class="legend" style={{ marginBottom: 8 }}>
            <span class="chip"><i class="sw" style={{ background: color(0) }} />{m.id}</span>
            {others.map((o, i) => (
              <span class="chip" key={o.model.id}>
                <i class="sw" style={{ background: color(i + 1) }} />
                <a href={hrefOf({ model: o.model.id })} onClick={(e) => { e.preventDefault(); navigate({ model: o.model.id }); }}>{o.model.id}</a>
                <button aria-label={`Remove ${o.model.id}`} onClick={() => setCompare(compare.filter((c) => c !== o.model.id))}>✕</button>
              </span>
            ))}
          </div>
        )}

        <Chart lines={lines} range={range} log={log} markers={markers} onZoom={(r) => setZoom(r)} height={380}
          bars={effMetric === "weekly"} partialLast={effMetric === "weekly" && !!mainPartial} endLabel={effMetric !== "weekly"}
          tipDate={effMetric === "weekly" ? (t) => `Week of ${fmtDate(new Date((t - WEEK / 2) * 1000), { month: "short", day: "numeric", year: "numeric" })}` : undefined}
          valueLabel={effMetric === "daily" ? (v) => fmtFull(v) + "/day" : effMetric === "weekly" ? (v) => fmtFull(v) + "/week" : undefined} />
        <p class="chart-note">
          {effMetric === "daily" && "7-day average of daily downloads. "}
          {effMetric === "weekly" && (others.length ? "Downloads per week, Monday to Sunday. " : "Downloads per week, Monday to Sunday; the striped bar is the week in progress. ")}
          {effMetric !== "likes" && `Daily figures start on ${fmtDate("2025-02-27")}, when the Hub began reporting all-time totals; the rolling 30-day view goes back to ${fmtDate("2024-07-29")}. `}
          The Hub sometimes books delayed downloads in a single day, which shows up as a short spike. Drag on the chart to zoom, double-click to reset.
        </p>
        </div>
      </div>

      {ms.length > 0 && effMetric !== "likes" && (
        <section class="section">
          <div class="wrap">
            <div class="section-head">
              <div>
                <h2>Milestones</h2>
                <p>The day {family ? "the family" : "the model"} first crossed each mark in all-time downloads.</p>
              </div>
            </div>
            <ol class="timeline">
              {ms.map((x) => (
                <li key={x.label} class={x.day || x.before ? "" : "pending"}>
                  <div class="m">{x.label}</div>
                  <div class="when">{x.day ? fmtDate(x.day) : x.before ? `Before ${fmtDate(x.before, { month: "short", year: "numeric" })}` : "Not yet"}</div>
                </li>
              ))}
            </ol>
          </div>
        </section>
      )}

      {(m.fam_members > 0 || data.children.length > 0) && <Family data={data} />}

      {!!data.spaces?.count && (
        <section class="section">
          <div class="wrap">
            <div class="section-head"><div><h2>Spaces using {m.id.split("/").pop()}</h2><p>Spaces whose card lists this model, and how that number grew.</p></div></div>
            <UsedBy title="Spaces using it" data={data.spaces} by="space" note="Counted from today's Space cards, by the month each Space was created." />
          </div>
        </section>
      )}

      <About data={data} />

      <Share model={m} url={shareUrl({ model: m.id, compare: compare.length ? compare : undefined })} />
    </>
  );
}

const RELATION: Record<string, string> = { quantized: "a quantization", finetune: "a fine-tune", adapter: "an adapter", merge: "a merge" };

/** The page in plain sentences: easy to skim, and the text search engines quote. */
function About({ data }: { data: ModelResponse }) {
  const m = data.model as ModelResponse["model"] & Record<string, any>;
  const [author] = m.id.includes("/") ? m.id.split("/") : [""];
  const name = m.id.split("/").pop();
  const task = m.pipeline_tag ? taskLabel(m.pipeline_tag) : "";
  const size = !m.params ? "" : m.params >= 1e9 ? `${(m.params / 1e9).toFixed(1)}B` : `${Math.round(m.params / 1e6)}M`;
  const kind = `${size ? `${size}-parameter ` : ""}${task}`.trim();
  const base = m.base_ids?.[0];
  const link = (r: Route, text: string) => <a href={hrefOf(r)} onClick={(e) => { e.preventDefault(); navigate(r); }}>{text}</a>;
  return (
    <section class="section">
      <div class="wrap about">
        <h2>About {name}</h2>
        <p>
          <b>{m.id}</b> is {/^[aeio8]|^1[18]/i.test(kind) ? "an" : "a"} {kind ? `${kind} model` : "model"}{author && <> by {link({ author }, author)}</>}.
          {" "}In the last 30 days it was downloaded <b>{fmtFull(m.dl30)}</b> times ({fmtFull(m.dl_7d)} in the last 7 days)
          {m.dl_all ? <>, and <b>{fmtFull(m.dl_all)}</b> times in total</> : null}.
          {m.rank_dl30 ? <> It ranks #{fmtFull(m.rank_dl30)} on the Hub by monthly downloads{m.rank_task && m.pipeline_tag ? <> and #{fmtFull(m.rank_task)} among {task} models</> : null}.</> : null}
          {m.likes != null ? <> It has {fmtFull(m.likes)} likes{m.likes_7d ? `, ${fmtFull(m.likes_7d)} of them in the last week` : ""}.</> : null}
        </p>
        {base && <p>It is {RELATION[m.base_relation ?? ""] ?? "a derivative"} of {link({ model: base }, base)}.</p>}
        {m.fam_members > 0 && (
          <p>
            {fmtFull(m.fam_members)} models build on {name}: {fmtFull(m.n_quantized)} quantized, {fmtFull(m.n_finetune)} fine-tuned, {fmtFull(m.n_adapter)} adapters
            and {fmtFull(m.n_merge)} merges. Together with the original they were downloaded {fmtFull(m.fam_dl30)} times in the last 30 days.
            {" "}{link({ view: "galaxy", model: m.id }, `See the ${name} galaxy`)}.
          </p>
        )}
        <p class="muted">Figures come from daily snapshots of the Hugging Face Hub and update every day.</p>
      </div>
    </section>
  );
}

function Family({ data }: { data: ModelResponse }) {
  const m = data.model;
  const parts = [
    { k: "Quantized", n: m.n_quantized ?? 0, c: "var(--c1)" },
    { k: "Fine-tuned", n: m.n_finetune ?? 0, c: "var(--c2)" },
    { k: "Adapters", n: m.n_adapter ?? 0, c: "var(--c3)" },
    { k: "Merges", n: m.n_merge ?? 0, c: "var(--c4)" },
  ];
  const total = parts.reduce((a, p) => a + p.n, 0) || 1;
  const share = m.fam_dl30 && m.dl30 != null ? 1 - m.dl30 / m.fam_dl30 : null;
  return (
    <section class="section">
      <div class="wrap">
        <div class="card family-top">
          <div class="family-sum">
            <h2>Family</h2>
            <p>
              {m.fam_members > 0
                ? <>{fmtFull(m.fam_members)} models build on {m.id.split("/").pop()}, directly or through other derivatives. Together with the original they were downloaded <b>{fmt(m.fam_dl30)}</b> times in the last 30 days{share != null && share > 0.01 ? <>, and <b>{Math.round(share * 100)}%</b> of that went to derivatives</> : null}.</>
                : <>Derivatives of {m.id.split("/").pop()} on the Hub.</>}
            </p>
            {m.fam_members > 0 && (
              <>
                <div class="big">{fmtFull(m.fam_all)}</div>
                <div class="muted" style={{ marginBottom: 18 }}>family downloads all time</div>
                <div class="rel" aria-hidden="true">
                  {parts.filter((p) => p.n).map((p) => <span key={p.k} style={{ width: `${(p.n / total) * 100}%`, background: p.c }} />)}
                </div>
                <div class="rel-legend">
                  {parts.map((p) => (
                    <div key={p.k}><span><i style={{ background: p.c }} />{p.k}</span><b>{fmtFull(p.n)}</b></div>
                  ))}
                </div>
                <a class="btn galaxy-btn" href={hrefOf({ view: "galaxy", model: m.id })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: m.id }); }}>
                  <span class="g-dot" aria-hidden="true" />See the {fmtFull(m.fam_members)} models as a galaxy
                </a>
              </>
            )}
          </div>
          {data.children.length > 0 && (
            <div>
              <div class="table-scroll">
                <table class="list">
                  <thead><tr><th>Most downloaded direct derivatives</th><th>Type</th><th>30 days</th><th>All time</th></tr></thead>
                  <tbody>
                    {data.children.slice(0, 12).map((c) => (
                      <tr key={c.id}>
                        <td class="name"><a href={hrefOf({ model: c.id })} onClick={(e) => { e.preventDefault(); navigate({ model: c.id }); }}>{c.id}</a></td>
                        <td class="muted">{c.relation}</td>
                        <td>{fmt(c.dl30)}</td>
                        <td>{fmt(c.dl_all)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
