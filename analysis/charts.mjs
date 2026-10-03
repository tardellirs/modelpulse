// Article charts from analysis.json. Run from a dir that has the Plex TTFs and @resvg/resvg-js installed.
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync, mkdirSync } from "fs";

const [, , analysisPath, outDir] = process.argv;
const A = JSON.parse(readFileSync(analysisPath, "utf8"));
mkdirSync(outDir, { recursive: true });

const INK = "#151833", PAPER = "#F6F7FA", MUTED = "#6A6F8C", RULE = "#E2E5EE", MARK = "#FFD43B";
const C = ["#3B4CF5", "#E8590C", "#0C8A7A", "#B02FB0", "#8A6D00", "#D64545", "#5C6AC4"];
const W = 1200, H = 675;
const font = { fontFiles: ["plex-400.ttf", "plex-600.ttf", "plex-700.ttf"], loadSystemFonts: false, defaultFontFamily: "IBM Plex Sans" };
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
const human = (v) => (v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : `${Math.round(v / 1e3)}K`);
const mlabel = (m) => new Date(m + "T00:00:00Z").toLocaleString("en", { month: "short", timeZone: "UTC" }) + (m.slice(5, 7) === "01" || m === A.months[0].m.slice(0, 10) ? ` ${m.slice(0, 4)}` : "");
const GAP = new Set(["2025-06-01"]); // snapshot gap month in the source; plotted as a break

function frame(title, subtitle, body, source = "Model Pulse, from daily snapshots of cfahlgren1/hub-stats") {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="IBM Plex Sans">
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  <text x="64" y="84" font-weight="700" font-size="40" letter-spacing="-0.5" fill="${INK}">${esc(title)}</text>
  <text x="64" y="122" font-size="21" fill="${MUTED}">${esc(subtitle)}</text>
  ${body}
  <g transform="translate(64,${H - 44}) scale(0.62)"><rect width="32" height="32" rx="8" fill="${INK}"/><path d="M5 17h5l3-8 5 15 3-7h6" fill="none" stroke="${MARK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>
  <text x="92" y="${H - 27}" font-size="15" fill="${MUTED}">${esc(source)}</text>
</svg>`;
}

function save(name, svg) {
  writeFileSync(`${outDir}/${name}.png`, new Resvg(svg, { font, fitTo: { mode: "width", value: W } }).render().asPng());
  console.log(name);
}

// generic multi-line chart over months; series: [{label, color, values: {m: v}}]
function lines(name, title, subtitle, series, { fmt = pct, yMax, labelRight = true, area = false } = {}) {
  const months = A.months.map((r) => r.m.slice(0, 10));
  const L = 92, R = labelRight ? 250 : 56, T = 170, B = 560;
  const raw = Math.max(...series.flatMap((s) => months.map((m) => s.values[m] ?? 0))) * 1.08;
  const step = [0.05, 0.1, 0.2, 0.25].find((st) => raw / st <= 5) ?? 0.25;
  const max = yMax ?? Math.ceil(raw / step) * step;
  const x = (i) => L + (i / (months.length - 1)) * (W - L - R);
  const y = (v) => B - (v / max) * (B - T);
  const ticks = yMax ? [0, 0.25, 0.5, 0.75, 1].map((f) => f * max) : Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const grid = ticks.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5"/>
    <text x="${L - 12}" y="${y(v) + 6}" text-anchor="end" font-size="16" fill="${MUTED}">${fmt(v)}</text>`).join("");
  const xt = months.map((m, i) => (i % 3 === 0 || i === months.length - 1) ? `<text x="${x(i)}" y="${B + 30}" text-anchor="middle" font-size="16" fill="${MUTED}">${mlabel(m)}</text>` : "").join("");
  const gaps = months.map((m, i) => GAP.has(m) ? `<rect x="${x(i) - 14}" y="${T}" width="28" height="${B - T}" fill="${RULE}" opacity="0.6"/>` : "").join("");
  const labels = [];
  const paths = series.map((s) => {
    let d = "", pen = false;
    months.forEach((m, i) => {
      const v = s.values[m];
      if (v == null || GAP.has(m)) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `; pen = true;
    });
    const last = [...months].reverse().find((m) => s.values[m] != null);
    labels.push({ y: y(s.values[last]), s });
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width ?? 4}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");
  // de-overlap right labels
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 24) labels[i].y = labels[i - 1].y + 24;
  const lab = labelRight ? labels.map(({ y: ly, s }) => `<text x="${W - R + 14}" y="${ly + 6}" font-size="18" font-weight="600" fill="${s.color}">${esc(s.label)} <tspan fill="${MUTED}" font-weight="400">${fmt(s.values[[...months].reverse().find((m) => s.values[m] != null)])}</tspan></text>`).join("") : "";
  save(name, frame(title, subtitle, gaps + grid + paths + xt + lab));
}

const byMonth = (rows, key, val, filter = () => true) => {
  const o = {};
  rows.filter(filter).forEach((r) => { (o[r[key]] ??= {})[r.m.slice(0, 10)] = Number(r[val]); });
  return o;
};

// 2. Qwen vs Llama
const tg = byMonth(A.textgen_orgs, "author", "share");
lines("02-text-orgs", "Qwen now gets half of all open LLM downloads",
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

// 6. model size: 100% stacked area
{
  const months = A.params.map((r) => r.m.slice(0, 10)).filter((m) => !GAP.has(m));
  const keys = [["under2b", "Under 2B"], ["b2_10", "2B to 10B"], ["b10_40", "10B to 40B"], ["over40b", "40B and up"]];
  const L = 92, R = 250, T = 170, B = 560;
  const x = (i) => L + (i / (months.length - 1)) * (W - L - R);
  const y = (v) => B - v * (B - T);
  const row = (m) => A.params.find((r) => r.m.slice(0, 10) === m);
  let acc = months.map(() => 0);
  const bands = keys.map(([k, label], ki) => {
    const lo = acc.slice(), hi = months.map((m, i) => acc[i] + Number(row(m)[k]));
    acc = hi;
    const up = hi.map((v, i) => `${x(i)},${y(v)}`).join(" L"), dn = lo.map((v, i) => `${x(i)},${y(v)}`).reverse().join(" L");
    const mid = (lo[lo.length - 1] + hi[hi.length - 1]) / 2;
    return `<path d="M${up} L${dn} Z" fill="${C[ki]}" fill-opacity="0.88"/>
      <text x="${W - R + 14}" y="${y(mid) + 6}" font-size="18" font-weight="600" fill="${C[ki]}">${label} <tspan fill="${MUTED}" font-weight="400">${pct(Number(row(months.at(-1))[k]))}</tspan></text>`;
  }).join("");
  const grid = [0, 0.25, 0.5, 0.75, 1].map((v) => `<text x="${L - 12}" y="${y(v) + 6}" text-anchor="end" font-size="16" fill="${MUTED}">${pct(v)}</text>`).join("");
  const xt = months.map((m, i) => (i % 3 === 0 || i === months.length - 1) ? `<text x="${x(i)}" y="${B + 30}" text-anchor="middle" font-size="16" fill="${MUTED}">${mlabel(m)}</text>` : "").join("");
  const g0 = Math.exp(Number(A.params[0].w_logmean)) / 1e9, g1 = Math.exp(Number(A.params.at(-1).w_logmean)) / 1e9;
  save("06-model-size", frame(`The typical downloaded LLM grew from ${g0.toFixed(1)}B to ${g1.toFixed(1)}B`,
    "Share of text-generation downloads by model size (parameters)", bands + grid + xt));
}

// 4. quantizers dumbbell
{
  const want = ["unsloth", "mradermacher", "lmstudio-community", "bartowski", "MaziyarPanahi", "mlx-community", "ggml-org", "TheBloke"];
  const get = (a, m) => Number((A.quantizers.find((r) => r.author === a && r.m.startsWith(m)) || {}).dl || 0);
  const rows = want.map((a) => ({ a, v0: get(a, "2025-03"), v1: get(a, "2026-09"), n: (A.quantizers.find((r) => r.author === a && r.m.startsWith("2026-09")) || {}).models }))
    .sort((p, q) => q.v1 - p.v1);
  const L = 300, R = 120, T = 175, rowH = 52, max = Math.max(...rows.flatMap((r) => [r.v0, r.v1])) * 1.08;
  const x = (v) => L + (v / max) * (W - L - R);
  const body = rows.map((r, i) => {
    const yy = T + i * rowH;
    const up = r.v1 >= r.v0, col = up ? C[0] : C[5];
    return `<text x="${L - 20}" y="${yy + 6}" text-anchor="end" font-size="20" font-weight="600" fill="${INK}">${esc(r.a)}</text>
      <line x1="${x(r.v0)}" x2="${x(r.v1)}" y1="${yy}" y2="${yy}" stroke="${col}" stroke-opacity="0.35" stroke-width="8" stroke-linecap="round"/>
      <circle cx="${x(r.v0)}" cy="${yy}" r="8" fill="${PAPER}" stroke="${MUTED}" stroke-width="3"/>
      <circle cx="${x(r.v1)}" cy="${yy}" r="10" fill="${col}"/>
      <text x="${Math.max(x(r.v1), x(r.v0)) + 18}" y="${yy + 6}" font-size="18" fill="${MUTED}">${human(r.v0)} to <tspan fill="${INK}" font-weight="700">${human(r.v1)}</tspan></text>`;
  }).join("");
  const legend = `<circle cx="${L}" cy="${T + rows.length * rowH + 8}" r="7" fill="${PAPER}" stroke="${MUTED}" stroke-width="3"/>
    <text x="${L + 16}" y="${T + rows.length * rowH + 14}" font-size="17" fill="${MUTED}">March 2025</text>
    <circle cx="${L + 150}" cy="${T + rows.length * rowH + 8}" r="8" fill="${C[0]}"/>
    <text x="${L + 166}" y="${T + rows.length * rowH + 14}" font-size="17" fill="${MUTED}">September 2026, monthly downloads</text>`;
  save("04-quantizers", frame("Quantizers became some of the Hub's biggest publishers",
    "Monthly downloads of repackaged models, March 2025 vs September 2026", body + legend));
}

// 7. launch curve
{
  const v = A.lifecycle.mean_weekly_share;
  const L = 92, R = 56, T = 175, B = 545, bw = (W - L - R) / v.length;
  const max = Math.max(...v) * 1.15;
  const y = (s) => B - (s / max) * (B - T);
  const bars = v.map((s, i) => `<rect x="${L + i * bw + 3}" y="${y(s)}" width="${bw - 6}" height="${B - y(s)}" rx="3" fill="${i < 2 ? C[1] : C[0]}" fill-opacity="${i < 2 ? 1 : 0.8}"/>`).join("");
  const xt = [0, 4, 8, 13, 17, 21, 25].map((i) => `<text x="${L + i * bw + bw / 2}" y="${B + 28}" text-anchor="middle" font-size="16" fill="${MUTED}">${i === 0 ? "launch week" : `week ${i}`}</text>`).join("");
  const grid = [0, 0.02, 0.04, 0.06, 0.08].filter((s) => s < max).map((s) => `<line x1="${L}" x2="${W - R}" y1="${y(s)}" y2="${y(s)}" stroke="${RULE}" stroke-width="1.5"/><text x="${L - 12}" y="${y(s) + 6}" text-anchor="end" font-size="16" fill="${MUTED}">${pct(s)}</text>`).join("");
  const note = `<text x="${W - R}" y="${T - 14}" text-anchor="end" font-size="18" fill="${INK}"><tspan font-weight="700">${pct(A.lifecycle.peak_after_month3)}</tspan> of these models peaked after their third month</text>`;
  save("07-launch-curve", frame("Launches spike for two weeks, then settle into a plateau",
    `Average weekly share of first-six-month downloads, ${A.lifecycle.models.toLocaleString("en")} models launched since Mar 2025`,
    grid + bars + xt + note));
}

// 8. likes per download
{
  const rows = A.likes_per_100k.map((r) => ({ t: r.pipeline_tag.replace(/-/g, " "), v: Number(r.likes_per_100k) }));
  const pick = [...rows.slice(0, 5), ...rows.slice(-5)];
  const L = 330, R = 140, T = 170, rowH = 40, max = Math.max(...pick.map((r) => r.v)) * 1.05;
  const x = (v) => L + (v / max) * (W - L - R);
  const body = pick.map((r, i) => {
    const yy = T + i * rowH + (i >= 5 ? 22 : 0);
    return `<text x="${L - 16}" y="${yy + 20}" text-anchor="end" font-size="19" fill="${INK}">${esc(r.t)}</text>
      <rect x="${L}" y="${yy + 4}" width="${Math.max(3, x(r.v) - L)}" height="26" rx="4" fill="${i < 5 ? C[3] : C[2]}"/>
      <text x="${Math.max(x(r.v), L + 3) + 12}" y="${yy + 23}" font-size="18" font-weight="600" fill="${INK}">${r.v >= 10 ? Math.round(r.v) : r.v.toFixed(1)}</text>`;
  }).join("") + `<line x1="${L - 300}" x2="${W - 64}" y1="${T + 5 * rowH + 12}" y2="${T + 5 * rowH + 12}" stroke="${RULE}" stroke-width="2" stroke-dasharray="6 6"/>`;
  save("08-likes", frame("Likes measure excitement, not use",
    "Likes per 100,000 monthly downloads, by task: the five highest and the five lowest", body));
}
