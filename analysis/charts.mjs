// Article charts from analysis.json. Run from a dir that has the Plex TTFs and @resvg/resvg-js installed.
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync, mkdirSync } from "fs";

const [, , analysisPath, outDir, hubPath] = process.argv;
const A = JSON.parse(readFileSync(analysisPath, "utf8"));
mkdirSync(outDir, { recursive: true });

const INK = "#1B1B1F", PAPER = "#ECE9E2", SURFACE = "#FBFAF5", MUTED = "#6E6C66", RULE = "#D9D5CA", MARK = "#FFD21E";
const C = ["#3B6FF5", "#FF8A1F", "#2F8F5B", "#A35BF0", "#8A6D00", "#E5484D", "#5C6AC4"];
const MONO = `font-family="IBM Plex Mono"`;
const W = 1200, H = 675;
const font = { fontFiles: ["fredoka-600.ttf", "ibm-plex-mono-400.ttf", "ibm-plex-mono-500.ttf", "ibm-plex-mono-600.ttf",
  "source-sans-3-400.ttf", "source-sans-3-600.ttf", "source-sans-3-700.ttf"], loadSystemFonts: false, defaultFontFamily: "Source Sans 3 ExtraLight" };
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
const human = (v) => (v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : `${Math.round(v / 1e3)}K`);
const mlabel = (m) => new Date(m + "T00:00:00Z").toLocaleString("en", { month: "short", timeZone: "UTC" }) + (m.slice(5, 7) === "01" || m === A.months[0].m.slice(0, 10) ? ` ${m.slice(0, 4)}` : "");
// before March 2025 the Hub had no all-time counter: those months come from the 30-day count and are shaded
const EST = new Set(A.months.filter((r) => !r.exact).map((r) => r.m.slice(0, 10)));
function estBand(xs, x, T, B) {
  const last = xs.reduce((k, m, i) => (EST.has(m) ? i : k), -1);
  if (last < 0) return "";
  const x1 = last === xs.length - 1 ? x(last) : (x(last) + x(last + 1)) / 2;
  return `<rect x="${x(0)}" y="${T - 14}" width="${x1 - x(0)}" height="${B - T + 14}" fill="${RULE}" opacity="0.45"/>
    <text x="${x(0) + 8}" y="${T + 2}" ${MONO} font-size="13" fill="${MUTED}">estimated from 30-day counts</text>`;
}

function frame(title, subtitle, body, source) {
  source ??= "Model Pulse, from daily snapshots of cfahlgren1/hub-stats";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="Source Sans 3 ExtraLight">
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  <text x="44" y="70" font-family="Fredoka Light" font-weight="600" font-size="38" letter-spacing="-0.5" fill="${INK}">${esc(title)}</text>
  <text x="46" y="106" font-size="21" font-weight="400" fill="${MUTED}">${esc(subtitle)}</text>
  <rect x="${44 + 6}" y="${136 + 6}" width="${W - 88}" height="${H - 136 - 66}" rx="18" fill="${INK}"/>
  <rect x="44" y="136" width="${W - 88}" height="${H - 136 - 66}" rx="18" fill="${SURFACE}" stroke="${INK}" stroke-width="3"/>
  ${body}
  <g transform="translate(44,${H - 46})"><g transform="scale(0.8)"><rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="${MARK}" stroke="${INK}" stroke-width="3"/><path d="M5.5 17h4.5l3-8 5 15 3-7h5.5" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g></g>
  <text x="80" y="${H - 26}" ${MONO} font-size="14" fill="${MUTED}">${esc(source)}</text>
</svg>`;
}

function save(name, svg) {
  writeFileSync(`${outDir}/${name}.png`, new Resvg(svg, { font, fitTo: { mode: "width", value: W } }).render().asPng());
  console.log(name);
}

// generic multi-line chart over months; series: [{label, color, values: {m: v}}]
function lines(name, title, subtitle, series, { fmt = pct, yMax, labelRight = true, area = false } = {}) {
  const months = A.months.map((r) => r.m.slice(0, 10));
  const L = 110, R = labelRight ? 262 : 70, T = 172, B = 538;
  const raw = Math.max(...series.flatMap((s) => months.map((m) => s.values[m] ?? 0))) * 1.08;
  const step = [0.05, 0.1, 0.2, 0.25].find((st) => raw / st <= 5) ?? 0.25;
  const max = yMax ?? Math.ceil(raw / step) * step;
  const x = (i) => L + (i / (months.length - 1)) * (W - L - R);
  const y = (v) => B - (v / max) * (B - T);
  const ticks = yMax ? [0, 0.25, 0.5, 0.75, 1].map((f) => f * max) : Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const grid = ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5" stroke-dasharray="5 6"/>
    <text x="${L - 12}" y="${y(v) + 5}" text-anchor="end" ${MONO} font-size="14" fill="${MUTED}">${fmt(v)}</text>`).join("");
  const xt = months.map((m, i) => (i % 3 === 0 || i === months.length - 1) ? `<text x="${x(i)}" y="${B + 28}" text-anchor="middle" ${MONO} font-size="14" fill="${MUTED}">${mlabel(m)}</text>` : "").join("");
  const gaps = estBand(months, x, T, B);
  const labels = [];
  const paths = series.map((s) => {
    let d = "", pen = false;
    months.forEach((m, i) => {
      const v = s.values[m];
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `; pen = true;
    });
    const last = [...months].reverse().find((m) => s.values[m] != null);
    labels.push({ y: y(s.values[last]), s });
    const w = s.width ?? 4;
    return `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w + 3.5}" stroke-linejoin="round" stroke-linecap="round"/>
      <path d="${d}" fill="none" stroke="${s.color}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");
  // de-overlap right labels
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 24) labels[i].y = labels[i - 1].y + 24;
  const over = labels.length ? labels[labels.length - 1].y - (B + 6) : 0;
  if (over > 0) labels.forEach((l) => (l.y -= over));
  const lab = labelRight ? labels.map(({ y: ly, s }) => `<text x="${W - R + 14}" y="${ly + 6}" font-size="18" font-weight="600" fill="${s.color}">${esc(s.label)} <tspan fill="${MUTED}" font-weight="400" ${MONO} font-size="16">${fmt(s.values[[...months].reverse().find((m) => s.values[m] != null)])}</tspan></text>`).join("") : "";
  save(name, frame(title, subtitle, gaps + grid + paths + xt + lab));
}

const R = JSON.parse(readFileSync(analysisPath.replace("analysis.json", "analysis_repos.json"), "utf8"));
const R2 = JSON.parse(readFileSync(analysisPath.replace("analysis.json", "analysis_repos2.json"), "utf8"));
const monthTick = (m, i, all) => {
  const mon = new Date(m + "T00:00:00Z").toLocaleString("en", { month: "short", timeZone: "UTC" });
  return i === 0 || m.slice(5, 7) === "01" ? `${mon} ${m.slice(0, 4)}` : mon;
};

// lines over any x axis; series: [{label, color, values: [] aligned with xs, width, dash}]; log: tick values for a log2 y axis
function xyLines(name, title, subtitle, xs, series, { fmt = pct, log, yMax, every = 3, xlabel = (x) => x, source, band = false } = {}) {
  const L = 110, Rr = 262, T = 172, B = 538;
  const all = series.flatMap((s) => s.values.filter((v) => v != null));
  const x = (i) => L + (i / (xs.length - 1)) * (W - L - Rr);
  let y, ticks;
  if (log) {
    const lo = Math.log2(Math.min(log[0], ...all)), hi = Math.log2(Math.max(log.at(-1), ...all));
    y = (v) => B - ((Math.log2(v) - lo) / (hi - lo)) * (B - T); ticks = log;
  } else {
    const raw = yMax ?? Math.max(...all) * 1.05;
    const step = [0.02, 0.05, 0.1, 0.2, 0.25].find((st) => raw / st <= 6) ?? 0.25;
    const max = yMax ?? Math.ceil(raw / step) * step;
    y = (v) => B - (v / max) * (B - T); ticks = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
  }
  const grid = ticks.map((v) => `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5" stroke-dasharray="5 6"/>
    <text x="${L - 12}" y="${y(v) + 5}" text-anchor="end" ${MONO} font-size="14" fill="${MUTED}">${fmt(v)}</text>`).join("");
  const xt = xs.map((m, i) => (i % every === 0 || i === xs.length - 1) ? `<text x="${x(i)}" y="${B + 28}" text-anchor="middle" ${MONO} font-size="14" fill="${MUTED}">${xlabel(m, i, xs)}</text>` : "").join("");
  const labels = [];
  const paths = series.map((s) => {
    const d = s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    labels.push({ y: y(s.values.at(-1)), s });
    const w = s.width ?? 4;
    if (s.dash) return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${w}" stroke-dasharray="8 7" stroke-linejoin="round" stroke-linecap="round"/>`;
    return `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w + 3.5}" stroke-linejoin="round" stroke-linecap="round"/>
      <path d="${d}" fill="none" stroke="${s.color}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 24) labels[i].y = labels[i - 1].y + 24;
  const over = labels.length ? labels.at(-1).y - (B + 6) : 0;
  if (over > 0) labels.forEach((l) => (l.y -= over));
  const lab = labels.map(({ y: ly, s }) => `<text x="${W - Rr + 14}" y="${ly + 6}" font-size="18" font-weight="600" fill="${s.color}">${esc(s.label)} <tspan fill="${MUTED}" font-weight="400" ${MONO} font-size="16">${fmt(s.values.at(-1))}</tspan></text>`).join("");
  save(name, frame(title, subtitle, (band ? estBand(xs, x, T, B) : "") + grid + paths + xt + lab, source));
}

// stacked bars over any x axis; stacks: [{label, color, values: [] aligned with xs}]
function stackedBars(name, title, subtitle, xs, stacks, { fmtY = (v) => (v ? human(v) : "0"), every = 3, xlabel = (x) => x, note = "", source, legend = true } = {}) {
  const L = 110, Rr = 70, T = legend && stacks.length > 1 ? 214 : 190, B = 530, bw = (W - L - Rr) / xs.length;
  const tot = xs.map((_, i) => stacks.reduce((a, s) => a + (s.values[i] ?? 0), 0));
  const raw = Math.max(...tot) * 1.05;
  const mag = 10 ** Math.floor(Math.log10(raw / 4)), step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((st) => raw / st <= 5);
  const max = Math.ceil(raw / step) * step;
  const y = (v) => B - (v / max) * (B - T);
  const bars = xs.map((_, i) => { let acc = 0; return stacks.map((s) => {
    const v = s.values[i] ?? 0, y0 = y(acc), y1 = y(acc + v); acc += v;
    return v ? `<rect x="${(L + i * bw + 2).toFixed(1)}" y="${y1.toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${(y0 - y1).toFixed(1)}" fill="${s.color}" stroke="${INK}" stroke-width="1.6"/>` : "";
  }).join(""); }).join("");
  const grid = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step).map((v) => `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5" stroke-dasharray="5 6"/>
    <text x="${L - 12}" y="${y(v) + 5}" text-anchor="end" ${MONO} font-size="14" fill="${MUTED}">${fmtY(v)}</text>`).join("");
  const xt = xs.map((m, i) => (i % every === 0 || i === xs.length - 1) ? `<text x="${L + i * bw + bw / 2}" y="${B + 26}" text-anchor="middle" ${MONO} font-size="14" fill="${MUTED}">${xlabel(m, i, xs)}</text>` : "").join("");
  const leg = legend && stacks.length > 1 ? stacks.map((s, k) => `<g transform="translate(${L + k * 170},168)"><rect width="16" height="16" rx="4" fill="${s.color}" stroke="${INK}" stroke-width="2"/><text x="24" y="13" font-size="16" fill="${INK}">${esc(s.label)}</text></g>`).join("") : "";
  save(name, frame(title, subtitle, grid + `<line x1="${L}" x2="${W - Rr}" y1="${B}" y2="${B}" stroke="${INK}" stroke-width="3"/>` + bars + xt + leg + note, source));
}

const byMonth = (rows, key, val, filter = () => true) => {
  const o = {};
  rows.filter(filter).forEach((r) => { (o[r[key]] ??= {})[r.m.slice(0, 10)] = Number(r[val]); });
  return o;
};

// 2. Qwen vs Llama
const tg = byMonth(A.textgen_orgs, "author", "share");
lines("02-text-orgs", "Qwen became the default open LLM publisher",
  "Share of text and vision-language model downloads, by publisher (original repos only)",
  [["Qwen", "Qwen", C[0]], ["meta-llama", "Meta Llama", C[1]], ["google", "Google", C[2]], ["nvidia", "NVIDIA", C[3]],
   ["deepseek-ai", "DeepSeek", C[4]], ["openai", "OpenAI", C[5]]].map(([k, label, color]) => ({ label, color, values: tg[k] ?? {} })));

// 3. derivatives
const dv = {}; ["derived", "quantized", "finetune", "gguf"].forEach((k) => (dv[k] = Object.fromEntries(A.derivative_share.map((r) => [r.m.slice(0, 10), Number(r[k])]))));
lines("03-derivatives", "Derivatives now take 43% of all downloads",
  "Share of monthly downloads going to models built on another model",
  [{ label: "All derivatives", color: C[0], values: dv.derived, width: 5 }, { label: "Quantized", color: C[1], values: dv.quantized },
   { label: "Fine-tuned", color: C[2], values: dv.finetune }, { label: "GGUF files", color: C[3], values: dv.gguf }]);

// 5. concentration
const cc = {}; ["top10", "top100", "top1000"].forEach((k) => (cc[k] = Object.fromEntries(A.concentration.map((r) => [r.m.slice(0, 10), Number(r[k])]))));
lines("05-concentration", "The top of the Hub is losing its grip",
  "Share of monthly downloads that go to the N most downloaded models",
  [{ label: "Top 1,000", color: C[2], values: cc.top1000 }, { label: "Top 100", color: C[0], values: cc.top100, width: 5 },
   { label: "Top 10", color: C[1], values: cc.top10 }], { yMax: 1 });

// 6. model size: growth of each size band, indexed, log scale (a stacked share hides it: every band grew)
{
  // exact months only: split into small size bands, the 30-day estimates are too noisy (one counter jump on
  // Llama-3.1-405B in Oct 2024 alone would multiply the 100B+ band six times)
  const rows = R.size_buckets.map((r) => ({ ...r, m: r.m.slice(0, 10) })).filter((r) => !EST.has(r.m));
  const bands = { small: ["lt1", "b1_4", "b4_10"], b10_35: ["b10_35"], b35_100: ["b35_100"], ge100: ["ge100"] };
  const abs = rows.map((r) => Object.fromEntries(Object.entries(bands).map(([k, ks]) => [k, ks.reduce((a, c) => a + r[c] * r.dl, 0)]).concat([["all", r.dl]])));
  const roll = (i, k) => (abs[i - 2][k] + abs[i - 1][k] + abs[i][k]) / 3;
  const xs = rows.slice(2).map((r) => r.m);
  const idx = (k) => xs.map((_, j) => roll(j + 2, k) / roll(2, k));
  const series = [
    { label: "100B and up", color: C[5], values: idx("ge100"), width: 5 },
    { label: "10B to 35B", color: C[1], values: idx("b10_35"), width: 5 },
    { label: "All LLMs", color: INK, values: idx("all"), width: 2.5, dash: true },
    { label: "Under 10B", color: C[0], values: idx("small") },
    { label: "35B to 100B", color: C[4], values: idx("b35_100") },
  ];
  const big = series[0].values.at(-1), small = series[3].values.at(-1);
  xyLines("06-model-size", `Downloads of 100B+ models grew ${Math.round(big)}x; small models ${small.toFixed(1)}x`,
    `Monthly text-generation downloads by model size, indexed to ${monthTick(rows[0].m, 1)}–${monthTick(rows[2].m, 1)} ${rows[2].m.slice(0, 4)} (3-month average, log scale)`,
    xs, series, { log: [1, 2, 4, 8, 16], fmt: (v) => `${v >= 9.95 ? Math.round(v) : v.toFixed(1)}x`, xlabel: monthTick });
}

// 4. quantizers dumbbell
{
  const want = ["unsloth", "mradermacher", "lmstudio-community", "bartowski", "MaziyarPanahi", "mlx-community", "ggml-org", "TheBloke"];
  const get = (a, m) => Number((A.quantizers.find((r) => r.author === a && r.m.startsWith(m)) || {}).dl || 0);
  const rows = want.map((a) => ({ a, v0: get(a, "2025-03"), v1: get(a, "2026-09"), n: (A.quantizers.find((r) => r.author === a && r.m.startsWith("2026-09")) || {}).models }))
    .sort((p, q) => q.v1 - p.v1);
  const L = 300, R = 150, T = 178, rowH = 48, max = Math.max(...rows.flatMap((r) => [r.v0, r.v1])) * 1.08;
  const x = (v) => L + (v / max) * (W - L - R);
  const body = rows.map((r, i) => {
    const yy = T + i * rowH;
    const up = r.v1 >= r.v0, col = up ? C[0] : C[5];
    return `<text x="${L - 22}" y="${yy + 7}" text-anchor="end" font-size="21" font-weight="700" fill="${INK}">${esc(r.a)}</text>
      <line x1="${x(r.v0)}" x2="${x(r.v1)}" y1="${yy}" y2="${yy}" stroke="${INK}" stroke-width="11" stroke-linecap="round"/>
      <line x1="${x(r.v0)}" x2="${x(r.v1)}" y1="${yy}" y2="${yy}" stroke="${col}" stroke-width="6" stroke-linecap="round"/>
      <circle cx="${x(r.v0)}" cy="${yy}" r="8" fill="${SURFACE}" stroke="${INK}" stroke-width="3"/>
      <circle cx="${x(r.v1)}" cy="${yy}" r="11" fill="${col}" stroke="${INK}" stroke-width="3"/>
      <text x="${Math.max(x(r.v1), x(r.v0)) + 20}" y="${yy + 6}" ${MONO} font-size="16" fill="${MUTED}">${human(r.v0)} to <tspan fill="${INK}" font-weight="700">${human(r.v1)}</tspan></text>`;
  }).join("");
  const ly = T + rows.length * rowH - 4;
  const legend = `<circle cx="${L}" cy="${ly}" r="7" fill="${SURFACE}" stroke="${INK}" stroke-width="3"/>
    <text x="${L + 16}" y="${ly + 5}" ${MONO} font-size="14" fill="${MUTED}">March 2025</text>
    <circle cx="${L + 150}" cy="${ly}" r="8" fill="${C[0]}" stroke="${INK}" stroke-width="3"/>
    <text x="${L + 166}" y="${ly + 5}" ${MONO} font-size="14" fill="${MUTED}">September 2026, monthly downloads</text>`;
  save("04-quantizers", frame("Quantizers became some of the Hub's biggest publishers",
    "Monthly downloads of repackaged models, March 2025 vs September 2026", body + legend));
}

// 7. launch curve
{
  const v = A.lifecycle.mean_weekly_share;
  const L = 110, R = 76, T = 196, B = 536, bw = (W - L - R) / v.length;
  const max = Math.max(...v) * 1.15;
  const y = (s) => B - (s / max) * (B - T);
  const bars = v.map((s, i) => `<rect x="${L + i * bw + 3}" y="${y(s)}" width="${bw - 6}" height="${B - y(s)}" rx="4" fill="${i < 2 ? C[1] : C[0]}" stroke="${INK}" stroke-width="2.5"/>`).join("");
  const xt = [0, 4, 8, 13, 17, 21, 25].map((i) => `<text x="${L + i * bw + bw / 2}" y="${B + 28}" text-anchor="middle" ${MONO} font-size="14" fill="${MUTED}">${i === 0 ? "launch week" : `week ${i}`}</text>`).join("");
  const grid = [0, 0.02, 0.04, 0.06, 0.08].filter((s) => s < max).map((s) => `<line x1="${L}" x2="${W - R}" y1="${y(s)}" y2="${y(s)}" stroke="${RULE}" stroke-width="1.5" stroke-dasharray="5 6"/><text x="${L - 12}" y="${y(s) + 5}" text-anchor="end" ${MONO} font-size="14" fill="${MUTED}">${pct(s)}</text>`).join("");
  const note = `<text x="${W - R}" y="${T - 18}" text-anchor="end" font-size="18" fill="${INK}"><tspan font-weight="700">${pct(A.lifecycle.peak_after_month3)}</tspan> of these models peaked after their third month</text>`;
  save("07-launch-curve", frame("Launches spike for two weeks, then settle into a plateau",
    `Average weekly share of first-six-month downloads, ${A.lifecycle.models.toLocaleString("en")} models launched since Mar 2025`,
    grid + bars + xt + note));
}

// 8. likes per download
{
  const rows = A.likes_per_100k.map((r) => ({ t: r.pipeline_tag.replace(/-/g, " "), v: Number(r.likes_per_100k) }));
  const pick = [...rows.slice(0, 5), ...rows.slice(-5)];
  const L = 330, R = 150, T = 166, rowH = 39, max = Math.max(...pick.map((r) => r.v)) * 1.05;
  const x = (v) => L + (v / max) * (W - L - R);
  const body = pick.map((r, i) => {
    const yy = T + i * rowH + (i >= 5 ? 22 : 0);
    return `<text x="${L - 16}" y="${yy + 20}" text-anchor="end" font-size="19" fill="${INK}">${esc(r.t)}</text>
      <rect x="${L}" y="${yy + 4}" width="${Math.max(6, x(r.v) - L)}" height="26" rx="5" fill="${i < 5 ? C[3] : C[2]}" stroke="${INK}" stroke-width="2.5"/>
      <text x="${Math.max(x(r.v), L + 6) + 12}" y="${yy + 23}" ${MONO} font-size="16" font-weight="600" fill="${INK}">${r.v >= 10 ? Math.round(r.v) : r.v.toFixed(1)}</text>`;
  }).join("") + `<line x1="70" x2="${W - 70}" y1="${T + 5 * rowH + 12}" y2="${T + 5 * rowH + 12}" stroke="${INK}" stroke-opacity="0.35" stroke-width="2" stroke-dasharray="6 6"/>`;
  save("08-likes", frame("Likes measure excitement, not use",
    "Likes per 100,000 monthly downloads, by task: the five highest and the five lowest", body));
}

// 1. Hub-wide weekly downloads, stacked by task, outlined bars
if (hubPath) {
  const hub = JSON.parse(readFileSync(hubPath, "utf8"));
  const tags = ["text-generation", "sentence-similarity", "image-text-to-text", "feature-extraction"];
  const LABELS = { "text-generation": "Text generation", "sentence-similarity": "Sentence similarity", "image-text-to-text": "Vision-language", "feature-extraction": "Feature extraction", other: "Everything else" };
  const COL = { "text-generation": C[0], "sentence-similarity": C[1], "image-text-to-text": C[2], "feature-extraction": C[3], other: "#D9D5CA" };
  // each snapshot row is a per-day average since the previous snapshot: spread it over every day of that gap
  const days = [...new Set(hub.day)].sort();
  const prev = new Map(days.map((d, i) => [d, i ? days[i - 1] : null]));
  const weeks = new Map();
  const add = (t, tag, v) => {
    const key = t - ((new Date(t).getUTCDay() + 6) % 7) * 86400000;
    const w = weeks.get(key) ?? {}; w[tag] = (w[tag] ?? 0) + v; weeks.set(key, w);
  };
  hub.day.forEach((d, i) => {
    const t = Date.parse(d + "T00:00:00Z"), p = prev.get(d);
    const gap = p ? Math.max(1, Math.round((t - Date.parse(p + "T00:00:00Z")) / 86400000)) : 1;
    const tag = tags.includes(hub.tag[i]) ? hub.tag[i] : "other";
    for (let k = 0; k < gap; k++) add(t - k * 86400000, tag, hub.dl[i]);
  });
  const ks = [...weeks.keys()].sort((a, b) => a - b).slice(0, -1); // drop the week in progress
  const order = [...tags, "other"];
  const tot = ks.map((k) => order.reduce((a, t) => a + (weeks.get(k)[t] ?? 0), 0));
  const L = 110, R = 70, T = 210, B = 530, bw = (W - L - R) / ks.length;
  const step = 250e6, max = Math.ceil((Math.max(...tot) * 1.05) / step) * step;
  const y = (v) => B - (v / max) * (B - T);
  const bars = ks.map((k, i) => {
    let acc = 0;
    return order.map((t) => {
      const v = weeks.get(k)[t] ?? 0, y0 = y(acc), y1 = y(acc + v); acc += v;
      return `<rect x="${(L + i * bw + 1).toFixed(1)}" y="${y1.toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${(y0 - y1).toFixed(1)}" fill="${COL[t]}" stroke="${INK}" stroke-width="1.2"/>`;
    }).join("");
  }).join("");
  const grid = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step).map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5" stroke-dasharray="5 6"/>
    <text x="${L - 12}" y="${y(v) + 5}" text-anchor="end" ${MONO} font-size="14" fill="${MUTED}">${v ? human(v) : "0"}</text>`).join("");
  const seen = new Set();
  const xt = ks.map((k, i) => { const d = new Date(k), m = d.getUTCMonth(); const key = `${d.getUTCFullYear()}-${m}`;
    if (seen.has(key) || ![0, 3, 6, 9].includes(m)) return ""; seen.add(key);
    return `<text x="${L + i * bw}" y="${B + 26}" ${MONO} font-size="14" fill="${MUTED}">${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} ${String(d.getUTCFullYear()).slice(2)}</text>`; }).join("");
  const legend = order.map((t, k) => `<g transform="translate(${L + k * 196},168)"><rect width="16" height="16" rx="4" fill="${COL[t]}" stroke="${INK}" stroke-width="2"/><text x="24" y="13" font-size="16" fill="${INK}">${LABELS[t]}</text></g>`).join("");
  save("01-hub", frame("The Hub serves ~100M model downloads a day", "Weekly downloads across all public models, by task. Up from ~61M a day a year ago.",
    grid + `<line x1="${L}" x2="${W - R}" y1="${B}" y2="${B}" stroke="${INK}" stroke-width="3"/>` + bars + xt + legend));
}

// 9. robotics datasets created per month
{
  const xs = R.ds_robotics.map((r) => r.m.slice(0, 10)).filter((m) => m >= "2024-07-01" && m <= "2026-09-01");
  const get = (rows, m, k) => Number((rows.find((r) => r.m.startsWith(m)) || {})[k] || 0);
  const last = xs.at(-1), share = get(R.ds_created, last, "robotics") / get(R.ds_created, last, "n");
  const q = R2.robotics_authors, a0 = q[0], a1 = q.at(-2);
  stackedBars("09-robotics", `One in ${Math.round(1 / share)} new datasets is now robot data`,
    `Robotics datasets created per month. Authors per quarter went from ${a0.authors} to ${a1.authors.toLocaleString("en")}.`,
    xs, [{ label: "Robotics datasets", color: C[2], values: xs.map((m) => get(R.ds_robotics, m, "created_n")) }],
    { xlabel: monthTick, fmtY: (v) => v.toLocaleString("en"), legend: false });
}

// 10. what fine-tuners say they trained on
{
  const rows = R2.train_themes, xs = rows.map((r) => String(r.y));
  const sh = (k) => rows.map((r) => r[k] / r.authors);
  xyLines("10-training-data", "Fine-tuners swapped IMDb and SQuAD for reasoning traces",
    "Share of model authors citing each kind of training data, by the year their model was created (2026: Jan–Sep)",
    xs, [{ label: "Classic NLP sets", color: C[0], values: sh("classic_nlp") }, { label: "Speech", color: C[3], values: sh("speech") },
      { label: "Chat instructions", color: C[1], values: sh("chat_sft") }, { label: "Math", color: C[4], values: sh("math") },
      { label: "Reasoning traces", color: C[5], values: sh("reasoning"), width: 5 }], { every: 1 });
}

// 11. new Spaces per month by SDK
{
  const xs = [...new Set(R.sp_new_by_sdk_month.map((r) => r.m.slice(0, 10)))].filter((m) => m >= "2023-01-01" && m <= "2026-09-01").sort();
  const get = (m, sdk) => R.sp_new_by_sdk_month.filter((r) => r.m.startsWith(m) && r.sdk === sdk).reduce((a, r) => a + Number(r.n), 0);
  const sdks = [["gradio", "Gradio", C[1]], ["docker", "Docker", C[0]], ["static", "Static", C[2]], ["streamlit", "Streamlit", C[5]], ["other", "Other", RULE]];
  stackedBars("11-spaces-sdk", "New Spaces swung from Gradio to static sites to Docker",
    "Spaces created per month, by SDK (Spaces that still exist today)",
    xs, sdks.map(([k, label, color]) => ({ label, color, values: xs.map((m) => get(m, k)) })), { xlabel: monthTick });
}

// 12. Spaces created vs likes given, indexed
{
  const tl = R2.sp_total_likes;
  const likes = {};
  for (let i = 1; i < tl.length; i++) {
    const d = (Date.parse(tl[i].day) - Date.parse(tl[i - 1].day)) / 864e5;
    const m = tl[i].day.slice(0, 7) + "-01";
    likes[m] = ((tl[i].likes - tl[i - 1].likes) / d) * 30.4;
  }
  const made = {};
  R.sp_new_by_sdk_month.forEach((r) => { const m = r.m.slice(0, 10); made[m] = (made[m] ?? 0) + Number(r.n); });
  const ms = Object.keys(likes).filter((m) => m <= "2026-09-01").sort();
  const roll = (o, i) => (o[ms[i - 2]] + o[ms[i - 1]] + o[ms[i]]) / 3;
  const xs = ms.slice(2);
  const idx = (o) => xs.map((_, j) => roll(o, j + 2) / roll(o, 2));
  const L1 = idx(likes), M1 = idx(made);
  const yr = (m) => m.slice(0, 4), mon = (m) => monthTick(m, 1);
  xyLines("12-spaces-likes", "More new Spaces than ever, half the likes",
    `Spaces created and likes given per month, indexed to ${mon(ms[0])}–${mon(ms[2])} ${yr(ms[2])} (3-month average, log scale)`,
    xs, [{ label: "New Spaces", color: C[0], values: M1, width: 5 }, { label: "Likes given", color: C[5], values: L1, width: 5 }],
    { log: [0.5, 1, 2, 4], fmt: (v) => `${v.toFixed(1)}x`, xlabel: monthTick });
}
