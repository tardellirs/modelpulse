import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { navigate, readRoute, SPACE_URL, type Route } from "./api";
import { AuthorPage } from "./AuthorPage";
import { Home } from "./Home";
import { Logo } from "./Logo";
import { ModelPage } from "./ModelPage";
import { Search } from "./Search";
import "./styles.css";

function App() {
  const [route, setRoute] = useState<Route>(readRoute());

  useEffect(() => {
    const h = () => setRoute(readRoute());
    addEventListener("popstate", h);
    addEventListener("routechange", h);
    // keep the huggingface.co address bar in sync on first load too
    try { window.parent?.postMessage({ queryString: location.search.slice(1), hash: "" }, "https://huggingface.co"); } catch {}
    return () => { removeEventListener("popstate", h); removeEventListener("routechange", h); };
  }, []);

  const isHome = !route.model && !route.author;

  return (
    <>
      <header class="top">
        <div class="wrap">
          <a class="brand" href="?" onClick={(e) => { e.preventDefault(); navigate({}); }}>
            <Logo /><span>Model Pulse</span>
          </a>
          {!isHome && <Search hotkey onPick={(id) => navigate({ model: id })} />}
          <nav>
            {!isHome && <a class="hide-sm" href="?" onClick={(e) => { e.preventDefault(); navigate({}); }}>Rankings</a>}
            <a class="like" href={SPACE_URL} target="_top" title="Like Model Pulse on Hugging Face">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2.1 0 3.6 1.1 5.4 3 1.8-1.9 3.3-3 5.4-3 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z" /></svg>
              <span class="t">Like</span>
            </a>
          </nav>
        </div>
      </header>
      <main>
        {route.model ? <ModelPage route={route} key={route.model} /> : route.author ? <AuthorPage route={route} key={route.author} /> : <Home />}
      </main>
      <footer class="foot">
        <div class="wrap">
          <span>
            Data from daily snapshots of <a href="https://huggingface.co/datasets/cfahlgren1/hub-stats" target="_blank" rel="noopener">cfahlgren1/hub-stats</a>,
            refreshed every day. An independent project, not affiliated with Hugging Face.
          </span>
          <span>Download counts follow the <a href="https://huggingface.co/docs/hub/models-download-stats" target="_blank" rel="noopener">Hub's own counting rules</a>.</span>
          <span class="maker">
            Made by <a href="https://huggingface.co/tardellirs" target="_blank" rel="noopener">Tardelli Stekel</a>
            {" "}(<a href="https://huggingface.co/tardellirs" target="_blank" rel="noopener">@tardellirs</a> on Hugging Face,{" "}
            <a href="https://stekel.ifsp.dev/" target="_blank" rel="noopener">stekel.ifsp.dev</a>)
          </span>
        </div>
      </footer>
    </>
  );
}

render(<App />, document.getElementById("app")!);
