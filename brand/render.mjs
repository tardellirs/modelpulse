import { Resvg } from "@resvg/resvg-js";
import { writeFileSync } from "fs";

const fonts = { fontFiles: ["plex-400.ttf", "plex-600.ttf", "plex-700.ttf", "plexcond-600.ttf"], loadSystemFonts: false, defaultFontFamily: "IBM Plex Sans" };
const INK = "#151833", PAPER = "#F6F7FA", SIGNAL = "#3B4CF5", MARK = "#FFD43B", MUTED = "#6A6F8C", RULE = "#E2E5EE";

const mark = (x, y, s) => `
  <g transform="translate(${x},${y}) scale(${s / 32})">
    <rect width="32" height="32" rx="8" fill="${INK}"/>
    <path d="M5 17h5l3-8 5 15 3-7h6" fill="none" stroke="${MARK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
  </g>`;

function render(svg, file, width) {
  const png = new Resvg(svg, { font: fonts, fitTo: { mode: "width", value: width } }).render().asPng();
  writeFileSync(file, png);
  console.log(file, png.length);
}

// ---- avatar ----
render(`<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="${INK}"/>
  <path d="M5 17h5l3-8 5 15 3-7h6" fill="none" stroke="${MARK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`, "avatar.png", 512);

// ---- thumbnail: a believable download curve with milestone markers ----
const W = 1200, H = 630;
const cx0 = 0, cx1 = W, cy0 = 430, cy1 = 610;
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const N = 140, pts = [];
for (let i = 0; i < N; i++) {
  const t = i / (N - 1);
  const base = 0.08 + 0.75 * Math.pow(t, 1.8) + 0.12 * Math.exp(-Math.pow((t - 0.42) / 0.05, 2));
  const v = Math.min(1, base * (0.93 + 0.14 * rnd()));
  pts.push([cx0 + t * (cx1 - cx0), cy1 - v * (cy1 - cy0)]);
}
// light smoothing
const sm = pts.map((p, i) => {
  const a = pts[Math.max(0, i - 2)], b = pts[Math.min(N - 1, i + 2)];
  return [p[0], (a[1] + p[1] * 2 + b[1]) / 4];
});
const line = "M" + sm.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
const area = `${line} L${cx1},${H} L${cx0},${H} Z`;
const milestones = [[0.30, "1M"], [0.62, "10M"], [0.88, "100M"]].map(([t, label]) => {
  const x = cx0 + t * (cx1 - cx0);
  return `<line x1="${x}" y1="${cy0 - 30}" x2="${x}" y2="${H}" stroke="${MARK}" stroke-width="3" stroke-dasharray="6 6"/>
    <rect x="${x - 34}" y="${cy0 - 62}" width="68" height="32" rx="6" fill="${MARK}"/>
    <text x="${x}" y="${cy0 - 39}" text-anchor="middle" font-family="IBM Plex Sans" font-weight="700" font-size="19" fill="${INK}">${label}</text>`;
}).join("");

render(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${SIGNAL}" stop-opacity="0.28"/>
      <stop offset="1" stop-color="${SIGNAL}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="${PAPER}"/>
  ${[450, 500, 550, 600].map((y) => `<line x1="0" x2="${W}" y1="${y}" y2="${y}" stroke="${RULE}" stroke-width="1.5"/>`).join("")}
  <path d="${area}" fill="url(#g)"/>
  ${milestones}
  <path d="${line}" fill="none" stroke="${SIGNAL}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>
  ${mark(64, 56, 64)}
  <text x="146" y="101" font-family="IBM Plex Sans" font-weight="700" font-size="34" fill="${INK}">Model Pulse</text>
  <text x="62" y="196" font-family="IBM Plex Sans Condensed" font-weight="600" font-size="76" letter-spacing="-1.5" fill="${INK}">Download history for</text>
  <text x="62" y="272" font-family="IBM Plex Sans Condensed" font-weight="600" font-size="76" letter-spacing="-1.5" fill="${INK}">every model on the Hub</text>
  <text x="64" y="318" font-family="IBM Plex Sans" font-weight="400" font-size="25" fill="${MUTED}">1.6M models, day by day since July 2024</text>
</svg>`, "thumbnail.png", 1200);
