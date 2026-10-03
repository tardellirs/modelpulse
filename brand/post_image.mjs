// Launch-post image: Hub-wide daily downloads by task, from /api/hub. Run from the brand/ dir with fonts present.
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync } from "fs";

const hub = JSON.parse(readFileSync(process.argv[2], "utf8"));
const W = 1200, H = 675, L = 92, R = 56, T = 250, B = 575;
const INK = "#151833", PAPER = "#F6F7FA", MUTED = "#6A6F8C", RULE = "#E2E5EE", MARK = "#FFD43B";
const COLORS = { "text-generation": "#3B4CF5", "sentence-similarity": "#E8590C", "image-text-to-text": "#0C8A7A", "feature-extraction": "#B02FB0" };
const LABELS = { "text-generation": "Text generation", "sentence-similarity": "Sentence similarity", "image-text-to-text": "Vision-language", "feature-extraction": "Feature extraction", other: "Everything else" };

const days = [...new Set(hub.day)].sort();
const tags = [...Object.keys(COLORS), "other"];
const series = Object.fromEntries(tags.map((t) => [t, new Array(days.length).fill(0)]));
const idx = new Map(days.map((d, i) => [d, i]));
hub.day.forEach((d, i) => { const t = COLORS[hub.tag[i]] ? hub.tag[i] : "other"; series[t][idx.get(d)] += hub.dl[i]; });
const smooth = (v, w = 28) => v.map((_, i) => { const s = v.slice(Math.max(0, i - w + 1), i + 1); return s.reduce((a, b) => a + b, 0) / s.length; });
for (const t of tags) series[t] = smooth(series[t]);

const stack = [];
let acc = new Array(days.length).fill(0);
for (const t of tags) { const top = acc.map((a, i) => a + series[t][i]); stack.push([t, acc, top]); acc = top; }
const max = Math.max(...acc) * 1.05;
const x = (i) => L + (i / (days.length - 1)) * (W - L - R);
const y = (v) => B - (v / max) * (B - T);
const bands = stack.map(([t, lo, hi]) => {
  const up = hi.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" L");
  const down = lo.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse().join(" L");
  return `<path d="M${up} L${down} Z" fill="${COLORS[t] || "#DCDFEA"}" fill-opacity="${COLORS[t] ? 0.9 : 1}"/>`;
}).join("");
const grid = [0, 25e6, 50e6, 75e6, 100e6].filter((v) => v < max).map((v) =>
  `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${RULE}" stroke-width="1.5"/>
   <text x="${L - 10}" y="${y(v) + 5}" text-anchor="end" font-size="15" fill="${MUTED}">${v ? v / 1e6 + "M" : "0"}</text>`).join("");
const seen = new Set();
const months = days.map((d, i) => [d, i]).filter(([d]) => { const m = d.slice(0, 7); if (seen.has(m) || !["01", "04", "07", "10"].includes(d.slice(5, 7))) return false; seen.add(m); return true; });
const ticks = months.map(([d, i]) => `<text x="${x(i)}" y="${B + 28}" text-anchor="middle" font-size="15" fill="${MUTED}">${new Date(d + "T00:00:00Z").toLocaleString("en", { month: "short", timeZone: "UTC" })} ${d.slice(2, 4)}</text>`).join("");
const legend = tags.map((t, k) => `<g transform="translate(${L + k * 196},${B + 60})"><rect width="14" height="14" rx="3" fill="${COLORS[t] || "#DCDFEA"}"/><text x="22" y="12" font-size="15" fill="${INK}">${LABELS[t]}</text></g>`).join("");

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="IBM Plex Sans">
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  <g transform="translate(${L - 28},48) scale(1.25)"><rect width="32" height="32" rx="8" fill="${INK}"/><path d="M5 17h5l3-8 5 15 3-7h6" fill="none" stroke="${MARK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>
  <text x="${L + 26}" y="78" font-weight="700" font-size="24" fill="${INK}">Model Pulse</text>
  <text x="${L - 28}" y="150" font-weight="700" font-size="50" letter-spacing="-1" fill="${INK}">The Hub serves ~100M model downloads a day</text>
  <text x="${L - 28}" y="192" font-size="22" fill="${MUTED}">Daily downloads across all public models, by task, 28-day average. Up from ~62M a year ago.</text>
  ${grid}${bands}${ticks}${legend}
</svg>`;
writeFileSync("post_image.png", new Resvg(svg, { font: { fontFiles: ["plex-400.ttf", "plex-600.ttf", "plex-700.ttf", "plexcond-600.ttf"], loadSystemFonts: false, defaultFontFamily: "IBM Plex Sans" }, fitTo: { mode: "width", value: 1200 } }).render().asPng());
console.log("ok", days[0], days[days.length - 1]);
