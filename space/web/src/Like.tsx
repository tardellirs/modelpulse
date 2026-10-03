import { useEffect, useRef, useState } from "preact/hooks";
import { SPACE_URL } from "./api";

/** Likes only happen on Hugging Face's own ♡ button, in the bar above the Space. When we're embedded there, point to it. */
export const EMBEDDED = (() => {
  try { return window.self !== window.top; } catch { return true; }
})();

const Heart = ({ size = 15, fill = "currentColor" }: { size?: number; fill?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} aria-hidden="true">
    <path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2.1 0 3.6 1.1 5.4 3 1.8-1.9 3.3-3 5.4-3 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z" />
  </svg>
);

const SHOW = "show-like-hint";
export const showLikeHint = () => { window.scrollTo({ top: 0, behavior: "smooth" }); window.dispatchEvent(new Event(SHOW)); };

export function LikeButton() {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const show = () => setOpen(true);
    const away = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    addEventListener(SHOW, show);
    addEventListener("mousedown", away);
    return () => { removeEventListener(SHOW, show); removeEventListener("mousedown", away); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => setOpen(false), 9000);
    return () => clearTimeout(t);
  }, [open]);

  if (!EMBEDDED)
    return (
      <a class="like" href={SPACE_URL} target="_blank" rel="noopener" title="Opens Model Pulse on Hugging Face, where you can like it">
        <Heart /><span class="t">Like on Hugging Face ↗</span>
      </a>
    );

  return (
    <div class="like-wrap" ref={wrap}>
      <button class="like" aria-expanded={open} aria-controls="like-hint" onClick={() => setOpen(!open)}>
        <Heart /><span class="t">Like</span><span aria-hidden="true">↑</span>
      </button>
      {open && (
        <div class="like-pop" id="like-hint" role="status">
          <b>Likes live on Hugging Face's own button.</b>
          <span>Click <span class="hf-like"><Heart size={12} fill="#ff4d6d" /> like</span> in the bar above this page, next to <code>modelpulse/model-pulse</code>.</span>
        </div>
      )}
    </div>
  );
}

export function LikeCta() {
  if (!EMBEDDED)
    return (
      <a class="btn" href={SPACE_URL} target="_blank" rel="noopener"><Heart fill="#ff4d6d" />Like on Hugging Face ↗</a>
    );
  return (
    <>
      <p class="like-how">
        Click <span class="hf-like"><Heart size={12} fill="#ff4d6d" /> like</span> in the Hugging Face bar above this page, next to <code>modelpulse/model-pulse</code>.
      </p>
      <button class="btn" onClick={showLikeHint}>Show me where</button>
    </>
  );
}
