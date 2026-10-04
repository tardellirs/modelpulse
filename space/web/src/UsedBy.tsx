import { useMemo } from "preact/hooks";
import { fmt, fmtFull, hrefOf, navigate, taskLabel, ts, type UsedBy as UsedByData } from "./api";
import { Chart, type Line } from "./Chart";

const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/**
 * Who uses a model or dataset: how many Spaces (or models) list it in their card today, how that count built up by
 * the month each of them was created, and the biggest of them.
 */
export function UsedBy({ title, data, by, note }: { title: string; data: UsedByData; by: "space" | "model"; note: string }) {
  const line: Line[] = useMemo(() => {
    let total = 0;
    const t: number[] = [], v: number[] = [];
    data.months.month.forEach((m, i) => { total += data.months.n[i]; t.push(ts(`${m}-15`)); v.push(total); });
    return t.length ? [{ label: title, color: css(by === "space" ? "--c3" : "--c2"), t, v, fill: true }] : [];
  }, [data]);
  if (!data.count) return null;
  return (
    <div class="card used-by">
      <div class="ub-head">
        <h3>{title}</h3>
        <div class="ub-n"><b>{fmtFull(data.count)}</b> {by === "space" ? (data.count === 1 ? "Space" : "Spaces") : data.count === 1 ? "model" : "models"}</div>
      </div>
      {line.length > 0 && line[0].t.length > 1 && <Chart lines={line} height={150} endLabel valueLabel={(v) => fmtFull(v)} />}
      <ol class="ub-list">
        {data.top.map((r) => {
          const route = by === "space" ? { space: r.id } : { model: r.id };
          return (
            <li key={r.id}>
              <a href={hrefOf(route)} onClick={(e) => { e.preventDefault(); navigate(route); }}>
                {by === "space" && <span class="emo" aria-hidden="true">{r.emoji || "·"}</span>}
                <span class="nm">{by === "space" && r.title ? <>{r.title} <small>{r.id}</small></> : r.id}</span>
                <span class="v">{by === "space" ? `${fmt(r.likes)} ${r.likes === 1 ? "like" : "likes"}` : `${fmt(r.dl30)}/mo`}</span>
              </a>
              {by === "model" && r.pipeline_tag && <span class="ub-sub">{taskLabel(r.pipeline_tag)}</span>}
            </li>
          );
        })}
      </ol>
      <p class="chart-note">{note}</p>
    </div>
  );
}
