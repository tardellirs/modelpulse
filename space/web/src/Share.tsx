import { useState } from "preact/hooks";
import { LikeCta } from "./Like";
import { API_BASE, fmt, fmtPct, SPACE_URL, type Model } from "./api";

const BADGE_HOST = "https://modelpulse.ifsp.dev";

function Copy({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button class="btn" onClick={async () => {
      try { await navigator.clipboard.writeText(text); } catch {
        const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
      }
      setDone(true); setTimeout(() => setDone(false), 1600);
    }}>{done ? "Copied" : label}</button>
  );
}

async function makeCard(model: Model) {
  await document.fonts.ready;
  const W = 1200, H = 675, dpr = 2;
  const c = document.createElement("canvas");
  c.width = W * dpr; c.height = H * dpr;
  const x = c.getContext("2d")!;
  x.scale(dpr, dpr);
  const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  x.fillStyle = css("--paper"); x.fillRect(0, 0, W, H);
  // brand
  x.fillStyle = css("--ink"); x.beginPath(); x.roundRect(56, 48, 34, 34, 9); x.fill();
  x.strokeStyle = "#FFD43B"; x.lineWidth = 3; x.lineCap = "round"; x.lineJoin = "round";
  x.beginPath(); x.moveTo(62, 66); x.lineTo(68, 66); x.lineTo(72, 57); x.lineTo(78, 75); x.lineTo(81, 67); x.lineTo(85, 67); x.stroke();
  x.fillStyle = css("--ink"); x.font = `700 20px ${css("--font")}`; x.fillText("Model Pulse", 102, 72);
  x.fillStyle = css("--muted"); x.font = `400 18px ${css("--font")}`;
  x.textAlign = "right"; x.fillText("modelpulse.ifsp.dev", W - 56, 72); x.textAlign = "left";
  // title + figures
  x.fillStyle = css("--ink"); x.font = `600 36px ${css("--font")}`;
  x.fillText(model.id.length > 48 ? model.id.slice(0, 47) + "…" : model.id, 56, 148);
  x.font = `600 88px ${css("--font-cond")}`;
  const big = (model.dl_all ?? model.dl30 ?? 0).toLocaleString("en");
  x.fillText(big, 56, 248);
  const bw = x.measureText(big).width;
  x.fillStyle = css("--muted"); x.font = `400 20px ${css("--font")}`;
  x.fillText(model.dl_all != null ? "downloads all time" : "downloads, last 30 days", 60, 280);
  if (model.growth_7d != null) {
    x.fillStyle = model.growth_7d >= 0 ? css("--up") : css("--down");
    x.font = `600 30px ${css("--font")}`;
    x.fillText(`${fmtPct(model.growth_7d)} this week`, 56 + bw + 28, 240);
  }
  // chart snapshot
  const src = document.querySelector(".chart-box canvas") as HTMLCanvasElement | null;
  if (src) {
    const cw = W - 112, ch = H - 330 - 40;
    const r = Math.min(cw / src.width, ch / src.height);
    x.drawImage(src, (W - src.width * r) / 2, 320, src.width * r, src.height * r);
  }
  return new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/png"));
}

if ((import.meta as any).env?.DEV) (window as any).__makeCard = makeCard;

export function Share({ model, url }: { model: Model; url: string }) {
  const [metric, setMetric] = useState<"month" | "all" | "likes">("month");
  const badge = `${BADGE_HOST}/badge/${model.id}.svg${metric === "month" ? "" : `?metric=${metric}`}`;
  const md = `[![Model Pulse](${badge})](${SPACE_URL}?model=${model.id})`;
  const growth = model.growth_7d != null ? ` (${fmtPct(model.growth_7d)} week over week)` : "";
  const post = `${model.id} has ${fmt(model.dl_all ?? model.dl30)} downloads on Hugging Face${growth}. Full download history:`;

  return (
    <section class="section">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Share this model's numbers</h2>
            <p>Every link opens this page with the same chart and comparison.</p>
          </div>
        </div>
        <div class="share-grid">
          <div>
            <h3>Link</h3>
            <p>Opens Model Pulse on Hugging Face, ready to explore.</p>
            <div class="code"><code>{url}</code><Copy text={url} /></div>
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button class="btn" onClick={async () => {
                const b = await makeCard(model);
                const a = document.createElement("a");
                a.href = URL.createObjectURL(b);
                a.download = `${model.id.replace("/", "_")}-model-pulse.png`;
                a.click();
                setTimeout(() => URL.revokeObjectURL(a.href), 2000);
              }}>Download image</button>
              <a class="btn" target="_blank" rel="noopener" href={`https://x.com/intent/post?text=${encodeURIComponent(post)}&url=${encodeURIComponent(url)}`}>Post on X</a>
              <a class="btn" target="_blank" rel="noopener" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`}>Share on LinkedIn</a>
            </div>
          </div>
          <div>
            <h3>Badge for your model card</h3>
            <p>Updates daily. Paste it into the README of {model.id.split("/").pop()}.</p>
            <div class="seg badge-opts" role="group" aria-label="Badge metric">
              <button aria-pressed={metric === "month"} onClick={() => setMetric("month")}>Monthly</button>
              <button aria-pressed={metric === "all"} onClick={() => setMetric("all")}>All time</button>
              <button aria-pressed={metric === "likes"} onClick={() => setMetric("likes")}>Likes</button>
            </div>
            <div class="badge-preview"><img src={badge.replace(BADGE_HOST, API_BASE)} alt="Model Pulse badge preview" height={22} /></div>
            <div class="code"><code>{md}</code><Copy text={md} label="Copy markdown" /></div>
          </div>
          <div class="cta">
            <h3>Keep Model Pulse on model pages</h3>
            <p>Hugging Face lists the most-liked Spaces on each model page. A like keeps download history one click away for everyone.</p>
            <LikeCta />
          </div>
        </div>
      </div>
    </section>
  );
}
