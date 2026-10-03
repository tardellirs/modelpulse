import { useEffect, useRef } from "preact/hooks";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { fmt, fmtDate, fmtFull } from "./api";

export type Line = { label: string; color: string; t: number[]; v: (number | null)[]; fill?: boolean; dash?: boolean; width?: number };
export type Marker = { t: number; label: string };

type Props = {
  lines: Line[];
  range?: [number, number] | null;
  log?: boolean;
  markers?: Marker[];
  height?: number;
  stacked?: boolean;
  onZoom?: (r: [number, number] | null) => void;
  valueLabel?: (v: number) => string;
};

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function alpha(color: string, a: number) {
  if (color.startsWith("#")) {
    const n = parseInt(color.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  return color;
}

export function Chart({ lines, range, log, markers = [], height = 360, stacked, onZoom, valueLabel }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);

  useEffect(() => {
    const el = box.current!;
    if (!lines.length) return;
    const muted = css("--muted"), rule = css("--rule-2"), ink = css("--ink"), mark = css("--mark");
    const font = `12px ${css("--font")}`;

    let data: uPlot.AlignedData;
    if (lines.length === 1) data = [lines[0].t, lines[0].v] as uPlot.AlignedData;
    else data = uPlot.join(lines.map((l) => [l.t, l.v] as uPlot.AlignedData));

    // stacked areas: accumulate series so each band sits on the previous one
    let raw = data;
    if (stacked) {
      const acc = data.slice() as (number | null)[][];
      for (let s = 2; s < acc.length; s++) acc[s] = acc[s].map((v, i) => (v ?? 0) + ((acc[s - 1][i] as number) ?? 0));
      raw = data;
      data = acc as uPlot.AlignedData;
    }

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height,
      padding: [18, 8, 0, 0],
      cursor: { drag: { x: true, y: false, setScale: true }, points: { size: 8, width: 2 }, y: false },
      legend: { show: false },
      scales: { x: { time: true }, y: { distr: log ? 3 : 1, range: (u, mn, mx) => [log ? Math.max(1, mn) : 0, mx * 1.08 || 1] } },
      axes: [
        {
          stroke: muted, font, grid: { show: false }, ticks: { show: true, stroke: rule, size: 4 }, gap: 6,
          values: [
            [86400 * 365, "{YYYY}", null, null, null, null, null, null, 1],
            [86400 * 28, "{MMM}", "\n{YYYY}", null, null, null, null, null, 1],
            [86400, "{MMM} {D}", "\n{YYYY}", null, "{D}", null, "{MMM} {D}", null, 1],
          ] as any,
        },
        {
          stroke: muted, font, size: 56, gap: 8,
          grid: { stroke: rule, width: 1 }, ticks: { show: false },
          values: (_u, vals) => vals.map((v) => (v == null ? "" : fmt(v))),
        },
      ],
      series: [
        {},
        ...lines.map((l, i) => ({
          label: l.label,
          stroke: l.color,
          width: l.width ?? (lines.length === 1 ? 2.25 : 2),
          dash: l.dash ? [5, 4] : undefined,
          spanGaps: true,
          points: { show: false },
          fill: stacked
            ? alpha(l.color, 0.85)
            : l.fill
              ? (u: uPlot) => {
                  const g = u.ctx.createLinearGradient(0, u.bbox.top, 0, u.bbox.top + u.bbox.height);
                  g.addColorStop(0, alpha(l.color, 0.26));
                  g.addColorStop(1, alpha(l.color, 0));
                  return g;
                }
              : undefined,
          ...(stacked && i > 0 ? {} : {}),
        })),
      ],
      bands: stacked ? lines.slice(1).map((_, i) => ({ series: [i + 2, i + 1] as [number, number] })) : undefined,
      hooks: {
        draw: [
          (u) => {
            if (!markers.length) return;
            const { ctx } = u;
            ctx.save();
            for (const m of markers) {
              const x = Math.round(u.valToPos(m.t, "x", true));
              if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue;
              ctx.strokeStyle = mark;
              ctx.lineWidth = 2 * devicePixelRatio;
              ctx.setLineDash([3 * devicePixelRatio, 3 * devicePixelRatio]);
              ctx.beginPath();
              ctx.moveTo(x, u.bbox.top);
              ctx.lineTo(x, u.bbox.top + u.bbox.height);
              ctx.stroke();
              ctx.setLineDash([]);
              ctx.font = `600 ${11 * devicePixelRatio}px ${css("--font")}`;
              const w = ctx.measureText(m.label).width + 10 * devicePixelRatio;
              const h = 18 * devicePixelRatio;
              ctx.fillStyle = mark;
              ctx.beginPath();
              ctx.roundRect(x - w / 2, u.bbox.top - h + 4 * devicePixelRatio, w, h, 4 * devicePixelRatio);
              ctx.fill();
              ctx.fillStyle = "#151833";
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText(m.label, x, u.bbox.top - h / 2 + 4 * devicePixelRatio);
            }
            ctx.restore();
          },
        ],
        setCursor: [
          (u) => {
            const t = tip.current!;
            const idx = u.cursor.idx;
            if (idx == null || u.cursor.left == null || u.cursor.left < 0) { t.style.display = "none"; return; }
            const rows = lines
              .map((l, i) => ({ l, v: (raw[i + 1] as (number | null)[])[idx] }))
              .filter((r) => r.v != null);
            if (!rows.length) { t.style.display = "none"; return; }
            const day = fmtDate(new Date((data[0][idx] as number) * 1000), { weekday: "short", month: "short", day: "numeric", year: "numeric" });
            t.innerHTML =
              `<div class="d">${day}</div>` +
              rows
                .map((r) => `<div class="r"><span><i class="sw" style="background:${r.l.color}"></i>${lines.length > 1 ? escapeHtml(r.l.label) : valueLabel ? "" : "Value"}</span><b>${valueLabel ? valueLabel(r.v as number) : fmtFull(r.v)}</b></div>`)
                .join("");
            t.style.display = "block";
            const x = u.cursor.left + u.bbox.left / devicePixelRatio;
            const top = Math.min(...rows.map((r, k) => u.valToPos((stacked ? (data[lines.indexOf(r.l) + 1] as number[])[idx] : r.v) as number, "y"))) + u.bbox.top / devicePixelRatio;
            const half = t.offsetWidth / 2;
            t.style.left = Math.min(Math.max(x, half), el.clientWidth - half) + "px";
            t.style.top = Math.max(top - 12, t.offsetHeight) + "px";
          },
        ],
        setSelect: [],
        setScale: [
          (u, key) => {
            if (key !== "x" || !onZoom) return;
            const mn = u.scales.x.min!, mx = u.scales.x.max!;
            onZoom([mn, mx]);
          },
        ],
      },
    };

    const u = new uPlot(opts, data, el);
    plot.current = u;
    if (range) u.setScale("x", { min: range[0], max: range[1] });
    const ro = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height }));
    ro.observe(el);
    const leave = () => (tip.current!.style.display = "none");
    el.addEventListener("mouseleave", leave);
    return () => { ro.disconnect(); el.removeEventListener("mouseleave", leave); u.destroy(); plot.current = null; };
  }, [lines, log, markers, height, stacked]);

  useEffect(() => {
    const u = plot.current;
    if (!u) return;
    const t = u.data[0] as number[];
    if (range) u.setScale("x", { min: range[0], max: range[1] });
    else u.setScale("x", { min: t[0], max: t[t.length - 1] });
  }, [range]);

  return (
    <div class="chart-box">
      <div ref={box} onDblClick={() => onZoom?.(null)} />
      <div ref={tip} class="tip" style={{ display: "none" }} />
    </div>
  );
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function Sparkline({ v, w = 96, h = 26, color = "var(--signal)" }: { v: number[]; w?: number; h?: number; color?: string }) {
  if (!v || v.length < 2) return <svg width={w} height={h} />;
  const mx = Math.max(...v) || 1;
  const pts = v.map((y, i) => `${((i / (v.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 2 - (y / mx) * (h - 4)).toFixed(1)}`);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" style={{ display: "block" }}>
      <path d={`M${pts.join(" L")} L${w - 1},${h} L1,${h}Z`} fill={color} opacity="0.12" />
      <path d={`M${pts.join(" L")}`} fill="none" stroke={color} stroke-width="1.5" stroke-linejoin="round" />
    </svg>
  );
}
