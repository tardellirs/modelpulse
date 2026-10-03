import { useEffect, useRef, useState } from "preact/hooks";
import { api, fmt, parseModelInput, taskLabel } from "./api";

type Hit = { id: string; pipeline_tag: string | null; dl30: number | null };

const SearchIcon = ({ size = 16 }) => (
  <svg class="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export function Search({ onPick, big, placeholder, autoFocus, hotkey, exclude = [] }: {
  onPick: (id: string) => void; big?: boolean; placeholder?: string; autoFocus?: boolean; hotkey?: boolean; exclude?: string[];
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
    const parsed = parseModelInput(s);
    const term = parsed && s.includes("huggingface.co") ? parsed : s;
    const n = ++seq.current;
    const t = setTimeout(() => {
      api.search(term).then((r) => {
        if (n !== seq.current) return;
        setHits(r.filter((h) => !exclude.includes(h.id)));
        setSel(0);
      }).catch(() => {});
    }, 120);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (id: string) => {
    setQ(""); setHits([]); setOpen(false);
    input.current?.blur();
    onPick(id);
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Escape") { setOpen(false); input.current?.blur(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (hits[sel]) pick(hits[sel].id);
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
        placeholder={placeholder ?? "Search models"}
        aria-label="Search models"
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
            <li key={h.id} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onMouseDown={(e) => { e.preventDefault(); pick(h.id); }}>
              <span class="rid">{hl(h.id)}</span>
              <span class="rmeta">{taskLabel(h.pipeline_tag)} · {fmt(h.dl30)}/mo</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
