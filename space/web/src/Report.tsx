import { useEffect, useMemo } from "preact/hooks";
import { marked } from "marked";
import md from "./report.md?raw";
import { navigate } from "./api";

const PUBLISHED = "October 3, 2026";

export function Report() {
  const html = useMemo(() => {
    const words = md.split(/\s+/).length;
    let h = marked.parse(md, { async: false }) as string;
    // byline under the title, wide tables scroll on their own
    h = h.replace("</h1>", `</h1><p class="byline">${PUBLISHED} · ${Math.round(words / 230)} min read · by <a href="https://huggingface.co/tardellirs">Tardelli Stekel</a></p>`);
    h = h.replace(/<table>/g, '<div class="table-scroll"><table class="list">').replace(/<\/table>/g, "</table></div>");
    // every chart is 1200x675; stating it lets the browser keep the space while the image loads
    h = h.replace(/<img /g, '<img loading="lazy" decoding="async" width="1200" height="675" ');
    return h;
  }, []);

  useEffect(() => {
    document.title = "What 19 months of daily downloads say about the Hub · Model Pulse";
    window.scrollTo({ top: 0 });
  }, []);

  // links to Model Pulse stay inside the app; everything else opens in a new tab
  const onClick = (e: MouseEvent) => {
    const a = (e.target as HTMLElement).closest("a");
    if (!a) return;
    const href = a.getAttribute("href") || "";
    const m = href.match(/^https:\/\/huggingface\.co\/spaces\/(?:modelpulse|tardellirs)\/model-pulse\/?(\?[^#]*)?$/);
    if (m) {
      e.preventDefault();
      const q = new URLSearchParams((m[1] || "").slice(1));
      const model = q.get("model"), view = q.get("view") || undefined;
      navigate(model || view ? { model: model || undefined, view } : {});
      return;
    }
    if (/^https?:/.test(href)) { a.target = "_blank"; a.rel = "noopener"; }
  };

  return <article class="wrap report" onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />;
}
