import { SPACE_URL } from "./api";

/** Likes only happen on Hugging Face's own ♡ button, in the bar above the Space. */
export const EMBEDDED = (() => {
  try { return window.self !== window.top; } catch { return true; }
})();

const Heart = ({ size = 15, fill = "currentColor" }: { size?: number; fill?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} aria-hidden="true">
    <path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2.1 0 3.6 1.1 5.4 3 1.8-1.9 3.3-3 5.4-3 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z" />
  </svg>
);

export function LikeCta() {
  // Outside Hugging Face, send people to the Space page, where the like button is.
  if (!EMBEDDED)
    return (
      <a class="btn" href={SPACE_URL} target="_blank" rel="noopener"><Heart fill="#ff4d6d" />Like on Hugging Face ↗</a>
    );
  // Inside the Space we can't like on the visitor's behalf: show the label, and explain on hover or focus.
  return (
    <span class="btn like-fake" tabIndex={0} aria-describedby="like-tip">
      <Heart fill="#ff4d6d" />Like on Hugging Face
      <span class="like-tip" id="like-tip" role="tooltip">
        Click <span class="hf-like"><Heart size={12} fill="#ff4d6d" /> like</span> in the Hugging Face bar above this page, next to <code>modelpulse/model-pulse</code>.
      </span>
    </span>
  );
}
