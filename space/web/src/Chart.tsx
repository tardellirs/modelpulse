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
  /** draw the single series as outlined bars (one per timestamp) */
  bars?: boolean;
  /** hatch the last bar: the period isn't over yet */
  partialLast?: boolean;
  /** pin a value tag to the end of a single line */
  endLabel?: boolean;
  onZoom?: (r: [number, number] | null) => void;
  valueLabel?: (v: number) => string;
  tipDate?: (t: number) => string;
  /** days (timestamps at 00:00 UTC) to grey out behind the series, with a note for the tooltip */
  shade?: { days: number[]; note: string };
};

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function alpha(color: string, a: number) {
  if (color.startsWith("#")) {
    const n = parseInt(color.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  return color;
}

export function Chart({ lines, range, log, markers = [], height = 360, stacked, bars, partialLast, endLabel, onZoom, valueLabel, tipDate, shade }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const padRef = useRef(0);
  // uPlot reports scale changes asynchronously, so remember the last range we set ourselves and ignore its echo
  const lastSet = useRef<[number, number] | null>(null);
  const setX = (u: uPlot, min: number, max: number) => { lastSet.current = [min, max]; u.setScale("x", { min, max }); };

  useEffect(() => {
    const el = box.current!;
    if (!lines.length) return;
    const rule = css("--rule-2"), ink = css("--ink"), mark = css("--mark"), surface = css("--surface");
    const mono = css("--font-mono");
    const font = `12px ${mono}`;
    const axisInk = css("--ink-2");
    const dpr = devicePixelRatio;
    const asBars = !!bars && lines.length === 1 && !stacked;
    const cased = !stacked && !asBars; // lines get an ink casing drawn underneath

    let joined: uPlot.AlignedData;
    if (lines.length === 1) joined = [lines[0].t, lines[0].v] as uPlot.AlignedData;
    else joined = uPlot.join(lines.map((l) => [l.t, l.v] as uPlot.AlignedData));

    // stacked areas: accumulate series so each band sits on the previous one
    const raw = joined;
    let base = joined;
    if (stacked) {
      const acc = joined.slice() as (number | null)[][];
      for (let s = 2; s < acc.length; s++) acc[s] = acc[s].map((v, i) => (v ?? 0) + ((acc[s - 1][i] as number) ?? 0));
      base = acc as uPlot.AlignedData;
    }
    // with casing, every line becomes two series: [casing, colour]
    const data: uPlot.AlignedData = cased ? [base[0], ...base.slice(1).flatMap((col) => [col, col])] as uPlot.AlignedData : base;
    const seriesOf = (i: number) => (cased ? 2 + i * 2 : 1 + i); // index of line i's visible series in data

    const single = lines.length === 1;
    const seriesOpts: uPlot.Series[] = [{}];
    lines.forEach((l) => {
      const w = l.width ?? (single ? 3 : 2.5);
      if (asBars) {
        seriesOpts.push({
          label: l.label, stroke: ink, width: 2, fill: l.color,
          paths: uPlot.paths.bars!({ size: [0.74, 70, 3], radius: 0.18 }),
          points: { show: false },
        });
        return;
      }
      if (stacked) {
        seriesOpts.push({ label: l.label, stroke: ink, width: 1, fill: alpha(l.color, 0.92), spanGaps: true, points: { show: false } });
        return;
      }
      // casing: ink stroke a bit wider, carries the flat area fill so the coloured line sits on top of both
      seriesOpts.push({
        label: "", stroke: ink, width: w + 3, spanGaps: true, points: { show: false },
        fill: l.fill ? alpha(l.color, 0.14) : undefined,
      });
      seriesOpts.push({ label: l.label, stroke: l.color, width: w, dash: l.dash ? [5, 4] : undefined, spanGaps: true, points: { show: false } });
    });

    const drawHook = (u: uPlot) => {
      const { ctx } = u;
      ctx.save();
      // milestone markers
      for (const m of markers) {
        const x = Math.round(u.valToPos(m.t, "x", true));
        if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue;
        ctx.strokeStyle = ink;
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = 1.5 * dpr;
        ctx.setLineDash([4 * dpr, 4 * dpr]);
        ctx.beginPath(); ctx.moveTo(x, u.bbox.top); ctx.lineTo(x, u.bbox.top + u.bbox.height); ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.font = `600 ${11 * dpr}px ${mono}`;
        const w = ctx.measureText(m.label).width + 10 * dpr, h = 18 * dpr;
        ctx.fillStyle = mark;
        ctx.beginPath(); ctx.roundRect(x - w / 2, u.bbox.top - h + 4 * dpr, w, h, 6 * dpr); ctx.fill();
        ctx.lineWidth = 2 * dpr; ctx.stroke();
        ctx.fillStyle = ink; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(m.label, x, u.bbox.top - h / 2 + 4 * dpr);
      }
      const xs = u.data[0] as number[];
      const ys = u.data[seriesOf(0)] as (number | null)[];
      // the period of the last bar isn't over: hatch it
      if (asBars && partialLast && xs.length > 1) {
        const i = xs.length - 1, v = ys[i];
        if (v != null) {
          const x0 = u.valToPos(xs[i - 1], "x", true), x1 = u.valToPos(xs[i], "x", true);
          const bw = Math.min((x1 - x0) * 0.74, 70 * dpr);
          const top = u.valToPos(v, "y", true), bot = u.valToPos(0, "y", true);
          ctx.beginPath(); ctx.rect(x1 - bw / 2, top, bw, bot - top); ctx.clip();
          ctx.strokeStyle = surface; ctx.lineWidth = 3 * dpr;
          for (let k = -bot; k < bot; k += 8 * dpr) { ctx.beginPath(); ctx.moveTo(x1 - bw / 2 + k, bot); ctx.lineTo(x1 - bw / 2 + k + (bot - top), top); ctx.stroke(); }
        }
      }
      ctx.restore();
      // value tag at the end of a single line
      if (endLabel && single && !asBars && !stacked) {
        let i = ys.length - 1;
        while (i >= 0 && ys[i] == null) i--;
        if (i >= 0 && xs[i] >= u.scales.x.min! && xs[i] <= u.scales.x.max!) {
          const x = u.valToPos(xs[i], "x", true), y = u.valToPos(ys[i]!, "y", true);
          ctx.save();
          ctx.fillStyle = lines[0].color; ctx.strokeStyle = ink; ctx.lineWidth = 2.5 * dpr;
          ctx.beginPath(); ctx.arc(x, y, 6 * dpr, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          const text = valueLabel ? valueLabel(ys[i]!) : fmt(ys[i]!);
          ctx.font = `600 ${12 * dpr}px ${mono}`;
          const w = ctx.measureText(text).width + 14 * dpr, h = 22 * dpr;
          const tx = Math.max(u.bbox.left, x - w - 12 * dpr), ty = Math.max(u.bbox.top, y - h - 10 * dpr);
          ctx.fillStyle = surface;
          ctx.beginPath(); ctx.roundRect(tx, ty, w, h, 7 * dpr); ctx.fill(); ctx.lineWidth = 2 * dpr; ctx.stroke();
          ctx.fillStyle = ink; ctx.textAlign = "left"; ctx.textBaseline = "middle";
          ctx.fillText(text, tx + 7 * dpr, ty + h / 2 + 0.5 * dpr);
          ctx.restore();
        }
      }
    };

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height,
      padding: [22, 10, 0, 0],
      cursor: {
        drag: { x: true, y: false, setScale: true }, y: false,
        points: asBars || stacked ? { show: false } : {
          size: (_u: uPlot, si: number) => (cased && si % 2 === 1 ? 0 : 12), width: 2.5,
          stroke: (_u: uPlot, si: number) => (cased && si % 2 === 1 ? "transparent" : ink),
          fill: (_u: uPlot, si: number) => (cased && si % 2 === 1 ? "transparent" : (seriesOpts[si].stroke as string)),
        } as any,
      },
      legend: { show: false },
      scales: { x: { time: true }, y: { distr: log ? 3 : 1, range: (_u, mn, mx) => [log ? Math.max(1, mn) : 0, mx * 1.1 || 1] } },
      axes: [
        {
          stroke: axisInk, font, grid: { show: false }, ticks: { show: true, stroke: ink, width: 2, size: 5 }, gap: 6,
          border: { show: true, stroke: ink, width: 2 },
          values: [
            [86400 * 365, "{YYYY}", null, null, null, null, null, null, 1],
            [86400 * 28, "{MMM}", "\n{YYYY}", null, null, null, null, null, 1],
            [86400, "{MMM} {D}", "\n{YYYY}", null, "{D}", null, "{MMM} {D}", null, 1],
          ] as any,
        },
        {
          stroke: axisInk, font, size: 60, gap: 8,
          grid: { stroke: rule, width: 1.5, dash: [4, 5] }, ticks: { show: false },
          values: (_u, vals) => vals.map((v) => (v == null ? "" : fmt(v))),
        },
      ],
      series: seriesOpts,
      bands: stacked ? lines.slice(1).map((_, i) => ({ series: [i + 2, i + 1] as [number, number] })) : undefined,
      hooks: {
        drawClear: [(u: uPlot) => {
          if (!shade?.days.length) return;
          const { ctx } = u;
          ctx.save();
          ctx.fillStyle = alpha(css("--ink") || "#1b1b1f", 0.09);
          for (const d of shade.days) {
            const x0 = u.valToPos(d - 43200, "x", true), x1 = u.valToPos(d + 43200, "x", true);
            if (x1 < u.bbox.left || x0 > u.bbox.left + u.bbox.width) continue;
            ctx.fillRect(x0, u.bbox.top, Math.max(x1 - x0, 2 * dpr), u.bbox.height);
          }
          ctx.restore();
        }],
        draw: [drawHook],
        setCursor: [
          (u) => {
            const t = tip.current!;
            const idx = u.cursor.idx;
            if (idx == null || u.cursor.left == null || u.cursor.left < 0) { t.style.display = "none"; return; }
            const rows = lines.map((l, i) => ({ l, i, v: (raw[i + 1] as (number | null)[])[idx] })).filter((r) => r.v != null);
            if (!rows.length) { t.style.display = "none"; return; }
            const ts = data[0][idx] as number;
            const day = tipDate ? tipDate(ts) : fmtDate(new Date(ts * 1000), { weekday: "short", month: "short", day: "numeric", year: "numeric" });
            const low = shade?.days.includes(ts) ? `<div class="d">${escapeHtml(shade.note)}</div>` : "";
            t.innerHTML = `<div class="d">${day}</div>` + low + rows.map((r) =>
              `<div class="r"><span><i class="sw" style="background:${r.l.color}"></i>${lines.length > 1 ? escapeHtml(r.l.label) : ""}</span><b>${valueLabel ? valueLabel(r.v as number) : fmtFull(r.v)}</b></div>`).join("");
            t.style.display = "block";
            const x = u.cursor.left + u.bbox.left / dpr;
            const top = Math.min(...rows.map((r) => u.valToPos((data[seriesOf(r.i)] as number[])[idx], "y"))) + u.bbox.top / dpr;
            const half = t.offsetWidth / 2;
            t.style.left = Math.min(Math.max(x, half), el.clientWidth - half) + "px";
            t.style.top = Math.max(top - 14, t.offsetHeight) + "px";
          },
        ],
        setScale: [
          (u, key) => {
            if (key !== "x" || !onZoom) return;
            const ls = lastSet.current, mn = u.scales.x.min!, mx = u.scales.x.max!;
            if (ls && Math.abs(ls[0] - mn) < 1 && Math.abs(ls[1] - mx) < 1) return;
            onZoom([mn + padRef.current, mx - padRef.current]);
          },
        ],
      },
    };

    const u = new uPlot(opts, data, el);
    plot.current = u;
    padRef.current = asBars && data[0].length > 1 ? ((data[0][1] as number) - (data[0][0] as number)) / 2 : 0;
    const p = padRef.current;
    if (range) setX(u, range[0] - p, range[1] + p);
    else if (p) setX(u, (data[0][0] as number) - p, (data[0][data[0].length - 1] as number) + p);
    const ro = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height }));
    ro.observe(el);
    const leave = () => (tip.current!.style.display = "none");
    el.addEventListener("mouseleave", leave);
    return () => { ro.disconnect(); el.removeEventListener("mouseleave", leave); u.destroy(); plot.current = null; };
  }, [lines, log, markers, height, stacked, bars, partialLast, endLabel, shade]);

  useEffect(() => {
    const u = plot.current;
    if (!u) return;
    const t = u.data[0] as number[];
    const p = padRef.current;
    if (range) setX(u, range[0] - p, range[1] + p);
    else setX(u, t[0] - p, t[t.length - 1] + p);
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

export function Sparkline({ v, w = 96, h = 28, color = "var(--signal)" }: { v: number[]; w?: number; h?: number; color?: string }) {
  if (!v || v.length < 2) return <svg width={w} height={h} />;
  const mx = Math.max(...v) || 1;
  const pts = v.map((y, i) => `${((i / (v.length - 1)) * (w - 6) + 3).toFixed(1)},${(h - 4 - (y / mx) * (h - 8)).toFixed(1)}`);
  const last = pts[pts.length - 1].split(",");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" style={{ display: "block", overflow: "visible" }}>
      <path d={`M${pts.join(" L")} L${w - 3},${h} L3,${h}Z`} fill={color} opacity="0.16" />
      <path d={`M${pts.join(" L")}`} fill="none" stroke="var(--ink)" stroke-width="4" stroke-linejoin="round" stroke-linecap="round" />
      <path d={`M${pts.join(" L")}`} fill="none" stroke={color} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <circle cx={last[0]} cy={last[1]} r="3.5" fill={color} stroke="var(--ink)" stroke-width="2" />
    </svg>
  );
}
