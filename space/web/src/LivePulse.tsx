import { useEffect, useMemo, useRef } from "preact/hooks";
import type { Hub } from "./api";

/** One heartbeat on a 120-unit strip: baseline, P wave, QRS spike, T wave. */
const BEAT = "h18 q5 -7 10 0 h6 l4 6 l6 -46 l7 58 l5 -18 h12 q7 -12 14 0 h38"; // 120 units wide, ends on the baseline
const BEAT_W = 120;

/** Downloads per second across the Hub, from the last 7 days in the hub series. */
function ratePerSecond(hub: Hub) {
  const byDay = new Map<string, number>();
  hub.day.forEach((d, i) => byDay.set(d, (byDay.get(d) ?? 0) + hub.dl[i]));
  const days = [...byDay.keys()].sort().slice(-7);
  const total = days.reduce((a, d) => a + (byDay.get(d) ?? 0), 0);
  return days.length ? total / (days.length * 86400) : 0;
}

const nf = new Intl.NumberFormat("en");

export function LivePulse({ hub }: { hub: Hub | null }) {
  const rate = useMemo(() => (hub ? ratePerSecond(hub) : 0), [hub]);
  const out = useRef<HTMLSpanElement>(null);
  const opened = useRef(performance.now());

  useEffect(() => {
    if (!rate) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0, timer = 0;
    const paint = () => {
      const n = Math.floor(((performance.now() - opened.current) / 1000) * rate);
      if (out.current) out.current.textContent = nf.format(n);
    };
    if (reduce) {
      paint();
      timer = window.setInterval(paint, 1000);
    } else {
      const loop = () => { paint(); raf = requestAnimationFrame(loop); };
      loop();
    }
    return () => { cancelAnimationFrame(raf); clearInterval(timer); };
  }, [rate]);

  // one beat per ~1,000 downloads keeps the rhythm tied to the real rate (clamped to a believable heart rate)
  const beatSeconds = rate ? Math.min(1.4, Math.max(0.6, 1000 / rate)) : 1;
  const path = "M0 60 " + Array.from({ length: 14 }, () => BEAT).join(" ");

  return (
    <section class="wrap">
      <div class="card live-pulse" aria-label="Live estimate of downloads from the Hugging Face Hub">
        <div class="ecg" aria-hidden="true">
          <svg viewBox={`0 0 ${BEAT_W * 7} 100`} preserveAspectRatio="none">
            <g class="ecg-strip" style={{ animationDuration: `${beatSeconds}s` }}>
              <path d={path} fill="none" stroke="#1B1B1F" stroke-width="4.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
            </g>
          </svg>
          <span class="ecg-live"><i />LIVE</span>
        </div>
        <div class="live-count">
          <span class="n" ref={out}>0</span>
          <span class="l">downloads from the Hub since you opened this page</span>
          <span class="m">{rate ? `≈ ${nf.format(Math.round(rate))} per second, from the last 7 days` : "measuring…"}</span>
        </div>
      </div>
    </section>
  );
}
