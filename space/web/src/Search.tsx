import { Fragment } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { api, fmt, parseHubInput, parseModelInput, taskLabel, type Kind } from "./api";

type Hit = { id: string; kind: Kind; meta: string; title?: string | null };
const GROUP: Record<Kind, string> = { model: "Models", dataset: "Datasets", space: "Spaces" };

const SearchIcon = ({ size = 16 }) => (
  <svg class="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

/** Models only by default; with `all`, datasets and Spaces too, grouped by kind. */
export function Search({ onPick, big, placeholder, autoFocus, hotkey, exclude = [], all }: {
  onPick: (id: string, kind: Kind) => void; big?: boolean; placeholder?: string; autoFocus?: boolean; hotkey?: boolean; exclude?: string[]; all?: boolean;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const seq = useRef(0);

  useEffect(() => {
    if (!hotkey) return;
    const h = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && document.activeElement?.tagName !== "INPUT")) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    addEventListener("keydown", h);
    return () => removeEventListener("keydown", h);
  }, [hotkey]);

  useEffect(() => {
    const s = q.trim();
    if (s.length < 2) { setHits([]); return; }
    const parsed = parseHubInput(s);
    const term = parsed && s.includes("huggingface.co") ? parsed.id : s;
    const n = ++seq.current;
    const t = setTimeout(() => {
      const done = (h: Hit[]) => { if (n === seq.current) { setHits(h.filter((x) => !exclude.includes(x.id))); setSel(0); } };
      if (all) {
        api.searchAll(term).then((r) => {
          const groups: Hit[][] = [
            r.models.map((h): Hit => ({ id: h.id, kind: "model", meta: `${taskLabel(h.pipeline_tag)} · ${fmt(h.dl30)}/mo` })),
            r.datasets.map((h): Hit => ({ id: h.id, kind: "dataset", meta: `${fmt(h.dl30)}/mo` })),
            r.spaces.map((h): Hit => ({ id: h.id, kind: "space", title: h.title, meta: `${h.emoji ?? ""} ${fmt(h.likes)} likes`.trim() })),
          ];
          // a kind with an exact name match goes first ("fineweb" is a dataset before it's any model)
          const t = term.toLowerCase().split("/").pop();
          const exact = (g: Hit[]) => g.some((h) => h.id.toLowerCase() === term.toLowerCase() || h.id.toLowerCase().split("/").pop() === t);
          done([...groups.filter(exact), ...groups.filter((g) => !exact(g))].flat());
        }).catch(() => {});
      } else {
        api.search(term).then((r) => done(r.map((h): Hit => ({ id: h.id, kind: "model", meta: `${taskLabel(h.pipeline_tag)} · ${fmt(h.dl30)}/mo` })))).catch(() => {});
      }
    }, 120);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (id: string, kind: Kind = "model") => {
    setQ(""); setHits([]); setOpen(false);
    input.current?.blur();
    onPick(id, kind);
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Escape") { setOpen(false); input.current?.blur(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (hits[sel]) pick(hits[sel].id, hits[sel].kind);
      else if (all) { const p = parseHubInput(q); if (p) pick(p.id, p.kind); }
      else { const p = parseModelInput(q); if (p) pick(p); }
    }
  };

  const term = q.trim().toLowerCase();
  const hl = (id: string) => {
    const i = id.toLowerCase().indexOf(term);
    if (i < 0 || !term) return id;
    return <>{id.slice(0, i)}<b>{id.slice(i, i + term.length)}</b>{id.slice(i + term.length)}</>;
  };

  return (
    <div class={`search${big ? " big" : ""}`}>
      <SearchIcon size={big ? 20 : 16} />
      <input
        ref={input}
        value={q}
        autoFocus={autoFocus}
        placeholder={placeholder ?? (all ? "Search models, datasets and Spaces" : "Search models")}
        aria-label={all ? "Search models, datasets and Spaces" : "Search models"}
        role="combobox"
        aria-expanded={open && hits.length > 0}
        aria-controls="search-results"
        autocomplete="off"
        spellcheck={false}
        onInput={(e) => { setQ((e.target as HTMLInputElement).value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKey}
      />
      {hotkey && !q && <kbd>⌘K</kbd>}
      {open && hits.length > 0 && (
        <ul class="results" id="search-results" role="listbox">
          {hits.map((h, i) => (
            <Fragment key={`${h.kind}:${h.id}`}>
              {all && (i === 0 || hits[i - 1].kind !== h.kind) && <li key={`g-${h.kind}`} class="rgroup" role="presentation">{GROUP[h.kind]}</li>}
              <li key={`${h.kind}:${h.id}`} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onMouseDown={(e) => { e.preventDefault(); pick(h.id, h.kind); }}>
                <span class="rid">{hl(h.id)}</span>
                <span class="rmeta">{h.meta}</span>
              </li>
            </Fragment>
          ))}
        </ul>
      )}
    </div>
  );
}
