import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { navigate, readRoute, type Route } from "./api";
import { AuthorPage } from "./AuthorPage";
import { Home } from "./Home";
import { Logo } from "./Logo";
import { LikeButton } from "./Like";
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
            <LikeButton />
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
