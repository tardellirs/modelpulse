import { render } from "preact";
import type { ComponentType } from "preact";
import { useEffect, useState } from "preact/hooks";
import { PATH_MODE, hrefOf, navigate, readRoute, type Route } from "./api";
import { AuthorPage } from "./AuthorPage";
import { Home } from "./Home";
import { Logo } from "./Logo";
import { ModelPage } from "./ModelPage";
import { Search } from "./Search";
// fonts are served with the site rather than from Google Fonts: one less origin to connect to before text renders
import "@fontsource/fredoka/latin-500.css";
import "@fontsource/fredoka/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "@fontsource/source-sans-3/latin-400.css";
import "@fontsource/source-sans-3/latin-600.css";
import "@fontsource/source-sans-3/latin-700.css";
import "./styles.css";

/** Load a page's code the first time it is shown, so model pages ship less JavaScript. */
function lazy<P>(load: () => Promise<ComponentType<P>>) {
  let Loaded: ComponentType<P> | null = null;
  let pending: Promise<ComponentType<P>> | null = null;
  return (props: P) => {
    const [, ready] = useState(0);
    useEffect(() => {
      if (!Loaded) (pending ??= load()).then((C) => { Loaded = C; ready((n) => n + 1); });
    }, []);
    return Loaded ? <Loaded {...(props as any)} /> : <div class="wrap" style={{ minHeight: "70vh" }} />;
  };
}

const Galaxy = lazy(() => import("./Galaxy").then((m) => m.Galaxy));
const Wrapped = lazy(() => import("./Wrapped").then((m) => m.Wrapped));
const Report = lazy(() => import("./Report").then((m) => m.Report));
const DatasetPage = lazy(() => import("./Repos").then((m) => m.DatasetPage));
const SpacePage = lazy(() => import("./Repos").then((m) => m.SpacePage));

function App() {
  const [route, setRoute] = useState<Route>(readRoute());

  useEffect(() => {
    const h = () => setRoute(readRoute());
    addEventListener("popstate", h);
    addEventListener("routechange", h);
    // keep the huggingface.co address bar in sync on first load too
    if (!PATH_MODE) try { window.parent?.postMessage({ queryString: location.search.slice(1), hash: "" }, "https://huggingface.co"); } catch {}
    return () => { removeEventListener("popstate", h); removeEventListener("routechange", h); };
  }, []);

  const isReport = route.view === "report";
  const isWrapped = route.view === "wrapped";
  const isGalaxy = route.view === "galaxy";
  const isHome = !route.model && !route.dataset && !route.space && !route.author && !isReport && !isWrapped && !isGalaxy;

  return (
    <>
      <header class="top">
        <div class="wrap">
          <a class="brand" aria-label="Model Pulse home" href={hrefOf({})} onClick={(e) => { e.preventDefault(); navigate({}); }}>
            <Logo /><span>Model Pulse</span>
          </a>
          {!isHome && <Search hotkey all onPick={(id, kind) => navigate({ [kind]: id })} />}
          <nav>
            {!isHome && <a class="btn nav-btn hide-sm" href={hrefOf({})} onClick={(e) => { e.preventDefault(); navigate({}); }}>Rankings</a>}
            <a class="btn nav-btn" aria-current={isGalaxy ? "page" : undefined} href={hrefOf({ view: "galaxy" })} onClick={(e) => { e.preventDefault(); navigate({ view: "galaxy" }); }}>Galaxy</a>
            <a class="btn nav-btn" aria-current={isWrapped ? "page" : undefined} href={hrefOf({ view: "wrapped" })} onClick={(e) => { e.preventDefault(); navigate({ view: "wrapped" }); }}>Wrapped</a>
            <a class={`btn nav-btn${isHome || isReport ? "" : " hide-sm"}`} aria-current={isReport ? "page" : undefined} href={hrefOf({ view: "report" })} onClick={(e) => { e.preventDefault(); navigate({ view: "report" }); }}>Report</a>
          </nav>
        </div>
      </header>
      <main>
        {isGalaxy ? <Galaxy model={route.model} key={route.model ?? "entry"} /> : isWrapped ? <Wrapped author={route.author} key={route.author ?? "entry"} /> : route.model ? <ModelPage route={route} key={route.model} /> : route.dataset ? <DatasetPage id={route.dataset} key={route.dataset} /> : route.space ? <SpacePage id={route.space} key={route.space} /> : route.author ? <AuthorPage route={route} key={route.author} /> : isReport ? <Report /> : <Home />}
      </main>
      <footer class="foot">
        <div class="wrap">
          <span>
            Data from daily snapshots of <a href="https://huggingface.co/datasets/cfahlgren1/hub-stats" target="_blank" rel="noopener">cfahlgren1/hub-stats</a>,
            refreshed every day. An independent project, not affiliated with Hugging Face.
          </span>
          <span>Download counts follow the <a href="https://huggingface.co/docs/hub/models-download-stats" target="_blank" rel="noopener">Hub's own counting rules</a>.</span>
          <span>Sister project: <a href="https://paperpulse.ifsp.dev" target="_blank" rel="noopener">Paper Pulse</a>, the upvote history of every Hugging Face Daily Paper.</span>
          <span class="maker">
            Made by <a href="https://huggingface.co/tardellirs" target="_blank" rel="noopener">Tardelli Stekel</a>
            {" "}(<a href="https://huggingface.co/tardellirs" target="_blank" rel="noopener">@tardellirs</a> on Hugging Face,{" "}
            <a href="https://stekel.ifsp.dev/" target="_blank" rel="noopener">stekel.ifsp.dev</a>)
            <a class="gh" href="https://github.com/tardellirs/modelpulse" target="_blank" rel="noopener" aria-label="Source code on GitHub" title="Source code on GitHub">
              <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>
            </a>
          </span>
        </div>
      </footer>
    </>
  );
}

render(<App />, document.getElementById("app")!);
