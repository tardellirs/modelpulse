import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { fmt, fmtFull, get, hrefOf, navigate, shareUrl } from "./api";
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
type Fam = { id: string; fam_members: number; fam_dl30: number | null; n_quantized: number; n_finetune: number; n_adapter: number; n_merge: number };

/** Indexed by the API's relation codes; the same hues as the Family bar on model pages. */
const REL = [
  { label: "Quantized", one: "quantization", color: "#3b6ff5", of: "Quantized from" },
  { label: "Fine-tuned", one: "fine-tune", color: "#ff8a1f", of: "Fine-tuned from" },
  { label: "Adapters", one: "adapter", color: "#2f8f5b", of: "Adapter on" },
  { label: "Merges", one: "merge", color: "#a35bf0", of: "Merge built on" },
];
/** Clockwise from the top: fine-tunes, adapters, quantizations, merges. */
const SECTOR_ORDER = [1, 2, 0, 3];
const INK = "#1b1b1f", PAPER = "#fbfaf5", SUN = "#ffd21e", MUTED = "#63615b";
/** Orbit radius for each generation (world units); the 4th ring also holds anything deeper. */
const RING = [0, 330, 590, 800, 960];
const TAU = Math.PI * 2;
const ORD = ["", "1st", "2nd", "3rd", "4th+"];
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const short = (id: string) => id.split("/").pop() ?? id;
const relOf = (g: GalaxyData, i: number) => (g.nodes.rel[i] >= 0 ? g.nodes.rel[i] : 1);

function hash(i: number, s: number) {
  let h = Math.imul(i ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(s + 1, 0xc2b2ae35);
  h ^= h >>> 13; h = Math.imul(h, 0x27d4eb2f); h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

type Layout = {
  n: number; x: Float32Array; y: Float32Array; ang: Float32Array; size: Float32Array; depth: Uint8Array;
  sub: Int32Array; start: Int32Array; kids: Int32Array; byRel: Int32Array[]; order: Int32Array;
  rings: number[]; sectors: { rel: number; a0: number; a1: number; count: number }[];
  gens: number[]; extent: number; cell: number; grid: Map<number, number[]>; links: Int32Array;
};

/**
 * An orrery: the base model is the sun, each generation of derivatives sits on its own orbit, direct derivatives
 * are grouped into one sector per kind, and everything built on a model stays inside that model's slice of the circle.
 */
function layout(g: GalaxyData): Layout {
  const { parent, dl30 } = g.nodes;
  const n = parent.length;
  const depth = new Uint8Array(n), sub = new Int32Array(n).fill(1);
  const start = new Int32Array(n + 1);
  for (let i = 1; i < n; i++) { depth[i] = Math.min(4, depth[parent[i]] + 1); start[parent[i] + 1]++; }
  for (let i = 0; i < n; i++) start[i + 1] += start[i];
  const fill = start.slice(0, n), kids = new Int32Array(Math.max(0, n - 1));
  for (let i = 1; i < n; i++) kids[fill[parent[i]]++] = i;
  for (let i = n - 1; i > 0; i--) sub[parent[i]] += sub[i];

  const gens = [0, 0, 0, 0, 0];
  for (let i = 1; i < n; i++) gens[depth[i]]++;
  // a model gets room in proportion to everything built on it, softened so the long tail stays visible
  const weight = (i: number) => 1 + Math.pow(sub[i] - 1, 0.8);
  const ang = new Float32Array(n), span = new Float32Array(n), x = new Float32Array(n), y = new Float32Array(n);

  /** Lay ids across [a0, a1] by weight, biggest in the middle. */
  const spread = (ids: number[], a0: number, a1: number) => {
    ids.sort((a, b) => weight(b) - weight(a) || (dl30[b] || 0) - (dl30[a] || 0));
    const arranged: number[] = [];
    ids.forEach((id, k) => (k % 2 ? arranged.unshift(id) : arranged.push(id)));
    const total = arranged.reduce((s, id) => s + weight(id), 0) || 1;
    let a = a0;
    for (const id of arranged) {
      const w = ((a1 - a0) * weight(id)) / total;
      ang[id] = a + w / 2; span[id] = w; a += w;
    }
  };

  // sectors for the direct derivatives, sized by the square root of their weight so small kinds stay readable
  const direct = Array.from(kids.subarray(start[0], start[1]));
  const groups = [0, 1, 2, 3].map((r) => direct.filter((i) => relOf(g, i) === r));
  const present = SECTOR_ORDER.filter((r) => groups[r].length);
  const gap = present.length > 1 ? 0.05 : 0;
  const raw = present.map((r) => Math.sqrt(groups[r].reduce((s, i) => s + weight(i), 0)));
  const rawTotal = raw.reduce((s, v) => s + v, 0) || 1;
  const minShare = present.length > 1 ? 0.12 : 1;
  const shares = raw.map((v) => Math.max(minShare, v / rawTotal));
  const shareTotal = shares.reduce((s, v) => s + v, 0);
  const usable = TAU - gap * present.length;
  const sectors: Layout["sectors"] = [];
  let a = -Math.PI / 2 - ((shares[0] / shareTotal) * usable) / 2;
  present.forEach((r, k) => {
    const w = (shares[k] / shareTotal) * usable;
    sectors.push({ rel: r, a0: a, a1: a + w, count: groups[r].length });
    spread(groups[r], a, a + w);
    a += w + gap;
  });
  // deeper generations inherit their parent's slice
  for (let p = 1; p < n; p++) {
    if (start[p + 1] > start[p]) spread(Array.from(kids.subarray(start[p], start[p + 1])), ang[p] - span[p] / 2, ang[p] + span[p] / 2);
  }

  // the most used models sit on the orbit line; the rest form a belt around it
  let maxDl = 1;
  for (let i = 1; i < n; i++) maxDl = Math.max(maxDl, dl30[i] || 0);
  const size = new Float32Array(n);
  for (let i = 1; i < n; i++) size[i] = (dl30[i] || 0) > 0 ? Math.min(24, 1.6 + 22 * Math.sqrt((dl30[i] || 0) / maxDl)) : 1.2;
  const band = gens.map((c) => Math.max(14, Math.min(120, Math.sqrt(c) * 1.3)));
  for (let i = 1; i < n; i++) {
    const d = depth[i], big = size[i] >= 5;
    const r = RING[d] + (big ? 0 : (hash(i, 1) - 0.5) * band[d]);
    const t = big ? ang[i] : ang[i] + (hash(i, 2) - 0.5) * Math.min(span[i] * 0.9, 0.08);
    x[i] = Math.cos(t) * r; y[i] = Math.sin(t) * r;
  }

  const order = Int32Array.from({ length: n }, (_, i) => i).sort((p, q) => (dl30[q] || 0) - (dl30[p] || 0));
  const byRel = [0, 1, 2, 3].map((r) => Int32Array.from({ length: n }, (_, i) => i).filter((i) => i > 0 && relOf(g, i) === r));
  const links = order.filter((i) => i > 0 && (dl30[i] || 0) > 0).slice(0, 160);
  const deepest = gens.reduce((m, c, d) => (c ? d : m), 1);
  const rings = RING.slice(1, deepest + 1);
  const extent = rings[rings.length - 1] + band[deepest] / 2 + 120;

  const cell = 24, grid = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const key = Math.floor(x[i] / cell) * 100003 + Math.floor(y[i] / cell);
    const b = grid.get(key);
    b ? b.push(i) : grid.set(key, [i]);
  }
  return { n, x, y, ang, size, depth, sub, start, kids, byRel, order, rings, sectors, gens, extent, cell, grid, links };
}

type View = { k: number; cx: number; cy: number };
type DrawOpts = { p: number; hidden: boolean[]; hover: number; sel: number; kFit: number; labelHits?: number[][]; labels?: number };

const zoomFactor = (k: number, kFit: number) => Math.min(2.6, Math.max(1, Math.sqrt(k / kFit)));
const sunRadius = (zf: number) => 22 + 6 * (zf - 1);

function draw(c: CanvasRenderingContext2D, W: number, H: number, v: View, g: GalaxyData, L: Layout, o: DrawOpts) {
  const { x, y, size } = L;
  const sx = (wx: number) => (wx - v.cx) * v.k + W / 2, sy = (wy: number) => (wy - v.cy) * v.k + H / 2;
  const ox = sx(0), oy = sy(0), zf = zoomFactor(v.k, o.kFit);
  const e = o.p >= 1 ? 1 : 1 - (1 - o.p) ** 3; // entrance: planets move out from the sun once
  c.globalAlpha = 1; c.fillStyle = PAPER; c.fillRect(0, 0, W, H);

  // sector wedges and orbits
  for (const s of L.sectors) {
    if (o.hidden[s.rel]) continue;
    c.beginPath(); c.moveTo(ox, oy); c.arc(ox, oy, (L.extent - 60) * v.k, s.a0, s.a1); c.closePath();
    c.fillStyle = REL[s.rel].color; c.globalAlpha = 0.045; c.fill();
  }
  c.globalAlpha = 1; c.setLineDash([3, 5]); c.lineWidth = 1; c.strokeStyle = "rgba(27,27,31,0.28)";
  for (const r of L.rings) { c.beginPath(); c.arc(ox, oy, r * v.k * e, 0, TAU); c.stroke(); }
  c.setLineDash([]);

  // lines from the most used derivatives to the model they come from
  c.strokeStyle = INK; c.lineWidth = 1; c.globalAlpha = 0.16 * e; c.beginPath();
  for (const i of L.links) {
    const p = g.nodes.parent[i];
    if (o.hidden[relOf(g, i)]) continue;
    c.moveTo(sx(x[p] * e), sy(y[p] * e)); c.lineTo(sx(x[i] * e), sy(y[i] * e));
  }
  c.stroke(); c.globalAlpha = 1;

  // the belt: small models as soft dots, one pass per kind
  for (let r = 0; r < 4; r++) {
    if (o.hidden[r]) continue;
    c.fillStyle = REL[r].color; c.globalAlpha = 0.5;
    const path = new Path2D();
    for (const i of L.byRel[r]) {
      if (size[i] >= 5) continue;
      const px = sx(x[i] * e), py = sy(y[i] * e), s = size[i] * zf;
      if (px < -s || py < -s || px > W + s || py > H + s) continue;
      if (s < 1.6) path.rect(px - s, py - s, s * 2, s * 2);
      else { path.moveTo(px + s, py); path.arc(px, py, s, 0, TAU); }
    }
    c.fill(path);
  }
  c.globalAlpha = 1;
  // planets: the most used models, outlined, smallest first so big ones stay on top
  for (let k = L.n - 1; k >= 0; k--) {
    const i = L.order[k];
    if (i === 0 || size[i] < 5 || o.hidden[relOf(g, i)]) continue;
    const px = sx(x[i] * e), py = sy(y[i] * e), s = size[i] * zf;
    c.beginPath(); c.arc(px, py, s, 0, TAU);
    c.fillStyle = REL[relOf(g, i)].color; c.fill();
    c.lineWidth = 2; c.strokeStyle = INK; c.stroke();
  }

  // the sun, with the site's hard shadow
  const sr = sunRadius(zf);
  c.beginPath(); c.arc(ox + 4, oy + 4, sr, 0, TAU); c.fillStyle = INK; c.fill();
  c.beginPath(); c.arc(ox, oy, sr, 0, TAU); c.fillStyle = SUN; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();

  for (const i of [o.sel, o.hover]) if (i > 0) highlight(c, W, H, v, g, L, o.kFit, i, i === o.sel);
  if (o.p < 1) return;

  // labels: sectors at the rim, then the biggest planets, more of them as you zoom in
  const boxes: number[][] = [[ox - sr - 6, oy - sr - 6, sr * 2 + 12, sr * 2 + 12], [W - 64, 0, 64, 150]];
  // labels steer around planets, not only around other labels
  for (const i of L.links) {
    if (o.hidden[relOf(g, i)] || size[i] < 5) continue;
    const s = size[i] * zf;
    boxes.push([sx(x[i]) - s, sy(y[i]) - s, s * 2, s * 2]);
  }
  c.textBaseline = "middle"; c.lineJoin = "round";
  for (const s of L.sectors) {
    if (o.hidden[s.rel]) continue;
    const m = (s.a0 + s.a1) / 2, r = (L.extent - 70) * v.k;
    const tx = ox + Math.cos(m) * r, ty = oy + Math.sin(m) * r;
    const t1 = REL[s.rel].label, t2 = `${fmtFull(s.count)} direct`;
    c.font = "600 13px 'IBM Plex Mono', ui-monospace, monospace";
    const w = c.measureText(`${t1} ${t2}`).width;
    const bx = Math.max(6, Math.min(W - w - 6, tx - w / 2));
    if (ty < 10 || ty > H - 10) continue;
    c.lineWidth = 4; c.strokeStyle = PAPER; c.strokeText(`${t1} ${t2}`, bx, ty);
    c.fillStyle = REL[s.rel].color; c.fillText(t1, bx, ty);
    c.fillStyle = INK; c.fillText(t2, bx + c.measureText(`${t1} `).width, ty);
    boxes.push([bx - 2, ty - 10, w + 4, 20]);
  }
  c.font = "500 11.5px 'IBM Plex Mono', ui-monospace, monospace";
  L.rings.forEach((r, d) => {
    // along the bottom of each orbit, usually the quietest part of the picture
    const t = `${ORD[d + 1]} generation`, tw = c.measureText(t).width, tx = ox - tw / 2, ty = oy + r * v.k + 11;
    if (ty < 8 || ty > H - 8) return;
    c.lineWidth = 4; c.strokeStyle = PAPER; c.strokeText(t, tx, ty); c.fillStyle = MUTED; c.fillText(t, tx, ty);
    boxes.push([tx - 2, ty - 8, tw + 4, 16]);
  });

  c.font = "600 15px 'Fredoka', system-ui, sans-serif";
  const sunName = short(g.root.id), snw = c.measureText(sunName).width, sny = oy + sr + 16;
  if (sny < H - 8) {
    c.lineWidth = 5; c.strokeStyle = PAPER; c.strokeText(sunName, ox - snw / 2, sny);
    c.fillStyle = INK; c.fillText(sunName, ox - snw / 2, sny);
    boxes.push([ox - snw / 2 - 2, sny - 10, snw + 4, 20]);
  }

  const max = o.labels ?? Math.min(40, Math.round(14 + 10 * Math.max(0, Math.log2(v.k / o.kFit))));
  const said = new Set<string>();
  c.font = "600 13px 'Source Sans 3', system-ui, sans-serif";
  let drawn = 0;
  const label = (i: number, force = false) => {
    const t = short(g.nodes.id[i]);
    if (!force && said.has(t)) return;
    const px = sx(x[i]), py = sy(y[i]), s = size[i] * zf;
    const right = Math.cos(L.ang[i]) >= -0.1;
    const w = c.measureText(t).width, bx = right ? px + s + 5 : px - s - 5 - w, by = py - 9;
    if (bx < 4 || by < 4 || bx + w > W - 4 || by + 18 > H - 4) return;
    if (!force && boxes.some((b) => bx < b[0] + b[2] && bx + w > b[0] && by < b[1] + b[3] && by + 18 > b[1])) return;
    boxes.push([bx - 2, by, w + 4, 18]);
    o.labelHits?.push([bx - 2, by, w + 4, 18, i]);
    said.add(t);
    c.lineWidth = 4; c.strokeStyle = PAPER; c.strokeText(t, bx, py);
    c.fillStyle = INK; c.fillText(t, bx, py);
    drawn++;
  };
  if (o.sel > 0) label(o.sel, true);
  for (let k = 0; k < Math.min(L.n, 800) && drawn < max; k++) {
    const i = L.order[k];
    if (i > 0 && (g.nodes.dl30[i] || 0) > 0 && !o.hidden[relOf(g, i)]) label(i);
  }
}

/** The path from a model back to the sun, plus links to the models built on it. */
function highlight(c: CanvasRenderingContext2D, W: number, H: number, v: View, g: GalaxyData, L: Layout, kFit: number, i: number, selected: boolean) {
  const sx = (j: number) => (L.x[j] - v.cx) * v.k + W / 2, sy = (j: number) => (L.y[j] - v.cy) * v.k + H / 2;
  const zf = zoomFactor(v.k, kFit);
  c.globalAlpha = 0.5; c.strokeStyle = REL[relOf(g, i)].color; c.lineWidth = 1.2; c.beginPath();
  for (let k = L.start[i]; k < L.start[i + 1] && k < L.start[i] + 400; k++) { const ch = L.kids[k]; c.moveTo(sx(i), sy(i)); c.lineTo(sx(ch), sy(ch)); }
  c.stroke(); c.globalAlpha = 1;
  c.strokeStyle = INK; c.lineWidth = 2.5; c.beginPath();
  let j = i; c.moveTo(sx(j), sy(j));
  while (j > 0) { j = g.nodes.parent[j]; c.lineTo(sx(j), sy(j)); }
  c.stroke();
  c.beginPath(); c.arc(sx(i), sy(i), Math.max(5, L.size[i] * zf) + 5, 0, TAU);
  c.lineWidth = 3; c.strokeStyle = selected ? INK : MUTED; c.stroke();
  if (selected) { c.beginPath(); c.arc(sx(i), sy(i), Math.max(5, L.size[i] * zf) + 9, 0, TAU); c.lineWidth = 2; c.strokeStyle = SUN; c.stroke(); }
}

const fitView = (L: Layout, W: number, H: number): View => ({ k: (Math.min(W, H) / 2 - 8) / L.extent, cx: 0, cy: 0 });

function Orrery({ g, L, hidden, sel, hoverExt, onSel, flyTo }: {
  g: GalaxyData; L: Layout; hidden: boolean[]; sel: number; hoverExt: number; onSel: (i: number) => void; flyTo: { i: number; n: number } | null;
}) {
  const box = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
  const st = useRef({ W: 0, H: 0, dpr: 1, view: { k: 1, cx: 0, cy: 0 } as View, kFit: 1, p: reduceMotion() ? 1 : 0, hover: -1, raf: 0, labels: [] as number[][] });
  const props = useRef({ hidden, sel, hoverExt });
  props.current = { hidden, sel, hoverExt };
  const snap = useRef<{ img: HTMLCanvasElement; view: View; heavy: boolean } | null>(null);
  const settle = useRef(0);
  const onSelRef = useRef(onSel);
  onSelRef.current = onSel;
  const [tip, setTip] = useState<{ i: number; x: number; y: number } | null>(null);

  const hovered = () => (props.current.hoverExt > 0 ? props.current.hoverExt : st.current.hover);
  /** Full redraw; the frame is cached without the hover highlight, which is laid on top. */
  const paint = () => {
    const s = st.current, c = cv.current?.getContext("2d");
    if (!c || !s.W) return;
    c.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    s.labels = [];
    const t0 = performance.now();
    draw(c, s.W, s.H, s.view, g, L, { p: s.p, hidden: props.current.hidden, hover: -1, sel: props.current.sel, kFit: s.kFit, labelHits: s.labels });
    if (s.p >= 1) {
      const img = snap.current?.img ?? document.createElement("canvas");
      if (img.width !== cv.current!.width || img.height !== cv.current!.height) { img.width = cv.current!.width; img.height = cv.current!.height; }
      const x = img.getContext("2d")!;
      x.setTransform(1, 0, 0, 1, 0, 0); x.drawImage(cv.current!, 0, 0);
      snap.current = { img, view: { ...s.view }, heavy: performance.now() - t0 > 22 };
    }
    if (hovered() > 0) highlight(c, s.W, s.H, s.view, g, L, s.kFit, hovered(), false);
  };
  /** Cheap frame: the cached image moved to the current view, plus the hover highlight. */
  const blit = () => {
    const s = st.current, c = cv.current?.getContext("2d"), sn = snap.current;
    if (!c || !sn) return paint();
    const f = s.view.k / sn.view.k;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = PAPER; c.fillRect(0, 0, cv.current!.width, cv.current!.height);
    const dx = (s.W / 2 - (s.W / 2) * f + (sn.view.cx - s.view.cx) * s.view.k) * s.dpr;
    const dy = (s.H / 2 - (s.H / 2) * f + (sn.view.cy - s.view.cy) * s.view.k) * s.dpr;
    c.drawImage(sn.img, dx, dy, sn.img.width * f, sn.img.height * f);
    c.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    if (f === 1 && dx === 0 && dy === 0 && hovered() > 0) highlight(c, s.W, s.H, s.view, g, L, s.kFit, hovered(), false);
  };
  const request = () => { const s = st.current; if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; paint(); }); };
  const viewChanged = () => {
    const s = st.current;
    if (!snap.current?.heavy) return request();
    if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; blit(); });
    clearTimeout(settle.current);
    settle.current = window.setTimeout(request, 160);
  };
  const hoverChanged = () => {
    const s = st.current, sn = snap.current;
    if (sn && s.p >= 1 && sn.view.k === s.view.k && sn.view.cx === s.view.cx && sn.view.cy === s.view.cy) {
      if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; blit(); });
    } else request();
  };
  const animate = (ms: number, step: (u: number) => void, view = false) => {
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

  useEffect(() => {
    const s = st.current;
    const resize = () => {
      const r = box.current!.getBoundingClientRect();
      const first = !s.W;
      s.W = r.width; s.H = r.height; s.dpr = Math.min(2, devicePixelRatio || 1);
      cv.current!.width = Math.round(s.W * s.dpr); cv.current!.height = Math.round(s.H * s.dpr);
      const fit = fitView(L, s.W, s.H);
      s.view = first ? fit : { ...s.view, k: s.view.k * (fit.k / s.kFit) };
      s.kFit = fit.k;
      paint();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(box.current!);
    if (s.p < 1) animate(1100, (u) => { s.p = u; });
    return () => { ro.disconnect(); clearTimeout(settle.current); };
  }, [L]);

  useEffect(request, [hidden, sel]);
  useEffect(hoverChanged, [hoverExt]);

  useEffect(() => {
    if (!flyTo) return;
    const s = st.current, from = { ...s.view };
    const to = { k: Math.max(from.k, s.kFit * 3.5), cx: L.x[flyTo.i], cy: L.y[flyTo.i] };
    animate(700, (u) => {
      const e = u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2;
      s.view = { k: from.k * (to.k / from.k) ** e, cx: from.cx + (to.cx - from.cx) * e, cy: from.cy + (to.cy - from.cy) * e };
    }, true);
  }, [flyTo]);

  const zoomAt = (px: number, py: number, f: number) => {
    const s = st.current, v = s.view;
    const wx = (px - s.W / 2) / v.k + v.cx, wy = (py - s.H / 2) / v.k + v.cy;
    const k = Math.min(s.kFit * 60, Math.max(s.kFit * 0.7, v.k * f));
    s.view = { k, cx: wx - (px - s.W / 2) / k, cy: wy - (py - s.H / 2) / k };
    viewChanged();
  };

  const hit = (px: number, py: number) => {
    const s = st.current, v = s.view;
    for (const b of s.labels) if (px >= b[0] && px <= b[0] + b[2] && py >= b[1] && py <= b[1] + b[3]) return b[4];
    const wx = (px - s.W / 2) / v.k + v.cx, wy = (py - s.H / 2) / v.k + v.cy;
    const zf = zoomFactor(v.k, s.kFit);
    if (Math.hypot(wx, wy) * v.k <= sunRadius(zf)) return 0;
    const reach = 30 / v.k;
    const c0 = Math.floor((wx - reach) / L.cell), c1 = Math.floor((wx + reach) / L.cell);
    const r0 = Math.floor((wy - reach) / L.cell), r1 = Math.floor((wy + reach) / L.cell);
    let best = -1, bestD = Infinity;
    for (let cx = c0; cx <= c1; cx++) for (let cy = r0; cy <= r1; cy++) {
      for (const i of L.grid.get(cx * 100003 + cy) ?? []) {
        if (i === 0 || props.current.hidden[relOf(g, i)]) continue;
        const rad = L.size[i] * zf;
        const d = Math.hypot((L.x[i] - wx) * v.k, (L.y[i] - wy) * v.k);
        // favour the bigger planet when small ones crowd around it
        if (d <= Math.max(7, rad + 5) && d - 1.6 * rad < bestD) { best = i; bestD = d - 1.6 * rad; }
      }
    }
    return best;
  };

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
        if (i !== s.hover) { s.hover = i; hoverChanged(); }
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
      if (p && moved < 6 && pts.size === 0) { const i = hit(p.x, p.y); onSelRef.current(i > 0 ? i : -1); }
    };
    const wheel = (e: WheelEvent) => { e.preventDefault(); const p = local(e); zoomAt(p.x, p.y, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0018))); };
    const leave = () => { if (s.hover >= 0) { s.hover = -1; hoverChanged(); } setTip(null); };
    el.addEventListener("pointerdown", down); el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    el.addEventListener("pointerleave", leave); el.addEventListener("wheel", wheel, { passive: false });
    return () => {
      el.removeEventListener("pointerdown", down); el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      el.removeEventListener("pointerleave", leave); el.removeEventListener("wheel", wheel);
    };
  }, [L]);

  const zoomBy = (f: number) => { const s = st.current; zoomAt(s.W / 2, s.H / 2, f); };
  const reset = () => {
    const s = st.current, from = { ...s.view }, to = fitView(L, s.W, s.H);
    animate(500, (u) => {
      const e = 1 - (1 - u) ** 3;
      s.view = { k: from.k + (to.k - from.k) * e, cx: from.cx * (1 - e), cy: from.cy * (1 - e) };
    }, true);
  };

  return (
    <div class="o-sky" ref={box}>
      <canvas ref={cv} role="img" aria-label={`${fmtFull(L.n - 1)} models built on ${g.root.id}, arranged by generation and kind`} />
      <div class="g-zoom">
        <button aria-label="Zoom in" onClick={() => zoomBy(1.6)}>+</button>
        <button aria-label="Zoom out" onClick={() => zoomBy(1 / 1.6)}>−</button>
        <button aria-label="Show everything" onClick={reset}>⤢</button>
      </div>
      {tip && tip.i !== sel && (
        <div class="g-tip" style={{ left: Math.min(tip.x, (st.current.W || 9999) - 260), top: tip.y }}>
          <b>{tip.i === 0 ? g.root.id : g.nodes.id[tip.i]}</b>
          <span>
            {tip.i === 0 ? "the base model" : `${REL[relOf(g, tip.i)].one}, ${ORD[L.depth[tip.i]]} generation`}, {fmt(g.nodes.dl30[tip.i])} downloads a month
            {L.sub[tip.i] > 1 ? `, ${fmtFull(L.sub[tip.i] - 1)} built on it` : ""}
          </span>
        </div>
      )}
    </div>
  );
}

async function shareImage(g: GalaxyData, L: Layout) {
  await Promise.all(["600 60px 'Fredoka'", "500 20px 'IBM Plex Mono'", "600 14px 'Source Sans 3'"].map((f) => document.fonts.load(f)));
  const W = 1600, H = 900, c = document.createElement("canvas");
  c.width = W; c.height = H;
  const x = c.getContext("2d")!;
  const k = (H / 2 - 20) / L.extent;
  draw(x, W, H, { k, cx: -(1090 - W / 2) / k, cy: 0 }, g, L, { p: 1, hidden: [false, false, false, false], hover: -1, sel: -1, kFit: k, labels: 14 });
  const fade = x.createLinearGradient(0, 0, 640, 0);
  fade.addColorStop(0, "rgba(251,250,245,1)"); fade.addColorStop(0.8, "rgba(251,250,245,0.92)"); fade.addColorStop(1, "rgba(251,250,245,0)");
  x.fillStyle = fade; x.fillRect(0, 0, 640, H);
  const text = (t: string, tx: number, ty: number, font: string, color: string, max = 520) => {
    x.font = font; x.fillStyle = color; x.textBaseline = "alphabetic";
    if (x.measureText(t).width > max) { while (t.length > 3 && x.measureText(t + "…").width > max) t = t.slice(0, -1); t += "…"; }
    x.fillText(t, tx, ty);
  };
  x.fillStyle = INK; x.beginPath(); x.roundRect(70, 70, 56, 56, 14); x.fill();
  x.fillStyle = SUN; x.beginPath(); x.roundRect(64, 64, 56, 56, 14); x.fill(); x.lineWidth = 4; x.strokeStyle = INK; x.stroke();
  x.beginPath(); x.lineWidth = 5; x.lineJoin = "round"; x.lineCap = "round";
  x.moveTo(74, 94); x.lineTo(84, 94); x.lineTo(90, 78); x.lineTo(100, 108); x.lineTo(106, 94); x.lineTo(112, 94); x.stroke();
  text("Model Pulse Galaxy", 138, 104, "600 32px 'Fredoka'", INK);
  const [org, name] = g.root.id.includes("/") ? [g.root.id.split("/")[0], short(g.root.id)] : ["", g.root.id];
  const big = name.length > 18 ? 50 : 64;
  text(org ? org + "/" : "", 66, 228, "500 24px 'IBM Plex Mono'", MUTED);
  x.font = `600 ${big}px 'Fredoka'`;
  const nw = Math.min(540, x.measureText(name).width + 28);
  x.fillStyle = SUN; x.beginPath(); x.roundRect(58, 246, nw, big + 20, 12); x.fill();
  text(name, 72, 246 + big + 2, `600 ${big}px 'Fredoka'`, INK, 510);
  text(fmtFull(g.total), 66, 432, "600 72px 'Fredoka'", INK);
  text("models built on it", 68, 470, "500 24px 'IBM Plex Mono'", MUTED);
  let ly = 560;
  for (const s of L.sectors) {
    x.fillStyle = REL[s.rel].color; x.beginPath(); x.arc(76, ly - 8, 9, 0, TAU); x.fill(); x.lineWidth = 2; x.strokeStyle = INK; x.stroke();
    text(`${REL[s.rel].label}  ${fmtFull(L.byRel[s.rel].length)}`, 98, ly, "500 24px 'IBM Plex Mono'", INK);
    ly += 42;
  }
  text("modelpulse.ifsp.dev", 66, H - 50, "500 22px 'IBM Plex Mono'", MUTED);
  return new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/png"));
}

function TypeBar({ counts }: { counts: number[] }) {
  const total = counts.reduce((s, v) => s + v, 0) || 1;
  return (
    <span class="o-bar" aria-hidden="true">
      {SECTOR_ORDER.map((r) => counts[r] > 0 && <i key={r} style={{ width: `${(counts[r] / total) * 100}%`, background: REL[r].color }} />)}
    </span>
  );
}

function Entry() {
  const [fams, setFams] = useState<Fam[]>([]);
  useEffect(() => {
    document.title = "Model galaxies: every model built on Llama, Qwen, FLUX and more · Model Pulse";
    get<Fam[]>("/api/galaxies").then((r) => setFams(r.slice(0, 16))).catch(() => {});
  }, []);
  return (
    <>
      <div class="wrap w-entry g-entry">
        <h1><Logo size={72} />Model Pulse <span class="hl">Galaxy</span></h1>
        <p class="lede">Every model built on a base model, laid out like a solar system: one orbit per generation, one sector for each kind of derivative, and the most downloaded as the biggest planets.</p>
        <div class="g-search">
          <Search big placeholder="A base model, e.g. meta-llama/Llama-3.1-8B" onPick={(id) => navigate({ view: "galaxy", model: id })} />
        </div>
      </div>
      {fams.length > 0 && (
        <section class="wrap g-fams">
          <h2>The biggest galaxies</h2>
          <div class="g-grid">
            {fams.map((r) => (
              <a key={r.id} class="g-fam" href={hrefOf({ view: "galaxy", model: r.id })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: r.id }); }}>
                <span class="o">{r.id.split("/")[0]}/</span>
                <span class="nm">{short(r.id)}</span>
                <TypeBar counts={[r.n_quantized, r.n_finetune, r.n_adapter, r.n_merge]} />
                <span class="c"><b>{fmtFull(r.fam_members)}</b> models, {fmt(r.fam_dl30)} downloads a month</span>
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
  const [hoverRow, setHoverRow] = useState(-1);
  const [fly, setFly] = useState<{ i: number; n: number } | null>(null);
  const [q, setQ] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!model) return;
    document.title = `${model} galaxy: every model built on it · Model Pulse`;
    setG(null); setErr(null); setSel(-1); setQ("");
    get<GalaxyData>(`/api/galaxy/${model}`)
      .then((d) => { setG(d); document.title = `${d.root.id} galaxy: ${d.total.toLocaleString("en")} models built on it · Model Pulse`; })
      .catch((e) => setErr(e.message));
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
  // who builds on this model the most, other than its own author
  const builders = useMemo(() => {
    if (!g) return [];
    const own = g.root.id.split("/")[0], m = new Map<string, { n: number; dl: number }>();
    g.nodes.id.forEach((id, i) => {
      if (!i) return;
      const a = id.split("/")[0];
      if (a === own) return;
      const r = m.get(a) ?? { n: 0, dl: 0 };
      r.n++; r.dl += g.nodes.dl30[i] || 0; m.set(a, r);
    });
    return [...m.entries()].sort((a, b) => b[1].dl - a[1].dl).slice(0, 6);
  }, [g]);

  if (!model) return <Entry />;
  if (err) return <div class="wrap err"><h1>No galaxy to show</h1><p>{err}</p></div>;

  const root = g?.root;
  const [org, name] = model.includes("/") ? [model.split("/")[0], short(model)] : ["", model];
  const pick = (i: number) => { setSel(i); setQ(""); if (i > 0) setFly({ i, n: Date.now() }); };
  const url = shareUrl({ view: "galaxy", model: root?.id ?? model });
  const post = root ? `${fmtFull(g!.total)} models are built on ${root.id}. Here is its whole galaxy:` : "";
  const top = g?.lineage.length ? g.lineage[g.lineage.length - 1] : null;
  const typeCounts = L ? [0, 1, 2, 3].map((r) => L.byRel[r].length) : [0, 0, 0, 0];
  const topList = L ? Array.from(L.order).filter((i) => i > 0).slice(0, 12) : [];
  const kind = (i: number) => REL[relOf(g!, i)];

  return (
    <div class="galaxy">
      <div class="wrap g-head">
        <div class="crumbs">
          <a class="chip" href={hrefOf({ view: "galaxy" })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy" }); }}>All galaxies</a>
          {top && <a class="chip chip-hot" href={hrefOf({ view: "galaxy", model: top })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: top }); }}>Part of the {short(top)} galaxy</a>}
          <a class="chip" href={hrefOf({ model })} onClick={(e) => { e.preventDefault(); navigate({ model }); }}>Download history</a>
        </div>
        <h1 class="model-name">{org && <span class="org">{org}/</span>}<span class="hl">{name}</span></h1>
        <p class="g-lede">
          {!g ? "Mapping every model built on it…"
            : g.total ? <><b>{fmtFull(g.total)}</b> models are built on {name}, directly or through other derivatives. Together with the original they were downloaded <b>{fmt(root!.fam_dl30)}</b> times in the last 30 days.</>
              : <>No models on the Hub are built on {name} yet.</>}
        </p>
      </div>

      <div class="wrap o-layout">
        <div class="o-stage">
          {g && L && g.total > 0 ? (
            <Orrery g={g} L={L} hidden={hidden} sel={sel} hoverExt={hoverRow} onSel={setSel} flyTo={fly} />
          ) : (
            <div class="o-sky o-empty">{g ? <span>Nothing orbits this model yet.</span> : <span class="g-loading">Mapping the galaxy…</span>}</div>
          )}
          <ul class="o-key">
            <li><span class="k-sun" aria-hidden="true" />{name} in the center</li>
            <li><span class="k-ring" aria-hidden="true" />one orbit per generation</li>
            <li><span class="k-size" aria-hidden="true" />bigger planet, more downloads</li>
            <li><span class="k-line" aria-hidden="true" />line to the model it was made from</li>
          </ul>
          {g && L && g.total > 0 && (
            <div class="g-foot">
              {L.n - 1 < g.total && <p class="muted">Showing the {fmtFull(L.n - 1)} most downloaded of {fmtFull(g.total)} models.</p>}
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
                <LikeCta />
              </div>
            </div>
          )}
        </div>

        {g && L && g.total > 0 && (
          <aside class="o-panel">
            <div class="g-find">
              <input value={q} onInput={(e) => setQ((e.target as HTMLInputElement).value)} placeholder="Find a model in this galaxy" aria-label="Find a model in this galaxy" spellcheck={false}
                onKeyDown={(e) => { if (e.key === "Enter" && found.length) pick(found[0]); if (e.key === "Escape") setQ(""); }} />
              {found.length > 0 && (
                <ul class="g-found">
                  {found.map((i) => <li key={i}><button onClick={() => pick(i)}><span>{g.nodes.id[i]}</span><small>{fmt(g.nodes.dl30[i])}/mo</small></button></li>)}
                </ul>
              )}
            </div>

            {sel > 0 && (
              <div class="o-sel">
                <button class="x" aria-label="Close" onClick={() => setSel(-1)}>×</button>
                <a class="id" href={hrefOf({ model: g.nodes.id[sel] })} onClick={(e) => { e.preventDefault(); navigate({ model: g.nodes.id[sel] }); }}>{g.nodes.id[sel]}</a>
                <span class="g-rel"><i style={{ background: kind(sel).color }} />{kind(sel).of} {short(g.nodes.id[g.nodes.parent[sel]])}, {ORD[L.depth[sel]]} generation</span>
                <span class="n"><b>{fmtFull(g.nodes.dl30[sel])}</b> downloads in the last 30 days</span>
                {L.sub[sel] > 1 && <span class="n"><b>{fmtFull(L.sub[sel] - 1)}</b> models built on it</span>}
                <div class="acts">
                  <a class="btn primary" href={hrefOf({ model: g.nodes.id[sel] })} onClick={(e) => { e.preventDefault(); navigate({ model: g.nodes.id[sel] }); }}>Download history</a>
                  {L.sub[sel] > 1 && <a class="btn" href={hrefOf({ view: "galaxy", model: g.nodes.id[sel] })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy", model: g.nodes.id[sel] }); }}>Its own galaxy</a>}
                </div>
              </div>
            )}

            <section>
              <h2>By kind</h2>
              <p class="o-note">All generations. Click to show or hide.</p>
              <div class="o-kinds" role="group" aria-label="Show or hide kinds of derivatives">
                {SECTOR_ORDER.filter((r) => typeCounts[r] > 0).map((r) => (
                  <button key={r} aria-pressed={!hidden[r]} onClick={() => setHidden(hidden.map((h, j) => (j === r ? !h : h)))}>
                    <i style={{ background: REL[r].color }} />
                    <span>{REL[r].label}</span>
                    <b>{fmtFull(typeCounts[r])}</b>
                    <span class="share"><span style={{ width: `${(typeCounts[r] / (L.n - 1)) * 100}%`, background: REL[r].color }} /></span>
                  </button>
                ))}
              </div>
              <p class="o-gens">
                {L.gens.slice(1).map((c, d) => (c ? <span key={d}><b>{fmtFull(c)}</b> {ORD[d + 1]} generation</span> : null))}
              </p>
            </section>

            <section>
              <h2>Most downloaded</h2>
              <ol class="o-top">
                {topList.map((i) => (
                  <li key={i}>
                    <button class={sel === i ? "on" : ""} onClick={() => pick(i)} onMouseEnter={() => setHoverRow(i)} onMouseLeave={() => setHoverRow(-1)} onFocus={() => setHoverRow(i)} onBlur={() => setHoverRow(-1)}>
                      <i style={{ background: kind(i).color }} />
                      <span class="nm">{g.nodes.id[i]}</span>
                      <span class="v">{fmt(g.nodes.dl30[i])}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </section>

            {builders.length > 0 && (
              <section>
                <h2>Who builds on it</h2>
                <ol class="o-top">
                  {builders.map(([a, r]) => (
                    <li key={a}>
                      <a href={hrefOf({ author: a })} onClick={(e) => { e.preventDefault(); navigate({ author: a }); }}>
                        <span class="nm">{a}</span>
                        <span class="v">{fmtFull(r.n)} {r.n === 1 ? "model" : "models"}</span>
                      </a>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </aside>
        )}
      </div>

    </div>
  );
}
