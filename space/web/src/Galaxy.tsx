import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { fmt, fmtFull, get, navigate, shareUrl } from "./api";
import { LikeCta } from "./Like";
import { Logo } from "./Logo";
import { Search } from "./Search";

type GalaxyData = {
  root: { id: string; author: string; pipeline_tag: string | null; dl30: number | null; dl_all: number | null; fam_members: number | null; fam_dl30: number | null; fam_all: number | null };
  relations: string[];
  lineage: string[];
  total: number;
  nodes: { id: string[]; parent: number[]; rel: number[]; dl30: number[] };
};

/** Same order as the API's relation codes, and the same hues as the Family bar on model pages. */
const REL = [
  { label: "Quantized", color: "#7d9dff", of: "Quantized from" },
  { label: "Fine-tuned", color: "#ff9d4a", of: "Fine-tuned from" },
  { label: "Adapters", color: "#4ccb8a", of: "Adapter on" },
  { label: "Merges", color: "#c38dff", of: "Merge built on" },
];
const SKY = "#16161a", SUN = "#ffd21e", STAR_TEXT = "#ece9e2";
const R = 1000; // galaxy radius in world units
const TAU = Math.PI * 2, GOLD = Math.PI * (3 - Math.sqrt(5));
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// deterministic noise, so a galaxy always looks the same
function hash(i: number, s: number) {
  let h = Math.imul(i ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(s + 1, 0xc2b2ae35);
  h ^= h >>> 13; h = Math.imul(h, 0x27d4eb2f); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
const gauss = (i: number, s: number) => (hash(i, s) + hash(i, s + 11) + hash(i, s + 23) - 1.5) * 2;
const short = (id: string) => id.split("/").pop() ?? id;

type Layout = {
  n: number; x: Float32Array; y: Float32Array; size: Float32Array; delay: Float32Array;
  sub: Int32Array; byRel: Int32Array[]; order: Int32Array; extent: number;
  cell: number; grid: Map<number, number[]>;
};

/**
 * Direct derivatives form the spiral arms, one colour per kind of derivative; the most used sit nearest the core.
 * Everything built on a derivative orbits it as a small sunflower cluster.
 */
function layout(g: GalaxyData): Layout {
  const { parent, rel, dl30 } = g.nodes;
  const n = parent.length;
  const depth = new Uint8Array(n), sub = new Int32Array(n).fill(1), subDl = new Float64Array(n);
  const start = new Int32Array(n + 1);
  for (let i = 1; i < n; i++) { depth[i] = depth[parent[i]] + 1; start[parent[i] + 1]++; }
  for (let i = 0; i < n; i++) start[i + 1] += start[i];
  const fill = start.slice(0, n), kids = new Int32Array(Math.max(0, n - 1));
  for (let i = 1; i < n; i++) kids[fill[parent[i]]++] = i; // the API lists each level biggest first
  for (let i = 0; i < n; i++) subDl[i] = dl30[i] || 0;
  for (let i = n - 1; i > 0; i--) { sub[parent[i]] += sub[i]; subDl[parent[i]] += subDl[i]; }

  const x = new Float32Array(n), y = new Float32Array(n);
  const kidsOf = (p: number) => Array.from(kids.subarray(start[p], start[p + 1]));
  const BIG = 120; // a derivative with this many models built on it becomes a satellite galaxy of its own
  const reach = (c: number) => 6.5 * Math.sqrt(c + 1);

  /** Spiral arms around (cx, cy): one colour per kind of derivative, the most used nearest the core. */
  const spiral = (p: number, cx: number, cy: number, radius: number) => {
    const members = kidsOf(p).sort((a, b) => subDl[b] - subDl[a]);
    const groups: number[][] = [[], [], [], []];
    for (const i of members) groups[rel[i] >= 0 ? rel[i] : 1].push(i);
    const d1 = Math.max(1, members.length);
    const armsPer = groups.map((m) => (m.length ? (d1 < 8 ? 1 : 1 + Math.floor((3 * m.length) / d1)) : 0));
    // interleave arms so two arms of the same colour rarely sit side by side
    const bySize = [0, 1, 2, 3].filter((r) => armsPer[r]).sort((a, b) => groups[b].length - groups[a].length);
    const armRel: number[] = [];
    for (let round = 0; round < 4; round++) for (const r of bySize) if (round < armsPer[r]) armRel.push(r);
    const K = armRel.length, rot = hash(p, 99) * TAU;
    for (let r = 0; r < 4; r++) {
      const arms = armRel.flatMap((ar, a) => (ar === r ? [a] : []));
      if (!arms.length) continue;
      const per = Math.ceil(groups[r].length / arms.length);
      groups[r].forEach((i, j) => {
        const a = arms[j % arms.length], t = Math.sqrt((Math.floor(j / arms.length) + 0.5) / per);
        const th = rot + (a / K) * TAU + t * 2.5 + gauss(i, 1) * 0.08;
        let rr = radius * (0.1 + 0.9 * t) * (1 + gauss(i, 2) * 0.045);
        // satellites move out of the core so they don't bury the sun
        const c = start[i + 1] - start[i];
        if (c >= BIG) rr = Math.max(rr, radius * 0.22 + reach(c));
        const off = gauss(i, 3) * radius * (0.014 + 0.055 * t);
        x[i] = cx + Math.cos(th) * rr - Math.sin(th) * off;
        y[i] = cy + Math.sin(th) * rr + Math.cos(th) * off;
      });
    }
  };
  /** A small sunflower cluster around a star. */
  const cluster = (p: number) => {
    const ks = kidsOf(p), step = reach(ks.length) / Math.sqrt(ks.length + 1), a0 = hash(p, 5) * TAU;
    ks.forEach((k, j) => {
      const d = step * Math.sqrt(j + 1.2), a = a0 + j * GOLD;
      x[k] = x[p] + Math.cos(a) * d;
      y[k] = y[p] + Math.sin(a) * d;
    });
  };
  spiral(0, 0, 0, R);
  for (let p = 1; p < n; p++) { // BFS order: a parent is always placed before its children
    const c = start[p + 1] - start[p];
    if (c >= BIG) spiral(p, x[p], y[p], reach(c));
    else if (c) cluster(p);
  }

  const size = new Float32Array(n), order = new Int32Array(n), delay = new Float32Array(n);
  for (let i = 0; i < n; i++) { size[i] = 0.55 + 0.42 * Math.log10(1 + (dl30[i] || 0)); order[i] = i; }
  order.sort((a, b) => (dl30[b] || 0) - (dl30[a] || 0));
  order.forEach((i, k) => { delay[i] = 0.45 * (k / n); });
  const byRel = [0, 1, 2, 3].map((r) => Int32Array.from({ length: n }, (_, i) => i).filter((i) => i > 0 && (rel[i] >= 0 ? rel[i] : 1) === r));
  const dist = Array.from({ length: n }, (_, i) => Math.hypot(x[i], y[i])).sort((a, b) => a - b);
  const extent = Math.max(R * 0.35, dist[Math.floor((n - 1) * 0.995)] ?? R);

  const cell = 16, grid = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const key = Math.floor(x[i] / cell) * 100003 + Math.floor(y[i] / cell);
    const b = grid.get(key);
    b ? b.push(i) : grid.set(key, [i]);
  }
  return { n, x, y, size, delay, sub, byRel, order, extent, cell, grid };
}

type View = { k: number; cx: number; cy: number };
type DrawOpts = { p: number; hidden: boolean[]; hover: number; sel: number; kFit: number; labels: boolean; labelHits?: number[][] };

function draw(c: CanvasRenderingContext2D, W: number, H: number, v: View, g: GalaxyData, L: Layout, o: DrawOpts) {
  const { x, y, size, delay } = L;
  c.globalCompositeOperation = "source-over"; c.globalAlpha = 1;
  c.fillStyle = SKY; c.fillRect(0, 0, W, H);
  const ox = (0 - v.cx) * v.k + W / 2, oy = (0 - v.cy) * v.k + H / 2;
  const glow = c.createRadialGradient(ox, oy, 0, ox, oy, Math.max(80, R * 0.45 * v.k));
  glow.addColorStop(0, "rgba(255,210,30,0.20)"); glow.addColorStop(1, "rgba(255,210,30,0)");
  c.fillStyle = glow; c.fillRect(0, 0, W, H);

  const zf = Math.min(3.2, Math.max(1, Math.sqrt(v.k / o.kFit)));
  const anim = o.p < 1;
  const pos = (i: number, out: number[]) => {
    let wx = x[i], wy = y[i];
    if (anim) {
      const t = Math.min(1, Math.max(0, (o.p - delay[i]) / 0.55)), e = 1 - (1 - t) ** 3;
      if (e <= 0) return false;
      const a = (1 - e) * 1.3, s = 0.12 + 0.88 * e, ca = Math.cos(a), sa = Math.sin(a);
      [wx, wy] = [(wx * ca - wy * sa) * s, (wx * sa + wy * ca) * s];
    }
    out[0] = (wx - v.cx) * v.k + W / 2; out[1] = (wy - v.cy) * v.k + H / 2;
    return true;
  };
  const pt = [0, 0];
  c.globalCompositeOperation = "lighter";
  for (let r = 0; r < 4; r++) {
    if (o.hidden[r]) continue;
    c.fillStyle = REL[r].color;
    const small = new Path2D(), big = new Path2D();
    for (const i of L.byRel[r]) {
      if (!pos(i, pt)) continue;
      const s = size[i] * zf, px = pt[0], py = pt[1];
      if (px < -s || py < -s || px > W + s || py > H + s) continue;
      if (s < 1.15) small.rect(px - s, py - s, s * 2, s * 2);
      else { big.moveTo(px + s, py); big.arc(px, py, s, 0, TAU); }
    }
    // faint dust adds up where stars crowd, so dense regions glow instead of turning into a white blob
    c.globalAlpha = 0.5; c.fill(small);
    c.globalAlpha = 0.85; c.fill(big);
  }
  // white cores make the most used stars read as bright ones
  c.globalAlpha = 0.9; c.fillStyle = "#fff"; c.beginPath();
  for (let k = 0, shown = 0; k < L.n && shown < 80; k++) {
    const i = L.order[k];
    if (i === 0 || (g.nodes.dl30[i] || 0) < 20_000) break;
    const r = g.nodes.rel[i] >= 0 ? g.nodes.rel[i] : 1;
    if (o.hidden[r] || !pos(i, pt)) continue;
    const s = size[i] * zf * 0.42;
    c.moveTo(pt[0] + s, pt[1]); c.arc(pt[0], pt[1], s, 0, TAU); shown++;
  }
  c.fill();
  c.globalCompositeOperation = "source-over"; c.globalAlpha = 1;

  if (!anim) for (const i of [o.sel, o.hover]) highlight(c, W, H, v, g, L, o.kFit, i, i === o.sel);

  // the base model is the sun
  const sr = 9 + 3 * Math.sqrt(zf);
  if (pos(0, pt)) {
    c.beginPath(); c.arc(pt[0], pt[1], sr + 6, 0, TAU); c.fillStyle = "rgba(255,210,30,0.22)"; c.fill();
    c.beginPath(); c.arc(pt[0], pt[1], sr, 0, TAU); c.fillStyle = SUN; c.fill();
    c.lineWidth = 2.5; c.strokeStyle = SKY; c.stroke();
  }

  if (!o.labels || anim) return;
  const max = Math.min(36, Math.round(8 + 7 * Math.max(0, Math.log2(v.k / o.kFit))));
  // keep labels off the sun and out from under the zoom buttons
  const boxes: number[][] = [[pt[0] - sr - 4, pt[1] - sr - 4, sr * 2 + 8, sr * 2 + 8], [W - 64, 0, 64, 150]];
  c.font = "600 12.5px 'Source Sans 3', system-ui, sans-serif";
  c.textBaseline = "middle"; c.lineJoin = "round";
  let drawn = 0;
  const said = new Set<string>(); // forks often keep the original name; label the most used one
  for (let k = 0; k < Math.min(L.n, 600) && drawn < max; k++) {
    const i = L.order[k];
    const r = g.nodes.rel[i] >= 0 ? g.nodes.rel[i] : 1;
    if (i === 0 || o.hidden[r] || !(g.nodes.dl30[i] > 0)) continue;
    pos(i, pt);
    const s = size[i] * zf, t = short(g.nodes.id[i]);
    if (said.has(t)) continue;
    const w = c.measureText(t).width, bx = pt[0] + s + 5, by = pt[1] - 9;
    if (bx < 4 || by < 4 || bx + w > W - 4 || by + 18 > H - 4) continue;
    if (boxes.some((b) => bx < b[0] + b[2] && bx + w > b[0] && by < b[1] + b[3] && by + 18 > b[1])) continue;
    boxes.push([bx - 2, by, w + 4, 18]);
    o.labelHits?.push([bx - 2, by, w + 4, 18, i]);
    said.add(t);
    c.lineWidth = 3.5; c.strokeStyle = SKY; c.strokeText(t, bx, pt[1]);
    c.fillStyle = STAR_TEXT; c.fillText(t, bx, pt[1]);
    drawn++;
  }
}

/** The path from a star back to the core, and a ring around the star. */
function highlight(c: CanvasRenderingContext2D, W: number, H: number, v: View, g: GalaxyData, L: Layout, kFit: number, i: number, selected: boolean) {
  if (i <= 0) return;
  const zf = Math.min(3.2, Math.max(1, Math.sqrt(v.k / kFit)));
  const sx = (j: number) => (L.x[j] - v.cx) * v.k + W / 2, sy = (j: number) => (L.y[j] - v.cy) * v.k + H / 2;
  c.beginPath(); c.strokeStyle = SUN; c.lineWidth = 1.6; c.globalAlpha = 0.85;
  let j = i; c.moveTo(sx(j), sy(j));
  while (j > 0) { j = g.nodes.parent[j]; c.lineTo(sx(j), sy(j)); }
  c.stroke(); c.globalAlpha = 1;
  c.beginPath(); c.arc(sx(i), sy(i), L.size[i] * zf + 5, 0, TAU);
  c.strokeStyle = selected ? SUN : "#fff"; c.lineWidth = 2; c.stroke();
}

function fitView(L: Layout, W: number, H: number): View {
  return { k: (Math.min(W, H) / 2 - 18) / (L.extent * 1.04), cx: 0, cy: 0 };
}

function Sky({ g, L, hidden, sel, onSel, flyTo }: {
  g: GalaxyData; L: Layout; hidden: boolean[]; sel: number; onSel: (i: number) => void; flyTo: { i: number; n: number } | null;
}) {
  const box = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
  const st = useRef({ W: 0, H: 0, dpr: 1, view: { k: 1, cx: 0, cy: 0 } as View, kFit: 1, p: reduceMotion() ? 1 : 0, hover: -1, raf: 0, labels: [] as number[][] });
  const props = useRef({ hidden, sel });
  props.current = { hidden, sel };
  const [tip, setTip] = useState<{ i: number; x: number; y: number } | null>(null);

  const snap = useRef<{ img: HTMLCanvasElement; view: View; heavy: boolean } | null>(null);
  const settle = useRef(0);

  /** Full redraw. The frame is cached without the hover highlight, which is laid on top. */
  const paint = () => {
    const s = st.current, c = cv.current?.getContext("2d");
    if (!c || !s.W) return;
    c.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    s.labels = [];
    const t0 = performance.now();
    draw(c, s.W, s.H, s.view, g, L, { p: s.p, hidden: props.current.hidden, hover: -1, sel: props.current.sel, kFit: s.kFit, labels: true, labelHits: s.labels });
    const heavy = performance.now() - t0 > 22;
    if (s.p >= 1) {
      const img = snap.current?.img ?? document.createElement("canvas");
      if (img.width !== cv.current!.width || img.height !== cv.current!.height) { img.width = cv.current!.width; img.height = cv.current!.height; }
      const x = img.getContext("2d")!;
      x.setTransform(1, 0, 0, 1, 0, 0); x.drawImage(cv.current!, 0, 0);
      snap.current = { img, view: { ...s.view }, heavy };
    }
    highlight(c, s.W, s.H, s.view, g, L, s.kFit, s.hover, false);
  };
  /** Cheap frame: the cached image moved to the current view, plus the hover highlight. */
  const blit = () => {
    const s = st.current, c = cv.current?.getContext("2d"), sn = snap.current;
    if (!c || !sn) return paint();
    const f = s.view.k / sn.view.k;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = SKY; c.fillRect(0, 0, cv.current!.width, cv.current!.height);
    const dx = (s.W / 2 - (s.W / 2) * f + (sn.view.cx - s.view.cx) * s.view.k) * s.dpr;
    const dy = (s.H / 2 - (s.H / 2) * f + (sn.view.cy - s.view.cy) * s.view.k) * s.dpr;
    c.drawImage(sn.img, dx, dy, sn.img.width * f, sn.img.height * f);
    c.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    if (f === 1 && dx === 0 && dy === 0) highlight(c, s.W, s.H, s.view, g, L, s.kFit, s.hover, false);
  };
  const request = () => {
    const s = st.current;
    if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; paint(); });
  };
  /** After the view changed: move the cached frame now when redrawing is slow, and redraw once things settle. */
  const viewChanged = () => {
    const s = st.current;
    if (!snap.current?.heavy) return request();
    if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; blit(); });
    clearTimeout(settle.current);
    settle.current = window.setTimeout(request, 160);
  };
  /** Only the hover changed: reuse the cached frame when the view hasn't moved. */
  const hovered = () => {
    const s = st.current, sn = snap.current;
    if (sn && sn.view.k === s.view.k && sn.view.cx === s.view.cx && sn.view.cy === s.view.cy && s.p >= 1) {
      if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; blit(); });
    } else request();
  };
  const animate = (ms: number, step: (e: number) => void, view = false) => {
    if (reduceMotion()) { step(1); request(); return; }
    const t0 = performance.now();
    const tick = (t: number) => {
      const u = Math.min(1, (t - t0) / ms);
      step(u);
      if (view && u < 1 && snap.current?.heavy) blit(); else paint();
      if (u < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  // size to the container, and play the entrance once per galaxy
  useEffect(() => {
    const s = st.current;
    const resize = () => {
      const r = box.current!.getBoundingClientRect();
      const first = !s.W;
      s.W = r.width; s.H = r.height; s.dpr = Math.min(2, devicePixelRatio || 1);
      cv.current!.width = Math.round(s.W * s.dpr); cv.current!.height = Math.round(s.H * s.dpr);
      const fit = fitView(L, s.W, s.H);
      if (first) s.view = fit;
      else s.view = { ...s.view, k: s.view.k * (fit.k / s.kFit) };
      s.kFit = fit.k;
      paint();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(box.current!);
    if (s.p < 1) animate(2000, (u) => { s.p = u; });
    return () => { ro.disconnect(); clearTimeout(settle.current); };
  }, [L]);

  useEffect(request, [hidden, sel]);

  useEffect(() => {
    if (!flyTo) return;
    const s = st.current, from = { ...s.view };
    const to = { k: Math.max(from.k, s.kFit * 5), cx: L.x[flyTo.i], cy: L.y[flyTo.i] };
    animate(700, (u) => {
      const e = u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2;
      s.view = { k: from.k * (to.k / from.k) ** e, cx: from.cx + (to.cx - from.cx) * e, cy: from.cy + (to.cy - from.cy) * e };
    }, true);
  }, [flyTo]);

  const zoomAt = (px: number, py: number, f: number) => {
    const s = st.current, v = s.view;
    const wx = (px - s.W / 2) / v.k + v.cx, wy = (py - s.H / 2) / v.k + v.cy;
    const k = Math.min(s.kFit * 80, Math.max(s.kFit * 0.6, v.k * f));
    s.view = { k, cx: wx - (px - s.W / 2) / k, cy: wy - (py - s.H / 2) / k };
    viewChanged();
  };

  const hit = (px: number, py: number) => {
    const s = st.current, v = s.view;
    // a label belongs to its star
    for (const b of s.labels) if (px >= b[0] && px <= b[0] + b[2] && py >= b[1] && py <= b[1] + b[3]) return b[4];
    const wx = (px - s.W / 2) / v.k + v.cx, wy = (py - s.H / 2) / v.k + v.cy;
    const zf = Math.min(3.2, Math.max(1, Math.sqrt(v.k / s.kFit)));
    const reach = 14 / v.k, c0 = Math.floor((wx - reach) / L.cell), c1 = Math.floor((wx + reach) / L.cell);
    const r0 = Math.floor((wy - reach) / L.cell), r1 = Math.floor((wy + reach) / L.cell);
    let best = -1, bestD = Infinity;
    for (let cx = c0; cx <= c1; cx++) for (let cy = r0; cy <= r1; cy++) {
      for (const i of L.grid.get(cx * 100003 + cy) ?? []) {
        const r = g.nodes.rel[i] >= 0 ? g.nodes.rel[i] : 1;
        if (i > 0 && props.current.hidden[r]) continue;
        const rad = i === 0 ? 12 : L.size[i] * zf;
        const d = Math.hypot((L.x[i] - wx) * v.k, (L.y[i] - wy) * v.k);
        // favour the brighter star when small ones crowd around it
        if (d <= Math.max(7, rad + 5) && d - 1.6 * rad < bestD) { best = i; bestD = d - 1.6 * rad; }
      }
    }
    return best;
  };

  // pointer: drag to pan, pinch or wheel to zoom, tap to select
  useEffect(() => {
    const el = cv.current!, s = st.current;
    const pts = new Map<number, { x: number; y: number }>();
    let moved = 0, pinch = 0;
    const local = (e: PointerEvent | WheelEvent) => { const r = el.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const down = (e: PointerEvent) => { el.setPointerCapture(e.pointerId); pts.set(e.pointerId, local(e)); moved = 0; pinch = 0; };
    const move = (e: PointerEvent) => {
      const p = local(e);
      if (!pts.has(e.pointerId)) {
        if (e.pointerType !== "mouse") return;
        const i = hit(p.x, p.y);
        if (i !== s.hover) { s.hover = i; hovered(); }
        setTip(i >= 0 ? { i, x: p.x, y: p.y } : null);
        el.style.cursor = i >= 0 ? "pointer" : "grab";
        return;
      }
      const prev = pts.get(e.pointerId)!;
      pts.set(e.pointerId, p);
      if (pts.size === 1) {
        moved += Math.abs(p.x - prev.x) + Math.abs(p.y - prev.y);
        s.view = { ...s.view, cx: s.view.cx - (p.x - prev.x) / s.view.k, cy: s.view.cy - (p.y - prev.y) / s.view.k };
        if (s.hover >= 0) { s.hover = -1; setTip(null); }
        viewChanged();
      } else if (pts.size === 2) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (pinch) zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, d / pinch);
        pinch = d; moved = 99;
      }
    };
    const up = (e: PointerEvent) => {
      const p = pts.get(e.pointerId);
      pts.delete(e.pointerId);
      if (pts.size < 2) pinch = 0;
      if (p && moved < 6 && pts.size === 0) {
        const i = hit(p.x, p.y);
        onSelRef.current(i > 0 ? i : -1);
      }
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = local(e);
      zoomAt(p.x, p.y, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0018)));
    };
    const leave = () => { if (s.hover >= 0) { s.hover = -1; hovered(); } setTip(null); };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("pointerleave", leave);
    el.addEventListener("wheel", wheel, { passive: false });
    return () => {
      el.removeEventListener("pointerdown", down); el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      el.removeEventListener("pointerleave", leave); el.removeEventListener("wheel", wheel);
    };
  }, [L]);
  const onSelRef = useRef(onSel);
  onSelRef.current = onSel;

  const zoomBy = (f: number) => { const s = st.current; zoomAt(s.W / 2, s.H / 2, f); };
  const reset = () => {
    const s = st.current, from = { ...s.view }, to = fitView(L, s.W, s.H);
    animate(500, (u) => {
      const e = 1 - (1 - u) ** 3;
      s.view = { k: from.k + (to.k - from.k) * e, cx: from.cx * (1 - e), cy: from.cy * (1 - e) };
    }, true);
  };

  return (
    <div class="g-sky" ref={box}>
      <canvas ref={cv} role="img" aria-label={`A galaxy of ${fmtFull(L.n - 1)} models built on ${g.root.id}`} />
      <div class="g-zoom">
        <button aria-label="Zoom in" onClick={() => zoomBy(1.6)}>+</button>
        <button aria-label="Zoom out" onClick={() => zoomBy(1 / 1.6)}>−</button>
        <button aria-label="Show the whole galaxy" onClick={reset}>⤢</button>
      </div>
      {tip && tip.i !== sel && (
        <div class="g-tip" style={{ left: tip.x, top: tip.y }}>
          <b>{g.nodes.id[tip.i]}</b>
          <span>{tip.i === 0 ? "the base model" : REL[g.nodes.rel[tip.i] >= 0 ? g.nodes.rel[tip.i] : 1].label.toLowerCase().replace(/s$/, "")}, {fmt(g.nodes.dl30[tip.i])} downloads in 30 days</span>
        </div>
      )}
      <span class="g-hint">Drag to move, scroll or pinch to zoom</span>
    </div>
  );
}

async function shareImage(g: GalaxyData, L: Layout) {
  await Promise.all(["600 60px 'Fredoka'", "500 20px 'IBM Plex Mono'", "600 14px 'Source Sans 3'"].map((f) => document.fonts.load(f)));
  const W = 1600, H = 900, c = document.createElement("canvas");
  c.width = W; c.height = H;
  const x = c.getContext("2d")!;
  const k = (H / 2 - 30) / (L.extent * 1.02);
  draw(x, W, H, { k, cx: -(1060 - W / 2) / k, cy: 0 }, g, L, { p: 1, hidden: [false, false, false, false], hover: -1, sel: -1, kFit: k, labels: true });
  const fade = x.createLinearGradient(0, 0, 760, 0);
  fade.addColorStop(0, "rgba(22,22,26,0.96)"); fade.addColorStop(0.75, "rgba(22,22,26,0.75)"); fade.addColorStop(1, "rgba(22,22,26,0)");
  x.fillStyle = fade; x.fillRect(0, 0, 760, H);
  const text = (t: string, tx: number, ty: number, font: string, color: string, max = 600) => {
    x.font = font; x.fillStyle = color; x.textBaseline = "alphabetic";
    if (x.measureText(t).width > max) { while (t.length > 3 && x.measureText(t + "…").width > max) t = t.slice(0, -1); t += "…"; }
    x.fillText(t, tx, ty);
  };
  // logo
  x.fillStyle = SUN; x.beginPath(); x.roundRect(64, 64, 56, 56, 14); x.fill();
  x.beginPath(); x.lineWidth = 5; x.strokeStyle = "#1b1b1f"; x.lineJoin = "round"; x.lineCap = "round";
  x.moveTo(74, 94); x.lineTo(84, 94); x.lineTo(90, 78); x.lineTo(100, 108); x.lineTo(106, 94); x.lineTo(112, 94); x.stroke();
  text("Model Pulse Galaxy", 136, 104, "600 32px 'Fredoka'", STAR_TEXT);
  const [org, name] = g.root.id.includes("/") ? g.root.id.split("/") : ["", g.root.id];
  text(org ? org + "/" : "", 64, 236, "500 24px 'IBM Plex Mono'", "#a9a69e");
  text(name, 62, 306, `600 ${name.length > 18 ? 52 : 66}px 'Fredoka'`, SUN, 640);
  text(fmtFull(g.total), 64, 420, "600 76px 'Fredoka'", STAR_TEXT);
  text("models built on it", 66, 460, "500 24px 'IBM Plex Mono'", "#a9a69e");
  if (g.root.fam_dl30) {
    text(fmt(g.root.fam_dl30), 64, 556, "600 52px 'Fredoka'", STAR_TEXT);
    text("family downloads in the last 30 days", 66, 592, "500 22px 'IBM Plex Mono'", "#a9a69e");
  }
  const counts = [0, 1, 2, 3].map((r) => L.byRel[r].length);
  let ly = 680;
  REL.forEach((r, i) => {
    if (!counts[i]) return;
    x.fillStyle = r.color; x.beginPath(); x.arc(74, ly - 8, 8, 0, TAU); x.fill();
    text(`${r.label}  ${fmtFull(counts[i])}`, 94, ly, "500 22px 'IBM Plex Mono'", STAR_TEXT);
    ly += 38;
  });
  text("huggingface.co/spaces/tardellirs/model-pulse", 64, H - 44, "500 20px 'IBM Plex Mono'", "#a9a69e");
  return new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/png"));
}

function Entry() {
  const [fams, setFams] = useState<{ id: string; fam_members: number; fam_dl30: number | null }[]>([]);
  useEffect(() => { document.title = "Model Pulse Galaxy"; get<typeof fams>("/api/galaxies").then((r) => setFams(r.slice(0, 16))).catch(() => {}); }, []);
  return (
    <>
      <div class="wrap w-entry g-entry">
        <h1><Logo size={72} />Model Pulse <span class="hl">Galaxy</span></h1>
        <p class="lede">Pick a base model and see every model built on it, from quantizations and fine-tunes to adapters and merges. The most downloaded shine brightest.</p>
        <div class="g-search">
          <Search big placeholder="A base model, e.g. meta-llama/Llama-3.1-8B" onPick={(id) => navigate({ view: "galaxy", model: id })} />
        </div>
      </div>
      {fams.length > 0 && (
        <section class="wrap g-fams">
          <h2>The biggest galaxies right now</h2>
          <div class="g-grid">
            {fams.map((r, k) => (
              <a key={r.id} class="g-fam" href={`?model=${r.id}&view=galaxy`} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: r.id }); }}>
                <i class="g-dot" style={{ transform: `rotate(${k * 47}deg)` }} aria-hidden="true" />
                <span class="o">{r.id.split("/")[0]}/</span>
                <span class="nm">{short(r.id)}</span>
                <span class="c">{fmtFull(r.fam_members)} models, {fmt(r.fam_dl30)} downloads in 30 days</span>
              </a>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

export function Galaxy({ model }: { model?: string }) {
  const [g, setG] = useState<GalaxyData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hidden, setHidden] = useState([false, false, false, false]);
  const [sel, setSel] = useState(-1);
  const [fly, setFly] = useState<{ i: number; n: number } | null>(null);
  const [q, setQ] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!model) return;
    document.title = `${model} galaxy · Model Pulse`;
    setG(null); setErr(null); setSel(-1); setQ("");
    get<GalaxyData>(`/api/galaxy/${model}`).then(setG).catch((e) => setErr(e.message));
  }, [model]);

  const L = useMemo(() => (g ? layout(g) : null), [g]);
  const lower = useMemo(() => (g ? g.nodes.id.map((s) => s.toLowerCase()) : []), [g]);
  const found = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!L || s.length < 2) return [];
    const out: number[] = [];
    for (let k = 0; k < L.n && out.length < 8; k++) if (L.order[k] > 0 && lower[L.order[k]].includes(s)) out.push(L.order[k]);
    return out;
  }, [q, L, lower]);

  if (!model) return <Entry />;
  if (err) return <div class="wrap err"><h1>No galaxy to show</h1><p>{err}</p></div>;

  const root = g?.root;
  const [org, name] = model.includes("/") ? [model.split("/")[0], short(model)] : ["", model];
  const pick = (i: number) => { setSel(i); setQ(""); if (i > 0) setFly({ i, n: Date.now() }); };
  const url = shareUrl({ view: "galaxy", model: root?.id ?? model });
  const post = root ? `${fmtFull(g!.total)} models are built on ${root.id}. Here is its whole galaxy:` : "";
  const top = g?.lineage.length ? g.lineage[g.lineage.length - 1] : null;

  return (
    <div class="galaxy">
      <div class="wrap g-head">
        <div class="crumbs">
          <a class="chip" href="?view=galaxy" onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy" }); }}>All galaxies</a>
          {top && <a class="chip chip-hot" href={`?model=${top}&view=galaxy`} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: top }); }}>Part of the {short(top)} galaxy</a>}
        </div>
        <h1 class="model-name">{org && <span class="org">{org}/</span>}<span class="hl">{name}</span></h1>
        <p class="g-lede">
          {!g ? "Mapping every model built on it…"
            : g.total ? <>{fmtFull(g.total)} models are built on {name}, directly or through other derivatives. Together with the original they were downloaded <b>{fmt(root!.fam_dl30)}</b> times in the last 30 days.</>
              : <>No models on the Hub are built on {name} yet.</>}
        </p>
      </div>

      <div class="wrap">
        <div class="g-panel">
          {g && L && g.total > 0 ? (
            <Sky g={g} L={L} hidden={hidden} sel={sel} onSel={setSel} flyTo={fly} />
          ) : (
            <div class="g-sky g-empty">{g ? <span>Nothing orbits this model yet.</span> : <span class="g-loading">Mapping the galaxy…</span>}</div>
          )}
          {g && sel >= 0 && L && (
            <div class="g-card">
              <button class="x" aria-label="Close" onClick={() => setSel(-1)}>×</button>
              <a class="id" href={`?model=${g.nodes.id[sel]}`} onClick={(e) => { e.preventDefault(); navigate({ model: g.nodes.id[sel] }); }}>{g.nodes.id[sel]}</a>
              <span class="g-rel">
                <i style={{ background: REL[g.nodes.rel[sel] >= 0 ? g.nodes.rel[sel] : 1].color }} />
                {REL[g.nodes.rel[sel] >= 0 ? g.nodes.rel[sel] : 1].of} {short(g.nodes.id[g.nodes.parent[sel]])}
              </span>
              <span class="n"><b>{fmtFull(g.nodes.dl30[sel])}</b> downloads in the last 30 days</span>
              {L.sub[sel] > 1 && <span class="n"><b>{fmtFull(L.sub[sel] - 1)}</b> models built on it</span>}
              <div class="acts">
                <a class="btn primary" href={`?model=${g.nodes.id[sel]}`} onClick={(e) => { e.preventDefault(); navigate({ model: g.nodes.id[sel] }); }}>Download history</a>
                {L.sub[sel] > 1 && <a class="btn" href={`?model=${g.nodes.id[sel]}&view=galaxy`} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: g.nodes.id[sel] }); }}>Its own galaxy</a>}
              </div>
            </div>
          )}
        </div>

        {g && L && g.total > 0 && (
          <div class="g-tools">
            <div class="g-legend" role="group" aria-label="Show or hide kinds of derivatives">
              {REL.map((r, i) => L.byRel[i].length > 0 && (
                <button key={r.label} aria-pressed={!hidden[i]} onClick={() => setHidden(hidden.map((h, j) => (j === i ? !h : h)))}>
                  <i style={{ background: r.color }} />{r.label}<b>{fmtFull(L.byRel[i].length)}</b>
                </button>
              ))}
            </div>
            <div class="g-find">
              <input value={q} onInput={(e) => setQ((e.target as HTMLInputElement).value)} placeholder="Find a model in this galaxy" aria-label="Find a model in this galaxy" spellcheck={false}
                onKeyDown={(e) => { if (e.key === "Enter" && found.length) pick(found[0]); if (e.key === "Escape") setQ(""); }} />
              {found.length > 0 && (
                <ul class="g-found">
                  {found.map((i) => (
                    <li key={i}><button onClick={() => pick(i)}><span>{g.nodes.id[i]}</span><small>{fmt(g.nodes.dl30[i])}/mo</small></button></li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {g && L && g.total > 0 && (
          <div class="g-foot">
            <p class="g-read">
              Each star is a model built on {name}, and the yellow sun is {name} itself. Colours show how a model was made, and each kind
              forms its own spiral arms. Bigger, brighter stars were downloaded more in the last 30 days, and the most used sit closest to the core.
              The small clusters around a star are the models built on that one. Tap a star to see its numbers.
              {L.n - 1 < g.total ? ` Showing the ${fmtFull(L.n - 1)} most downloaded.` : ""}
            </p>
            <div class="w-actions g-actions">
              <button class="btn primary" disabled={saving} onClick={async () => {
                setSaving(true);
                try {
                  const b = await shareImage(g, L);
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(b); a.download = `${g.root.id.replace("/", "_")}-galaxy.png`; a.click();
                  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
                } finally { setSaving(false); }
              }}>{saving ? "Drawing…" : "Download image"}</button>
              <a class="btn" target="_blank" rel="noopener" href={`https://x.com/intent/post?text=${encodeURIComponent(post)}&url=${encodeURIComponent(url)}`}>Post on X</a>
              <a class="btn" target="_blank" rel="noopener" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}>LinkedIn</a>
              <button class="btn" onClick={() => navigator.clipboard?.writeText(url)}>Copy link</button>
              <a class="btn" href={`?model=${g.root.id}`} onClick={(e) => { e.preventDefault(); navigate({ model: g.root.id }); }}>{name} download history</a>
              <LikeCta />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
