// HF-style brand images: avatar + Space/org-card thumbnail. Run from a dir with the TTFs and @resvg/resvg-js.
// usage: node render2.mjs hub.json
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync } from "fs";

const INK = "#1B1B1F", PAPER = "#ECE9E2", SURFACE = "#FBFAF5", MARK = "#FFD21E", MUTED = "#6E6C66", RULE = "#D9D5CA", BLUE = "#3B6FF5", RED = "#E5484D";
export const fonts = {
  fontFiles: ["fredoka-600.ttf", "fredoka-500.ttf", "ibm-plex-mono-400.ttf", "ibm-plex-mono-500.ttf", "ibm-plex-mono-600.ttf",
              "source-sans-3-400.ttf", "source-sans-3-600.ttf", "source-sans-3-700.ttf"],
  loadSystemFonts: false, defaultFontFamily: "Source Sans 3",
};
const BANNER_X = Number(process.env.BX ?? 732), BANNER_W = Number(process.env.BW ?? 462);
const render = (svg, file, width) => { writeFileSync(file, new Resvg(svg, { font: fonts, fitTo: { mode: "width", value: width } }).render().asPng()); console.log(file); };

export const logo = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s / 32})">
  <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="${MARK}" stroke="${INK}" stroke-width="3"/>
  <path d="M5.5 17h4.5l3-8 5 15 3-7h5.5" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g>`;
const star = (cx, cy, r, rot) => {
  const pts = [];
  for (let i = 0; i < 32; i++) { const a = (i / 32) * Math.PI * 2 + rot; const rr = i % 2 ? r * 0.82 : r; pts.push(`${(cx + rr * Math.cos(a)).toFixed(1)},${(cy + rr * Math.sin(a)).toFixed(1)}`); }
  return `M${pts.join(" L")}Z`;
};

// ---- avatar: the site's sticker icon with its hard offset shadow, on the site's paper ----
render(`<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="${PAPER}"/>
  <rect x="84" y="84" width="380" height="380" rx="92" fill="${INK}"/>
  <rect x="58" y="58" width="380" height="380" rx="92" fill="${MARK}" stroke="${INK}" stroke-width="26"/>
  <path d="M120 266h56l38-100 62 188 38-88h66" fill="none" stroke="${INK}" stroke-width="34" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`, "avatar.png", 512);

// ---- banner: the home page lockup, logo + "Model" + highlighted "Pulse" ----
render(`<svg xmlns="http://www.w3.org/2000/svg" width="1228" height="260" viewBox="0 0 1228 260">
  <rect width="1228" height="260" fill="${PAPER}"/>
  <g transform="translate(34,42)">
    <rect x="12" y="12" width="172" height="172" rx="42" fill="${INK}"/>
    <rect x="0" y="0" width="172" height="172" rx="42" fill="${MARK}" stroke="${INK}" stroke-width="14"/>
    <path d="M28 92h26l17-46 28 86 17-40h28" fill="none" stroke="${INK}" stroke-width="15" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <text x="246" y="192" font-family="Fredoka Light" font-weight="600" font-size="168" letter-spacing="-3" fill="${INK}">Model</text>
  <rect x="${BANNER_X}" y="26" width="${BANNER_W}" height="206" rx="24" fill="${MARK}"/>
  <text x="${BANNER_X + 30}" y="192" font-family="Fredoka Light" font-weight="600" font-size="168" letter-spacing="-3" fill="${INK}">Pulse</text>
</svg>`, "banner.png", 1228);

// ---- thumbnail with real weekly Hub downloads ----
const hub = JSON.parse(readFileSync(process.argv[2], "utf8"));
const byDay = new Map();
hub.day.forEach((d, i) => byDay.set(d, (byDay.get(d) ?? 0) + hub.dl[i]));
const weeks = new Map();
for (const [d, v] of byDay) {
  const t = Date.parse(d + "T00:00:00Z"); const wd = (new Date(t).getUTCDay() + 6) % 7;
  const key = t - wd * 86400000; weeks.set(key, (weeks.get(key) ?? 0) + v);
}
const wk = [...weeks.entries()].sort((a, b) => a[0] - b[0]).slice(-60, -1).map(([, v]) => v);

const W = 1200, H = 630;
const cx = 64, cy = 360, cw = W - 128, ch = 210;
const max = Math.max(...wk) * 1.08, bw = (cw - 48) / wk.length;
const bars = wk.map((v, i) => {
  const h = (v / max) * (ch - 40), x = cx + 24 + i * bw + 2, y = cy + ch - 18 - h;
  return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${h.toFixed(1)}" rx="2.5" fill="${BLUE}" stroke="${INK}" stroke-width="2"/>`;
}).join("");

render(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  ${logo(64, 50, 60)}
  <text x="140" y="94" font-family="Fredoka Light" font-weight="600" font-size="38" fill="${INK}">Model Pulse</text>
  <text x="62" y="196" font-family="Fredoka Light" font-weight="600" font-size="64" letter-spacing="-1" fill="${INK}">Download history for</text>
  <rect x="56" y="222" width="372" height="78" rx="12" fill="${MARK}"/>
  <text x="70" y="282" font-family="Fredoka Light" font-weight="600" font-size="64" letter-spacing="-1" fill="${INK}">every model</text>
  <text x="446" y="282" font-family="Fredoka Light" font-weight="600" font-size="64" letter-spacing="-1" fill="${INK}">on the Hub</text>
  <text x="64" y="334" font-family="IBM Plex Mono" font-weight="500" font-size="20" fill="${MUTED}">weekly downloads across all public models</text>
  <rect x="${cx + 6}" y="${cy + 6}" width="${cw}" height="${ch}" rx="18" fill="${INK}"/>
  <rect x="${cx}" y="${cy}" width="${cw}" height="${ch}" rx="18" fill="${SURFACE}" stroke="${INK}" stroke-width="3"/>
  ${[0.33, 0.66].map((f) => `<line x1="${cx + 24}" x2="${cx + cw - 24}" y1="${cy + ch - 18 - f * (ch - 40)}" y2="${cy + ch - 18 - f * (ch - 40)}" stroke="${RULE}" stroke-width="2" stroke-dasharray="5 6"/>`).join("")}
  <line x1="${cx + 24}" x2="${cx + cw - 24}" y1="${cy + ch - 18}" y2="${cy + ch - 18}" stroke="${INK}" stroke-width="3"/>
  ${bars}
  <g transform="rotate(10 1040 150)">
    <path d="${star(1040, 150, 82, 0)}" fill="${INK}" transform="translate(5,5)"/>
    <path d="${star(1040, 150, 82, 0)}" fill="${RED}" stroke="${INK}" stroke-width="3"/>
    <text x="1040" y="142" text-anchor="middle" font-family="Fredoka Light" font-weight="600" font-size="32" fill="#fff">1.6M</text>
    <text x="1040" y="176" text-anchor="middle" font-family="Fredoka Light" font-weight="600" font-size="24" fill="#fff">models</text>
  </g>
</svg>`, "thumbnail.png", 1200);
