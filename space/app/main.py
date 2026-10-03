import logging
import os
import threading
from functools import lru_cache
from html import escape

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import jobs
from .data import Store

STATIC = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Model Pulse", docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
logging.basicConfig(level=logging.INFO)
store = Store()
def link_candidates():
    ranked = {r["id"] for rows in store.leaderboards.values() if isinstance(rows, list) for r in rows if r.get("id")}
    trending = set(jobs.trending_models())
    return store.top_ids(20_000) + sorted(ranked | trending), ranked | trending


linker = jobs.Linker(lambda mid: store.model(mid) is not None,
                     lambda mid: (store.model(mid) or {}).get("dl30"),
                     link_candidates)


def reload_store():
    global store
    store = Store()
    _hub.cache_clear()
    badge_svg.cache_clear()


@app.on_event("startup")
def start_jobs():
    if not os.environ.get("HF_TOKEN"):
        return
    sha = open(os.path.join(jobs.DATA_DIR, ".sha")).read().strip() if os.path.exists(os.path.join(jobs.DATA_DIR, ".sha")) else None
    threading.Thread(target=jobs.refresher, args=(sha, reload_store), daemon=True).start()
    threading.Thread(target=linker.run, daemon=True).start()
    if os.environ.get("RUN_DAILY", "1") == "1":
        threading.Thread(target=jobs.updater, args=(os.path.expanduser("~/work"),), daemon=True).start()

CACHE = {"Cache-Control": "public, max-age=3600"}


def j(data, status=200):
    return JSONResponse(data, status_code=status, headers=CACHE)


def clean(row):
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}


@app.get("/api/health")
def health():
    from datetime import date
    last = store.meta["days"][-1]
    lag = (date.today() - date.fromisoformat(last)).days
    return JSONResponse({"ok": lag <= 3, "last_day": last, "days_behind": lag, "models": store.meta["models"]},
                        status_code=200 if lag <= 3 else 503, headers={"Cache-Control": "no-store"})


@app.get("/api/meta")
def meta():
    return j({"days": len(store.meta["days"]), "first": store.meta["days"][0], "last": store.meta["days"][-1],
              "models": store.meta["models"], "families": store.meta["families"]})


@app.get("/api/model/{mid:path}")
def model(mid: str):
    m = store.model(mid)
    if not m:
        raise HTTPException(404, f"{mid} is not tracked. Models appear once they reach 10 downloads in 30 days or get a like.")
    mid = m["id"]
    linker.add(mid)
    out = {"model": clean(m), "series": store.series(mid), "children": [clean(c) for c in store.children(mid, 25)]}
    if (m.get("fam_members") or 0) >= 3:
        out["family"] = store.family_series(mid)
    return j(out)


@app.get("/api/author/{author}")
def author(author: str):
    s = store.author_series(author)
    models = [clean(r) for r in store.author_models(author)]
    if not models:
        raise HTTPException(404, f"No tracked models for {author}.")
    return j({"author": author, "series": s, "models": models})


@app.get("/api/search")
def search(q: str = Query("", max_length=120)):
    return j(store.search(q))


@lru_cache(maxsize=1)
def _hub():
    return store.hub()


@app.get("/api/hub")
def hub():
    return j(_hub())


@app.get("/api/leaderboards")
def leaderboards():
    return j(store.leaderboards)


# ---------- badge ----------

def human(n):
    if n is None:
        return "–"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{suf}" if v < 100 else f"{v:.0f}{suf}"
    return str(int(n))


def text_w(s, size=11, bold=False):
    # Verdana advance widths (em) for the characters badges use; bold Verdana is ~10% wider
    narrow, wide = "il.,:;|!1 /", "MWmw%▲▼"
    em = sum(0.36 if ch in narrow else 0.95 if ch in wide else 0.64 for ch in s)
    return em * size * (1.1 if bold else 1.0)


def daily_points(series, n=62):
    days, alls = series["day"], series["dl_all"]
    pts = [(d, a) for d, a in zip(days, alls) if a is not None][-(n + 1):]
    out = []
    for (d0, a0), (d1, a1) in zip(pts, pts[1:]):
        out.append(max(0, a1 - a0))
    if not out:
        return [v or 0 for v in series["dl30"][-n:]]
    # 7-day average, like the site's chart, so the sparkline reads as a trend
    return [sum(out[max(0, i - 6):i + 1]) / len(out[max(0, i - 6):i + 1]) for i in range(len(out))][6:]


@lru_cache(maxsize=4096)
def badge_svg(mid, metric, theme):
    m = store.model(mid)
    if not m:
        label, value, spark, delta = "model pulse", "not tracked", [], None
    else:
        s = store.series(m["id"])
        spark = daily_points(s)
        if metric == "all":
            label, value = "downloads", human(m["dl_all"])
        elif metric == "likes":
            label, value, spark = "likes", human(m["likes"]), (s["likes"][-56:] if s["likes"] else [])
        else:
            label, value = "downloads/mo", human(m["dl30"])
        delta = m.get("growth_7d")
    dark = theme == "dark"
    ink, paper, accent = ("#151833", "#ffffff", "#3B4CF5") if not dark else ("#F6F7FA", "#151833", "#8F9BFF")
    lw = 18 + text_w(label) + 10
    sw = 40 if len(spark) > 2 else 0
    dtext = "" if delta is None else (("▲" if delta >= 0 else "▼") + f"{abs(delta) * 100:.0f}%")
    rw = 10 + text_w(value, 11, True) + (10 + sw if sw else 0) + (8 + text_w(dtext, 10) if dtext else 0) + 10
    W, H = round(lw + rw), 22
    path = ""
    if sw:
        mx = max(spark) or 1
        x0 = lw + 10 + text_w(value, 11, True) + 10
        step = sw / (len(spark) - 1)
        coords = [(x0 + i * step, 16 - (v / mx) * 10) for i, v in enumerate(spark)]
        path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    dx = lw + rw - 10 - text_w(dtext, 10)
    dcol = "#1F9D55" if (delta or 0) >= 0 else "#D64545"
    if dark:
        dcol = "#5BD08A" if (delta or 0) >= 0 else "#FF7A7A"
    t = escape
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{t(label)}: {t(value)}">
<title>{t(mid)} · {t(label)}: {t(value)} · Model Pulse</title>
<rect width="{W}" height="{H}" rx="5" fill="{paper}" stroke="{ink}" stroke-opacity=".18"/>
<path d="M0 5a5 5 0 0 1 5-5h{lw - 5:.0f}v{H}H5a5 5 0 0 1-5-5z" fill="{ink}"/>
<path d="M6 11h2.5l1.5-4 2.5 8 1.5-4H16" fill="none" stroke="#FFD43B" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
<g font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
<text x="19" y="15" fill="{paper}">{t(label)}</text>
<text x="{lw + 10:.0f}" y="15" fill="{ink}" font-weight="bold">{t(value)}</text>
{f'<text x="{dx:.0f}" y="15" fill="{dcol}" font-size="10">{t(dtext)}</text>' if dtext else ''}
</g>
{f'<path d="{path}" fill="none" stroke="{accent}" stroke-width="1.4" stroke-linejoin="round"/>' if path else ''}
</svg>"""


@app.get("/badge/{mid:path}.svg")
def badge(mid: str, metric: str = "month", theme: str = "light"):
    svg = badge_svg(mid, metric if metric in ("month", "all", "likes") else "month", "dark" if theme == "dark" else "light")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=21600"})


# ---------- frontend ----------

if os.path.isdir(STATIC):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC, "assets")), name="assets")


@app.get("/{path:path}")
def spa(path: str):
    f = os.path.join(STATIC, path)
    if path and os.path.isfile(f) and os.path.abspath(f).startswith(os.path.abspath(STATIC)):
        return FileResponse(f)
    return FileResponse(os.path.join(STATIC, "index.html"))
