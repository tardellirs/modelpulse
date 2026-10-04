"""Server-rendered pages for search engines and link previews.

Every app URL gets its own title, description, canonical link, preview image and a plain-HTML summary of
the page, so it can be indexed without running JavaScript. The browser app then takes over the same page.
"""
import html
import json
import os
import re
from dataclasses import dataclass, field
from urllib.parse import quote

SITE = os.environ.get("SITE_ORIGIN", "https://modelpulse.ifsp.dev")
SPACE = "https://huggingface.co/spaces/tardellirs/model-pulse"
DEFAULT_IMAGE = SPACE + "/resolve/main/thumbnail-v3.png"
CREATOR = {"@type": "Person", "name": "Tardelli Stekel", "url": "https://huggingface.co/tardellirs"}
e = html.escape

def span(store):
    """First and last day of the data."""
    return store.meta["days"][0], store.meta["days"][-1]


RELATION = {"quantized": "a quantization", "finetune": "a fine-tune", "adapter": "an adapter", "merge": "a merge"}


def seg(mid: str) -> str:
    return "/".join(quote(p, safe="") for p in mid.split("/"))


def compact(n) -> str:
    if n is None:
        return "–"
    for v, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= v:
            return f"{n / v:.1f}".rstrip("0").rstrip(".") + s
    return str(int(n))


def full(n) -> str:
    return "–" if n is None else f"{int(n):,}"


def task(t) -> str:
    return t.replace("-", " ") if t else "model"


def a(href: str, text: str) -> str:
    return f'<a href="{e(href)}">{e(text)}</a>'


@dataclass
class Page:
    title: str
    description: str
    path: str
    body: str
    image: str = DEFAULT_IMAGE
    noindex: bool = False
    status: int = 200
    ld: list = field(default_factory=list)
    redirect: str | None = None


def crumbs(*items):
    """BreadcrumbList structured data from (name, path) pairs."""
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + p} for i, (n, p) in enumerate(items)]}


class Pages:
    def __init__(self, static_dir: str, report_path: str):
        self.static_dir = static_dir
        self.report_path = report_path
        self._template = None
        self._report = None

    # ---------- shell ----------

    def template(self):
        if self._template is None:
            t = open(os.path.join(self.static_dir, "index.html")).read()
            t = re.sub(r"<title>.*?</title>\s*", "", t, flags=re.S)
            t = re.sub(r'<meta name="description"[^>]*>\s*', "", t)
            # start downloading the heading and body fonts with the HTML, so text appears in its final face
            assets = os.path.join(self.static_dir, "assets")
            names = os.listdir(assets) if os.path.isdir(assets) else []
            for prefix in ("fredoka-latin-600-normal-", "source-sans-3-latin-400-normal-", "source-sans-3-latin-600-normal-",
                           "ibm-plex-mono-latin-500-normal-", "ibm-plex-mono-latin-600-normal-"):
                f = next((n for n in names if n.startswith(prefix) and n.endswith(".woff2")), None)
                if f:
                    t = t.replace("</head>", f'    <link rel="preload" href="/assets/{f}" as="font" type="font/woff2" crossorigin />\n  </head>', 1)
            self._template = t
        return self._template

    def render(self, p: Page) -> str:
        url = SITE + p.path
        head = [
            f"<title>{e(p.title)}</title>",
            f'<meta name="description" content="{e(p.description)}" />',
            f'<link rel="canonical" href="{e(url)}" />',
            '<meta name="msvalidate.01" content="0F762368C80A35B6AA04DBEC3D1E5D2B" />',
            '<meta property="og:site_name" content="Model Pulse" />',
            '<meta property="og:type" content="website" />',
            f'<meta property="og:title" content="{e(p.title)}" />',
            f'<meta property="og:description" content="{e(p.description)}" />',
            f'<meta property="og:url" content="{e(url)}" />',
            f'<meta property="og:image" content="{e(p.image)}" />',
            '<meta name="twitter:card" content="summary_large_image" />',
            f'<meta name="twitter:title" content="{e(p.title)}" />',
            f'<meta name="twitter:description" content="{e(p.description)}" />',
            f'<meta name="twitter:image" content="{e(p.image)}" />',
        ]
        if p.noindex:
            head.append('<meta name="robots" content="noindex, follow" />')
        for d in p.ld:
            head.append('<script type="application/ld+json">' + json.dumps(d).replace("</", "<\\/") + "</script>")
        t = self.template().replace("</head>", "    " + "\n    ".join(head) + "\n  </head>", 1)
        return t.replace('<div id="app"></div>', f'<div id="app"><main class="wrap ssr">{p.body}</main></div>', 1)

    # ---------- routing ----------

    def page(self, store, path: str, query) -> Page:
        # old query-string links (as used inside the Space) move to their real paths
        if query.get("model") or query.get("dataset") or query.get("space") or query.get("author") or query.get("view"):
            return Page("", "", "", "", redirect=self._query_path(query))
        parts = [p for p in path.split("/") if p]
        if not parts:
            return self.home(store)
        head, rest = parts[0], "/".join(parts[1:])
        if head == "model" and rest:
            return self.model(store, rest)
        if head == "dataset" and rest:
            return self.dataset(store, rest)
        if head == "space" and rest:
            return self.space(store, rest)
        if head == "author" and len(parts) == 2:
            return self.author(store, parts[1])
        if head == "galaxy":
            return self.galaxy(store, rest) if rest else self.galaxies(store)
        if head == "wrapped":
            return self.wrapped(parts[1] if len(parts) == 2 else None)
        if head == "report" and not rest:
            return self.report()
        return self.not_found("This page doesn't exist.")

    @staticmethod
    def _query_path(q):
        view, model, author, dataset, space = q.get("view"), q.get("model"), q.get("author"), q.get("dataset"), q.get("space")
        if view == "galaxy":
            path = f"/galaxy/{seg(model)}" if model else "/galaxy"
        elif view == "wrapped":
            path = f"/wrapped/{quote(author, safe='')}" if author else "/wrapped"
        elif view == "report":
            path = "/report"
        elif model:
            path = f"/model/{seg(model)}"
        elif dataset:
            path = f"/dataset/{seg(dataset)}"
        elif space:
            path = f"/space/{seg(space)}"
        elif author:
            path = f"/author/{quote(author, safe='')}"
        else:
            path = "/"
        return path + (f"?compare={quote(q['compare'], safe=',/')}" if q.get("compare") else "")

    def not_found(self, msg: str) -> Page:
        return Page("Not found · Model Pulse", msg, "/", f"<h1>Not found</h1><p>{e(msg)}</p><p>{a('/', 'Search all models')}</p>",
                    noindex=True, status=404)

    # ---------- pages ----------

    def home(self, store) -> Page:
        meta, lb = store.meta, store.leaderboards
        first, last = span(store)
        top = store.top_models(50)
        rows = lambda items, href, label, value: "".join(
            f"<li>{a(href(r), label(r))} {e(value(r))}</li>" for r in items)
        body = (
            "<h1>Model Pulse: download history for every Hugging Face model</h1>"
            f"<p>Daily downloads, likes and derivative families for {full(meta['models'])} models on the Hugging Face Hub, "
            f"every day since July 2024. Search any model to see how it grew, compare models, and follow its quantizations, "
            f"fine-tunes, adapters and merges.</p>"
            f"<p>{a('/galaxy', 'Model galaxies')} · {a('/wrapped', 'Model Pulse Wrapped')} · {a('/report', 'The 19-month report')}</p>"
            "<h2>Most downloaded models in the last 30 days</h2><ol>"
            + rows(top, lambda r: f"/model/{seg(r['id'])}", lambda r: r["id"], lambda r: f"{compact(r['dl30'])} downloads, {task(r['pipeline_tag'])}")
            + "</ol><h2>Fastest growing this week</h2><ol>"
            + rows((lb.get("gainers_7d") or [])[:25], lambda r: f"/model/{seg(r['id'])}", lambda r: r["id"], lambda r: f"{compact(r.get('dl_7d'))} downloads in 7 days")
            + "</ol><h2>Biggest families</h2><ol>"
            + rows((lb.get("families") or [])[:25], lambda r: f"/galaxy/{seg(r['id'])}", lambda r: r["id"], lambda r: f"{full(r.get('fam_members'))} derivatives")
            + "</ol><h2>Top organizations</h2><ol>"
            + rows((lb.get("authors_dl30") or [])[:25], lambda r: f"/author/{quote(r['author'], safe='')}", lambda r: r["author"], lambda r: f"{compact(r.get('dl30'))} downloads in 30 days")
            + "</ol>"
        )
        ld = [{
            "@context": "https://schema.org", "@type": "WebSite", "name": "Model Pulse", "url": SITE + "/",
            "potentialAction": {"@type": "SearchAction", "target": SITE + "/model/{model_id}", "query-input": "required name=model_id"},
        }, {
            "@context": "https://schema.org", "@type": "Dataset", "name": "Model Pulse: daily Hugging Face model downloads",
            "description": f"Daily download and like history for {full(meta['models'])} models on the Hugging Face Hub since {first}, updated every day.",
            "url": "https://huggingface.co/datasets/modelpulse/model-pulse-data", "creator": CREATOR, "isAccessibleForFree": True,
            "temporalCoverage": f"{first}/{last}", "keywords": ["Hugging Face", "model downloads", "machine learning", "statistics"],
        }]
        return Page("Model Pulse · Download history for every Hugging Face model",
                    f"Daily download history, likes and rankings for {compact(meta['models'])} models on the Hugging Face Hub, updated every day since July 2024.",
                    "/", body, ld=ld)

    def model(self, store, mid: str) -> Page:
        m = store.model(mid)
        if not m and "/" not in mid:
            from .repos import legacy_id
            m = store.model(legacy_id("models", mid) or "")
        if not m:
            return self.not_found(f"{mid} is not tracked. Models appear once they reach 10 downloads in 30 days or get a like.")
        if m["id"] != mid:
            return Page("", "", "", "", redirect=f"/model/{seg(m['id'])}")
        path = f"/model/{seg(mid)}"
        author, name = (mid.split("/", 1) + [""])[:2] if "/" in mid else ("", mid)
        dl30, dl_all, dl7 = m.get("dl30"), m.get("dl_all"), m.get("dl_7d")
        fam = m.get("fam_members") or 0
        tsk = task(m.get("pipeline_tag"))
        params = m.get("params")
        size = f"{params / 1e9:.1f}B-parameter " if params and params >= 1e9 else (f"{params / 1e6:.0f}M-parameter " if params else "")

        desc = f"{mid} was downloaded {compact(dl30)} times in the last 30 days"
        desc += f" and {compact(dl_all)} times in total" if dl_all else ""
        desc += f", with {full(fam)} derivatives" if fam else ""
        desc += ". Daily download history since July 2024, likes, rankings and model family."

        kind = f"{size}{tsk}"
        article = "an" if re.match(r"(?i)[aeio]|8|11|18", kind) else "a"
        facts = [f"<p><b>{e(mid)}</b> is {article} {e(kind)} model"
                 + (f" by {a('/author/' + quote(author, safe=''), author)}" if author else "") + ". "
                 f"In the last 30 days it was downloaded <b>{full(dl30)}</b> times ({full(dl7)} in the last 7 days)"
                 + (f", and <b>{full(dl_all)}</b> times in total" if dl_all else "") + ".</p>"]
        if m.get("rank_dl30"):
            facts.append(f"<p>It ranks #{full(m['rank_dl30'])} on the Hub by monthly downloads"
                         + (f" and #{full(m['rank_task'])} among {e(tsk)} models" if m.get("rank_task") and m.get("pipeline_tag") else "") + ".</p>")
        if m.get("likes") is not None:
            facts.append(f"<p>It has {full(m['likes'])} likes" + (f", {full(m['likes_7d'])} of them in the last week" if m.get("likes_7d") else "") + ".</p>")
        bases = m.get("base_ids") or []
        if bases:
            facts.append(f"<p>It is {RELATION.get(m.get('base_relation'), 'a derivative')} of {a('/model/' + seg(bases[0]), bases[0])}.</p>")
        if fam:
            facts.append(
                f"<p>{full(fam)} models build on {e(name)}: {full(m.get('n_quantized'))} quantized, {full(m.get('n_finetune'))} fine-tuned, "
                f"{full(m.get('n_adapter'))} adapters and {full(m.get('n_merge'))} merges. Together with the original they were downloaded "
                f"{full(m.get('fam_dl30'))} times in the last 30 days. {a('/galaxy/' + seg(mid), 'See the ' + name + ' galaxy')}.</p>")
        kids = store.children(mid, 12)
        if kids:
            facts.append("<h2>Most downloaded derivatives</h2><ul>" + "".join(
                f"<li>{a('/model/' + seg(c['id']), c['id'])} ({e(c['relation'] or 'derivative')}), {compact(c['dl30'])} downloads in 30 days</li>" for c in kids) + "</ul>")
        facts.append(f"<p>{a('https://huggingface.co/' + mid, 'Open ' + mid + ' on Hugging Face')}</p>")
        crumb = [("Model Pulse", "/")] + ([(author, f"/author/{quote(author, safe='')}")] if author else []) + [(name, path)]
        body = (f'<nav>{" / ".join(a(p, n) for n, p in crumb[:-1])}</nav>'
                f"<h1>{e(mid)} download history</h1>" + "".join(facts))
        return Page(f"{mid} downloads: daily history and stats · Model Pulse", desc, path, body,
                    image=f"{SITE}/og/model/{seg(mid)}.png", ld=[crumbs(*crumb)])

    def dataset(self, store, rid: str) -> Page:
        repos = getattr(store, "repos", None)
        d = repos.dataset(rid) if repos else None
        if not d and repos and "/" not in rid:
            from .repos import legacy_id
            d = repos.dataset(legacy_id("datasets", rid) or "")
        if not d:
            return self.not_found(f"{rid} is not tracked. Datasets appear once they reach 10 downloads in 30 days or get a like.")
        if d["id"] != rid:
            return Page("", "", "", "", redirect=f"/dataset/{seg(d['id'])}")
        path = f"/dataset/{seg(rid)}"
        author, name = rid.split("/", 1) if "/" in rid else ("", rid)
        task_name = task(d.get("pipeline_tag")) if d.get("pipeline_tag") else ""
        models = repos.used_by("dataset", rid, "model", 12)
        spaces = repos.used_by("dataset", rid, "space", 8)
        desc = (f"{rid} was downloaded {compact(d.get('dl30'))} times in the last 30 days"
                + (f" and {compact(d.get('dl_all'))} times in total" if d.get("dl_all") else "")
                + (f". {full(models['count'])} models are trained on it" if models["count"] else "")
                + ". Daily download history since July 2024, rankings and the models and Spaces that use it.")
        body = [f'<nav>{a("/", "Model Pulse")}' + (f' / {a("/author/" + quote(author, safe=""), author)}' if author else "") + "</nav>",
                f"<h1>{e(rid)} download history</h1>",
                f"<p><b>{e(rid)}</b> is a{'n' if task_name[:1] in 'aeio' and task_name else ''} {e(task_name + ' ' if task_name else '')}dataset on the Hugging Face Hub. "
                f"In the last 30 days it was downloaded <b>{full(d.get('dl30'))}</b> times ({full(d.get('dl_7d'))} in the last 7 days)"
                + (f", and <b>{full(d.get('dl_all'))}</b> times in total" if d.get("dl_all") else "")
                + (f". It ranks #{full(d.get('rank_dl30'))} among datasets by monthly downloads" if d.get("rank_dl30") else "") + ".</p>"]
        if d.get("description"):
            body.append(f"<p>{e(d['description'])}</p>")
        if models["count"]:
            body.append(f"<h2>Models trained on {e(name)}</h2><p>{full(models['count'])} models list it as training data.</p><ul>" + "".join(
                f"<li>{a('/model/' + seg(m['id']), m['id'])} {compact(m.get('dl30'))} downloads in 30 days</li>" for m in models["top"]) + "</ul>")
        if spaces["count"]:
            body.append(f"<h2>Spaces using {e(name)}</h2><ul>" + "".join(
                f"<li>{a('/space/' + seg(s['id']), s.get('title') or s['id'])} {full(s.get('likes'))} likes</li>" for s in spaces["top"]) + "</ul>")
        body.append(f"<p>{a('https://huggingface.co/datasets/' + rid, 'Open ' + rid + ' on Hugging Face')}</p>")
        crumb = [("Model Pulse", "/")] + ([(author, f"/author/{quote(author, safe='')}")] if author else []) + [(name, path)]
        return Page(f"{rid} downloads: daily history and stats · Model Pulse", desc, path, "".join(body),
                    image=f"{SITE}/og/dataset/{seg(rid)}.png", ld=[crumbs(*crumb)])

    def space(self, store, rid: str) -> Page:
        repos = getattr(store, "repos", None)
        s = repos.space(rid) if repos else None
        if not s:
            return self.not_found(f"{rid} is not tracked. Spaces appear once they get a like.")
        if s["id"] != rid:
            return Page("", "", "", "", redirect=f"/space/{seg(s['id'])}")
        path = f"/space/{seg(rid)}"
        author, name = rid.split("/", 1) if "/" in rid else ("", rid)
        title = s.get("title") or name
        uses = repos.space_uses(rid)
        desc = (f"{title} ({rid}) has {full(s.get('likes'))} likes on Hugging Face, {full(s.get('likes_7d'))} of them in the last 7 days. "
                "Likes over time since July 2024, its ranking and the models and datasets it uses.")
        body = [f'<nav>{a("/", "Model Pulse")}' + (f' / {a("/author/" + quote(author, safe=""), author)}' if author else "") + "</nav>",
                f"<h1>{e(title)}: likes over time</h1>",
                f"<p><b>{e(rid)}</b> is a{'n' if (s.get('sdk') or '')[:1] in 'aeio' and s.get('sdk') else ''} {e((s.get('sdk') or '') + ' ')}Space on the Hugging Face Hub. "
                f"It has <b>{full(s.get('likes'))}</b> likes, {full(s.get('likes_7d'))} in the last 7 days and {full(s.get('likes_30d'))} in the last 30, "
                f"and ranks #{full(s.get('rank_likes'))} among Spaces by likes.</p>"]
        if s.get("short_description"):
            body.append(f"<p>{e(s['short_description'])}</p>")
        if uses["models"] or uses["datasets"]:
            body.append("<h2>What it uses</h2><ul>" + "".join(
                f"<li>{a('/model/' + seg(m['id']), m['id'])} (model)</li>" for m in uses["models"]) + "".join(
                f"<li>{a('/dataset/' + seg(x['id']), x['id'])} (dataset)</li>" for x in uses["datasets"]) + "</ul>")
        body.append(f"<p>{a('https://huggingface.co/spaces/' + rid, 'Open ' + rid + ' on Hugging Face')}</p>")
        crumb = [("Model Pulse", "/")] + ([(author, f"/author/{quote(author, safe='')}")] if author else []) + [(title, path)]
        return Page(f"{title}: likes over time · {rid} · Model Pulse", desc, path, "".join(body),
                    image=f"{SITE}/og/space/{seg(rid)}.png", ld=[crumbs(*crumb)])

    def author(self, store, name: str) -> Page:
        author = store.find_author(name)
        if not author:
            return self.not_found(f"No tracked models for {name}.")
        if author != name:
            return Page("", "", "", "", redirect=f"/author/{quote(author, safe='')}")
        path = f"/author/{quote(author, safe='')}"
        s = store.author_summary(author)
        models = store.author_models(author, 100)
        top = ", ".join(m["id"].split("/", 1)[-1] for m in models[:3])
        body = (f'<nav>{a("/", "Model Pulse")}</nav><h1>{e(author)} on Hugging Face: model downloads</h1>'
                f"<p>{e(author)} has {full(s['models'])} tracked models, downloaded {full(s['dl30'])} times in the last 30 days"
                + (f" and {full(s['dl_all'])} times in total" if s["dl_all"] else "") + f". {a('/wrapped/' + quote(author, safe=''), author + ' Wrapped: the last 12 months')}.</p>"
                "<h2>Models by downloads in the last 30 days</h2><ol>" + "".join(
                    f"<li>{a('/model/' + seg(m['id']), m['id'])} {compact(m['dl30'])} downloads, {e(task(m.get('pipeline_tag')))}</li>" for m in models) + "</ol>")
        return Page(f"{author} on Hugging Face: model downloads and rankings · Model Pulse",
                    f"Download history for {full(s['models'])} models by {author} on the Hugging Face Hub, with {compact(s['dl30'])} downloads in the last 30 days. Top models: {top}.",
                    path, body, image=f"{SITE}/og/author/{quote(author, safe='')}.png", ld=[crumbs(("Model Pulse", "/"), (author, path))])

    def galaxies(self, store) -> Page:
        gs = store.galaxies(40)
        body = (f'<nav>{a("/", "Model Pulse")}</nav><h1>Model galaxies</h1>'
                "<p>Pick a base model and see every model built on it, from quantizations and fine-tunes to adapters and merges, drawn as a galaxy.</p>"
                "<h2>The biggest galaxies</h2><ol>" + "".join(
                    f"<li>{a('/galaxy/' + seg(g['id']), g['id'])} {full(g['fam_members'])} models</li>" for g in gs) + "</ol>")
        return Page("Model galaxies: every model built on Llama, Qwen, FLUX and more · Model Pulse",
                    "See every quantization, fine-tune, adapter and merge built on a Hugging Face base model, drawn as a galaxy and sized by downloads.",
                    "/galaxy", body)

    def galaxy(self, store, mid: str) -> Page:
        m = store.model(mid)
        if not m:
            return self.not_found(f"{mid} is not tracked.")
        if m["id"] != mid:
            return Page("", "", "", "", redirect=f"/galaxy/{seg(m['id'])}")
        path = f"/galaxy/{seg(mid)}"
        fam = m.get("fam_members") or 0
        kids = store.children(mid, 25)
        body = (f'<nav>{a("/", "Model Pulse")} / {a("/galaxy", "Galaxies")}</nav><h1>The {e(mid)} galaxy</h1>'
                f"<p>{full(fam)} models are built on {a('/model/' + seg(mid), mid)}: {full(m.get('n_quantized'))} quantized, "
                f"{full(m.get('n_finetune'))} fine-tuned, {full(m.get('n_adapter'))} adapters and {full(m.get('n_merge'))} merges. "
                f"Together they were downloaded {full(m.get('fam_dl30'))} times in the last 30 days.</p>"
                + ("<h2>Most downloaded direct derivatives</h2><ul>" + "".join(
                    f"<li>{a('/model/' + seg(c['id']), c['id'])} ({e(c['relation'] or 'derivative')}), {compact(c['dl30'])} downloads in 30 days</li>" for c in kids) + "</ul>" if kids else ""))
        return Page(f"{mid} galaxy: {full(fam)} models built on it · Model Pulse",
                    f"Every model built on {mid}: {full(m.get('n_quantized'))} quantizations, {full(m.get('n_finetune'))} fine-tunes, "
                    f"{full(m.get('n_adapter'))} adapters and {full(m.get('n_merge'))} merges, drawn as a galaxy and sized by downloads.",
                    path, body, image=f"{SITE}/og/galaxy/{seg(mid)}.png" if fam else f"{SITE}/og/model/{seg(mid)}.png", noindex=fam < 20,
                    ld=[crumbs(("Model Pulse", "/"), ("Galaxies", "/galaxy"), (mid, path))])

    def wrapped(self, author: str | None) -> Page:
        if author:
            path = f"/wrapped/{quote(author, safe='')}"
            return Page(f"{author}'s last 12 months on Hugging Face · Model Pulse Wrapped",
                        f"{author}'s year on the Hugging Face Hub in six cards: downloads, the #1 model, the biggest week, the models built on theirs, and their rank.",
                        path, f'<nav>{a("/wrapped", "Model Pulse Wrapped")}</nav><h1>{e(author)} Wrapped</h1>'
                              f"<p>{e(author)}'s last 12 months on the Hugging Face Hub. {a('/author/' + quote(author, safe=''), 'See all models by ' + author)}.</p>",
                        image=f"{SITE}/og/author/{quote(author, safe='')}.png", noindex=True)
        return Page("Model Pulse Wrapped: your last 12 months on Hugging Face",
                    "Your last 12 months on the Hugging Face Hub in six cards: total downloads, your #1 model, your biggest week, the models built on yours, and where you rank.",
                    "/wrapped", f'<nav>{a("/", "Model Pulse")}</nav><h1>Model Pulse Wrapped</h1>'
                                "<p>Type a Hugging Face username or organization to see its last 12 months on the Hub.</p>")

    def report(self) -> Page:
        if self._report is None:
            import markdown
            md = open(self.report_path).read()
            h = markdown.markdown(md, extensions=["tables"])
            h = h.replace("<img ", '<img loading="lazy" width="1200" height="675" ')
            h = h.replace("https://huggingface.co/spaces/tardellirs/model-pulse?model=", "/model/")
            first = re.sub(r"<[^>]+>", "", re.search(r"<p>(.*?)</p>", h, re.S).group(1)).strip()
            title = re.search(r"<h1>(.*?)</h1>", h, re.S)
            self._report = (re.sub(r"<[^>]+>", "", title.group(1)) if title else "What 19 months of daily downloads say about the Hub", first, h)
        title, first, h = self._report
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": title, "author": CREATOR,
               "image": SITE + "/report/01-hub.png", "datePublished": "2026-10-03", "publisher": CREATOR}]
        return Page(f"{title} · Model Pulse", first[:300], "/report", f'<article class="report">{h}</article>',
                    image=SITE + "/report/01-hub.png", ld=ld)

    # ---------- for AI search tools ----------

    def llms_txt(self, store) -> str:
        first, last = span(store)
        return f"""# Model Pulse

> Daily download history, likes and derivative families for {full(store.meta['models'])} models on the Hugging Face Hub, plus download history for datasets and likes for Spaces, from {first} to {last}, updated every day. Made by Tardelli Stekel (huggingface.co/tardellirs).

Every page states its figures in plain text: downloads in the last 30 days, the last 7 days and all time, likes, the model's rank on the Hub and within its task, and how many quantizations, fine-tunes, adapters and merges build on it.

## Pages

- [Any model]({SITE}/model/Qwen/Qwen3-8B): {SITE}/model/{{org}}/{{name}}, download history and stats for one model
- [Any dataset]({SITE}/dataset/HuggingFaceFW/fineweb): {SITE}/dataset/{{org}}/{{name}}, download history, and the models trained on it and Spaces using it
- [Any Space]({SITE}/space/HuggingFaceFW/finephrase): {SITE}/space/{{org}}/{{name}}, likes over time and the models and datasets it uses
- [Any author or organization]({SITE}/author/Qwen): {SITE}/author/{{name}}, all of its models ranked by downloads
- [Model galaxies]({SITE}/galaxy): every model built on a base model, e.g. {SITE}/galaxy/meta-llama/Llama-3.1-8B
- [Report]({SITE}/report): what 19 months of daily downloads say about the Hub
- [Rankings]({SITE}/): most downloaded, fastest growing, biggest families and top organizations

## Data

- [Open dataset](https://huggingface.co/datasets/modelpulse/model-pulse-data): one row per model per day
- [JSON API]({SITE}/api/model/Qwen/Qwen3-8B): /api/model/{{org}}/{{name}}, /api/author/{{name}}, /api/leaderboards
- [Hugging Face Space]({SPACE})
"""

    # ---------- sitemap ----------

    PER_FILE = 25_000

    def sitemap_index(self, store, n_models: int) -> str:
        last = span(store)[1]
        files = ["static", "authors", "galaxies"] + [f"models-{i + 1}" for i in range((n_models + self.PER_FILE - 1) // self.PER_FILE)]
        if getattr(store, "repos", None) and store.repos.ok:
            files += ["datasets-1", "datasets-2", "spaces-1", "spaces-2"]
        items = "".join(f"<sitemap><loc>{SITE}/sitemaps/{f}.xml</loc><lastmod>{last}</lastmod></sitemap>" for f in files)
        return f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</sitemapindex>'

    def sitemap(self, store, name: str, n_models: int) -> str | None:
        last = span(store)[1]
        if name == "static":
            paths = ["/", "/galaxy", "/wrapped", "/report"]
        elif name == "authors":
            paths = [f"/author/{quote(x, safe='')}" for x in store.sitemap_authors(20_000)]
        elif name == "galaxies":
            paths = [f"/galaxy/{seg(x)}" for x in store.sitemap_galaxies(10_000)]
        elif m := re.fullmatch(r"(datasets|spaces)-(\d+)", name):
            repos = getattr(store, "repos", None)
            if not repos or not repos.ok:
                return None
            k = int(m.group(2)) - 1
            ids = repos.top_ids(m.group(1), 2 * self.PER_FILE)[k * self.PER_FILE:(k + 1) * self.PER_FILE]
            if not ids:
                return None
            paths = [f"/{m.group(1)[:-1]}/{seg(x)}" for x in ids]
        elif m := re.fullmatch(r"models-(\d+)", name):
            k = int(m.group(1)) - 1
            ids = store.top_ids(n_models)[k * self.PER_FILE:(k + 1) * self.PER_FILE]
            if not ids:
                return None
            paths = [f"/model/{seg(x)}" for x in ids]
        else:
            return None
        items = "".join(f"<url><loc>{e(SITE + p)}</loc><lastmod>{last}</lastmod></url>" for p in paths)
        return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
