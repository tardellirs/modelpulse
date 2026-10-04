import { useEffect, useMemo, useState } from "preact/hooks";
import {
  API_BASE, SPACE_URL, api, daily, fmt, fmtDate, fmtFull, fmtPct, hrefOf, navigate, ord, plain, shareUrl, smooth, taskLabel, weekly, WEEK,
  type DatasetResponse, type Route, type SpaceResponse,
} from "./api";
import { Chart, type Line } from "./Chart";
import { LikeCta } from "./Like";
import { BADGE_HOST, Copy } from "./Share";
import { UsedBy } from "./UsedBy";

type RangeKey = "3M" | "6M" | "1Y" | "All";
const RANGES: Record<RangeKey, number | null> = { "3M": 91, "6M": 182, "1Y": 365, All: null };
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const Heart = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="#ff6b81" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2.1 0 3.6 1.1 5.4 3 1.8-1.9 3.3-3 5.4-3 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z" /></svg>
);

function useRange(lines: Line[], key: RangeKey, zoom: [number, number] | null) {
  return useMemo((): [number, number] | null => {
    if (zoom) return zoom;
    const days = RANGES[key];
    if (!days || !lines.length || !lines[0].t.length) return null;
    const last = lines[0].t[lines[0].t.length - 1];
    return [last - days * 86400, last];
  }, [lines, key, zoom]);
}

function RangeSeg({ value, onChange }: { value: RangeKey; onChange: (k: RangeKey) => void }) {
  return (
    <div class="seg" role="group" aria-label="Time range">
      {(Object.keys(RANGES) as RangeKey[]).map((k) => <button key={k} aria-pressed={value === k} onClick={() => onChange(k)}>{k}</button>)}
    </div>
  );
}

function ShareRow({ route, text }: { route: Route; text: string }) {
  const url = shareUrl(route);
  return (
    <section class="section">
      <div class="wrap w-actions g-actions">
        <a class="btn" target="_blank" rel="noopener" href={`https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`}>Post on X</a>
        <a class="btn" target="_blank" rel="noopener" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}>LinkedIn</a>
        <button class="btn" onClick={() => navigator.clipboard?.writeText(url)}>Copy link</button>
        <LikeCta />
      </div>
    </section>
  );
}

function Loading({ id }: { id: string }) {
  return <div class="wrap hero"><div class="crumbs" style={{ visibility: "hidden" }}><span class="chip">loading</span></div><h1 class="model-name">{id}</h1><div class="skeleton" style={{ marginTop: 24 }} /></div>;
}

function NotFound({ id, err }: { id: string; err: string }) {
  return <div class="wrap err"><h1>No history for {id}</h1><p class="muted">{err}</p></div>;
}

function Name({ id }: { id: string }) {
  const [org, name] = id.includes("/") ? [id.split("/")[0], id.split("/").slice(1).join("/")] : [null, id];
  return (
    <h1 class="model-name">
      {org && <a href={hrefOf({ author: org })} onClick={(e) => { e.preventDefault(); navigate({ author: org }); }} class="org">{org}/</a>}
      <span class="hl">{name}</span>
    </h1>
  );
}

/** The README badge for a dataset card, like the one for models. */
function DatasetBadge({ id }: { id: string }) {
  const [metric, setMetric] = useState<"month" | "all" | "likes">("month");
  const badge = `${BADGE_HOST}/badge/dataset/${id}.svg${metric === "month" ? "" : `?metric=${metric}`}`;
  const md = `[![Model Pulse](${badge})](${SPACE_URL}?dataset=${id})`;
  return (
    <section class="section">
      <div class="wrap">
        <div class="card ds-badge">
          <h3>Badge for your dataset card</h3>
          <p>Updates daily. Paste it into the README of {id.split("/").pop()}.</p>
          <div class="seg badge-opts" role="group" aria-label="Badge metric">
            <button aria-pressed={metric === "month"} onClick={() => setMetric("month")}>Monthly</button>
            <button aria-pressed={metric === "all"} onClick={() => setMetric("all")}>All time</button>
            <button aria-pressed={metric === "likes"} onClick={() => setMetric("likes")}>Likes</button>
          </div>
          <div class="badge-preview"><img src={badge.replace(BADGE_HOST, API_BASE)} alt="Model Pulse badge preview" height={22} /></div>
          <div class="code"><code>{md}</code><Copy text={md} label="Copy markdown" /></div>
        </div>
      </div>
    </section>
  );
}

// ---------- datasets ----------

type DMetric = "weekly" | "daily" | "month" | "total" | "likes";

export function DatasetPage({ id }: { id: string }) {
  const [d, setD] = useState<DatasetResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetricRaw] = useState<DMetric>("weekly");
  const [rangeKey, setRangeKey] = useState<RangeKey>("1Y");
  const [zoom, setZoom] = useState<[number, number] | null>(null);
  const setMetric = (m: DMetric) => { setZoom(null); setMetricRaw(m); };

  useEffect(() => {
    setD(null); setErr(null);
    api.dataset(id).then((r) => {
      setD(r);
      if (r.dataset.id !== id) navigate({ dataset: r.dataset.id }, true);
      document.title = `${r.dataset.id} downloads: daily history and stats · Model Pulse`;
    }).catch((e) => setErr(e.message));
  }, [id]);

  const hasDaily = !!d && d.series.dl_all.filter((x) => x != null).length > 7;
  const eff: DMetric = (metric === "weekly" || metric === "daily") && !hasDaily ? "month" : metric;
  const lines: Line[] = useMemo(() => {
    if (!d) return [];
    const s = d.series, c = css("--c1");
    if (eff === "weekly") { const x = daily(s.day, s.dl_all), w = weekly(x.t, x.v); return [{ label: d.dataset.id, color: c, t: w.t, v: w.v, fill: true }]; }
    if (eff === "daily") { const x = daily(s.day, s.dl_all); return [{ label: d.dataset.id, color: c, t: x.t, v: smooth(x.v, 7), fill: true }]; }
    const x = plain(s.day, eff === "month" ? s.dl30 : eff === "total" ? s.dl_all : s.likes);
    return [{ label: d.dataset.id, color: c, t: x.t, v: x.v, fill: true }];
  }, [d, eff]);
  const partial = useMemo(() => (d && eff === "weekly" ? (weekly(daily(d.series.day, d.series.dl_all).t, daily(d.series.day, d.series.dl_all).v) as { partial?: boolean }).partial : false), [d, eff]);
  const range = useRange(lines, rangeKey, zoom);

  if (err) return <NotFound id={id} err={err} />;
  if (!d) return <Loading id={id} />;
  const x = d.dataset, name = x.id.split("/").pop();

  return (
    <>
      <div class="wrap hero">
        <div class="crumbs">
          <span class="chip chip-kind">Dataset</span>
          {x.pipeline_tag && <span class="chip">{taskLabel(x.pipeline_tag)}</span>}
          {x.size && <span class="chip">{x.size} rows</span>}
          {x.license && <span class="chip">{x.license}</span>}
          {x.likes != null && <span class="chip"><Heart />{fmtFull(x.likes)} likes{x.likes_7d ? <span class="up">+{fmtFull(x.likes_7d)}</span> : null}</span>}
          <a class="chip" href={`https://huggingface.co/datasets/${x.id}`} target="_blank" rel="noopener">Open on Hugging Face ↗</a>
        </div>
        <Name id={x.id} />
        <div class="card stats" style={{ padding: 0 }}>
          <div class="fig fig-main"><div class="num">{fmtFull(x.dl_all ?? x.dl30)}</div><div class="label">{x.dl_all != null ? "downloads all time" : "downloads in the last 30 days"}</div></div>
          <div class="fig"><div class="val">{fmt(x.dl30)}</div><div class="label">last 30 days</div></div>
          <div class="fig">
            <div class="val">{fmt(x.dl_7d)}{x.growth_7d != null && <small class={x.growth_7d >= 0 ? "up" : "down"}>{fmtPct(x.growth_7d)}</small>}</div>
            <div class="label">last 7 days{x.growth_7d != null ? ", vs. 3-week average" : ""}</div>
          </div>
          <div class="fig"><div class="val">#{fmtFull(x.rank_dl30)}</div><div class="label">among datasets{x.rank_task && x.pipeline_tag ? `, ${ord(x.rank_task)} in ${taskLabel(x.pipeline_tag)}` : ""}</div></div>
        </div>
        <div class="card chart-card">
          <div class="chart-bar">
            <div class="left">
              <div class="seg" role="group" aria-label="Metric">
                {hasDaily && <button aria-pressed={eff === "weekly"} onClick={() => setMetric("weekly")}>Weekly</button>}
                {hasDaily && <button aria-pressed={eff === "daily"} onClick={() => setMetric("daily")}>Daily</button>}
                <button aria-pressed={eff === "month"} onClick={() => setMetric("month")}>Rolling 30 days</button>
                {hasDaily && <button aria-pressed={eff === "total"} onClick={() => setMetric("total")}>All time</button>}
                <button aria-pressed={eff === "likes"} onClick={() => setMetric("likes")}>Likes</button>
              </div>
              <RangeSeg value={rangeKey} onChange={(k) => { setZoom(null); setRangeKey(k); }} />
            </div>
          </div>
          <Chart lines={lines} range={range} onZoom={setZoom} height={360} bars={eff === "weekly"} partialLast={eff === "weekly" && !!partial} endLabel={eff !== "weekly"}
            tipDate={eff === "weekly" ? (t) => `Week of ${fmtDate(new Date((t - WEEK / 2) * 1000), { month: "short", day: "numeric", year: "numeric" })}` : undefined}
            valueLabel={eff === "daily" ? (v) => fmtFull(v) + "/day" : eff === "weekly" ? (v) => fmtFull(v) + "/week" : undefined} />
          <p class="chart-note">
            {eff === "weekly" && "Downloads per week, Monday to Sunday; the striped bar is the week in progress. "}
            {eff === "daily" && "7-day average of daily downloads. "}
            Dataset downloads follow the Hub's counting rules. Drag on the chart to zoom, double-click to reset.
          </p>
        </div>
      </div>

      {(d.models.count > 0 || d.spaces.count > 0) && (
        <section class="section">
          <div class="wrap">
            <div class="section-head"><div><h2>Who uses {name}</h2><p>Models whose card lists {name} as training data, and Spaces whose card lists it.</p></div></div>
            <div class="ub-grid">
              <UsedBy title="Models trained on it" data={d.models} by="model" note="Counted from today's model cards, by the month each model was created." />
              <UsedBy title="Spaces using it" data={d.spaces} by="space" note="Counted from today's Space cards, by the month each Space was created." />
            </div>
          </div>
        </section>
      )}

      <section class="section">
        <div class="wrap about">
          <h2>About {name}</h2>
          <p>
            <b>{x.id}</b> is a{/^[aeio]/i.test(x.pipeline_tag ?? "") ? "n" : ""} {x.pipeline_tag ? `${taskLabel(x.pipeline_tag)} ` : ""}dataset on the Hugging Face Hub.
            {" "}In the last 30 days it was downloaded <b>{fmtFull(x.dl30)}</b> times{x.dl_all ? <>, and <b>{fmtFull(x.dl_all)}</b> times in total</> : null}.
            {x.rank_dl30 ? ` It ranks #${fmtFull(x.rank_dl30)} among datasets by monthly downloads.` : ""}
            {x.used_by_models ? ` ${fmtFull(x.used_by_models)} models list it as training data` : ""}
            {x.used_by_models && x.used_by_spaces ? `, and ${fmtFull(x.used_by_spaces)} Spaces use it.` : x.used_by_models ? "." : x.used_by_spaces ? ` ${fmtFull(x.used_by_spaces)} Spaces use it.` : ""}
          </p>
          {x.description && <p class="muted">{x.description}{x.description.length >= 300 ? "…" : ""}</p>}
        </div>
      </section>
      <DatasetBadge id={x.id} />
      <ShareRow route={{ dataset: x.id }} text={`${x.id} has ${fmt(x.dl_all ?? x.dl30)} downloads on Hugging Face. Full download history:`} />
    </>
  );
}

// ---------- Spaces ----------

type SMetric = "weekly" | "total";

export function SpacePage({ id }: { id: string }) {
  const [d, setD] = useState<SpaceResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetric] = useState<SMetric>("weekly");
  const [rangeKey, setRangeKey] = useState<RangeKey>("1Y");
  const [zoom, setZoom] = useState<[number, number] | null>(null);

  useEffect(() => {
    setD(null); setErr(null);
    api.space(id).then((r) => {
      setD(r);
      if (r.space.id !== id) navigate({ space: r.space.id }, true);
      document.title = `${r.space.title || r.space.id}: likes over time · Model Pulse`;
    }).catch((e) => setErr(e.message));
  }, [id]);

  const lines: Line[] = useMemo(() => {
    if (!d) return [];
    const c = css("--c3");
    if (metric === "total") { const x = plain(d.series.day, d.series.likes); return [{ label: d.space.id, color: c, t: x.t, v: x.v, fill: true }]; }
    const x = daily(d.series.day, d.series.likes), w = weekly(x.t, x.v);
    return [{ label: d.space.id, color: c, t: w.t, v: w.v, fill: true }];
  }, [d, metric]);
  const range = useRange(lines, rangeKey, zoom);

  if (err) return <NotFound id={id} err={err} />;
  if (!d) return <Loading id={id} />;
  const s = d.space;
  const uses = [...d.uses.models.map((u) => ({ ...u, kind: "model" as const })), ...d.uses.datasets.map((u) => ({ ...u, kind: "dataset" as const }))];

  return (
    <>
      <div class="wrap hero">
        <div class="crumbs">
          <span class="chip chip-kind">Space</span>
          {s.sdk && <span class="chip">{s.sdk}</span>}
          {s.created_at && <span class="chip">since {fmtDate(s.created_at, { month: "short", year: "numeric" })}</span>}
          <a class="chip" href={`https://huggingface.co/spaces/${s.id}`} target="_blank" rel="noopener">Open on Hugging Face ↗</a>
        </div>
        <h1 class="model-name sp-title">
          {s.emoji && <span class="emo" aria-hidden="true">{s.emoji}</span>}
          <span class="hl">{s.title || s.id.split("/").pop()}</span>
        </h1>
        <p class="sp-id">
          <a href={hrefOf({ author: s.id.split("/")[0] })} onClick={(e) => { e.preventDefault(); navigate({ author: s.id.split("/")[0] }); }}>{s.id.split("/")[0]}</a>/{s.id.split("/").slice(1).join("/")}
          {s.short_description ? <> · {s.short_description}</> : null}
        </p>
        <div class="card stats" style={{ padding: 0 }}>
          <div class="fig fig-main"><div class="num">{fmtFull(s.likes)}</div><div class="label">likes</div></div>
          <div class="fig"><div class="val">+{fmtFull(s.likes_7d)}</div><div class="label">last 7 days</div></div>
          <div class="fig"><div class="val">+{fmtFull(s.likes_30d)}</div><div class="label">last 30 days</div></div>
          <div class="fig"><div class="val">#{fmtFull(s.rank_likes)}</div><div class="label">among Spaces by likes</div></div>
        </div>
        <div class="card chart-card">
          <div class="chart-bar">
            <div class="left">
              <div class="seg" role="group" aria-label="Metric">
                <button aria-pressed={metric === "weekly"} onClick={() => { setZoom(null); setMetric("weekly"); }}>Likes per week</button>
                <button aria-pressed={metric === "total"} onClick={() => { setZoom(null); setMetric("total"); }}>Total likes</button>
              </div>
              <RangeSeg value={rangeKey} onChange={(k) => { setZoom(null); setRangeKey(k); }} />
            </div>
          </div>
          <Chart lines={lines} range={range} onZoom={setZoom} height={340} bars={metric === "weekly"} endLabel={metric !== "weekly"}
            tipDate={metric === "weekly" ? (t) => `Week of ${fmtDate(new Date((t - WEEK / 2) * 1000), { month: "short", day: "numeric", year: "numeric" })}` : undefined}
            valueLabel={metric === "weekly" ? (v) => `+${fmtFull(v)} likes` : (v) => `${fmtFull(v)} likes`} />
          <p class="chart-note">The Hub doesn't publish visits or usage for Spaces, so likes are the measure here. Drag on the chart to zoom, double-click to reset.</p>
        </div>
      </div>

      {uses.length > 0 && (
        <section class="section">
          <div class="wrap">
            <div class="section-head"><div><h2>What it uses</h2><p>Models and datasets listed in this Space's card, by downloads in the last 30 days.</p></div></div>
            <div class="card">
              <ol class="ub-list">
                {uses.map((u) => {
                  const route = u.kind === "model" ? { model: u.id } : { dataset: u.id };
                  return (
                    <li key={`${u.kind}:${u.id}`}>
                      <a href={hrefOf(route)} onClick={(e) => { e.preventDefault(); navigate(route); }}>
                        <span class={`kind k-${u.kind}`}>{u.kind}</span>
                        <span class="nm">{u.id}</span>
                        <span class="v">{u.dl30 != null ? `${fmt(u.dl30)}/mo` : "not tracked"}</span>
                      </a>
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        </section>
      )}

      <section class="section">
        <div class="wrap about">
          <h2>About {s.title || s.id}</h2>
          <p>
            <b>{s.id}</b> is a{s.sdk && /^[aeio]/i.test(s.sdk) ? "n" : ""} {s.sdk ? `${s.sdk} ` : ""}Space on the Hugging Face Hub{s.created_at ? `, created in ${fmtDate(s.created_at, { month: "long", year: "numeric" })}` : ""}.
            {" "}It has <b>{fmtFull(s.likes)}</b> likes, {fmtFull(s.likes_7d)} of them in the last 7 days and {fmtFull(s.likes_30d)} in the last 30, and ranks #{fmtFull(s.rank_likes)} among Spaces by likes.
            {uses.length ? ` Its card lists ${fmtFull(d.uses.models.length)} model${d.uses.models.length === 1 ? "" : "s"} and ${fmtFull(d.uses.datasets.length)} dataset${d.uses.datasets.length === 1 ? "" : "s"}.` : ""}
          </p>
        </div>
      </section>
      <ShareRow route={{ space: s.id }} text={`${s.title || s.id} has ${fmt(s.likes)} likes on Hugging Face. Likes over time:`} />
    </>
  );
}
