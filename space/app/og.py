"""Link-preview images (1200x630) for model pages, in the site's look."""
import io
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(__file__), "fonts")
PAPER, SURF, INK, MUTED, MARK = "#ECE9E2", "#FBFAF5", "#1B1B1F", "#6E6C66", "#FFD21E"
W, H = 1200, 630


def font(name: str, size: int):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def compact(n) -> str:
    if n is None:
        return "–"
    for v, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= v:
            return f"{n / v:.1f}".rstrip("0").rstrip(".") + s
    return str(int(n))


def card(d: ImageDraw.ImageDraw, box, fill, r=22, shadow=7):
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0 + shadow, y0 + shadow, x1 + shadow, y1 + shadow), r, fill=INK)
    d.rounded_rectangle(box, r, fill=fill, outline=INK, width=4)


def fit(d, text, name, size, width, min_size=30):
    while size > min_size and d.textlength(text, font=font(name, size)) > width:
        size -= 2
    f = font(name, size)
    while d.textlength(text, font=f) > width and len(text) > 4:
        text = text[:-2] + "…"
    return text, f


def header(d: ImageDraw.ImageDraw, right: str):
    d.rounded_rectangle((60, 50, 124, 114), 16, fill=INK)
    d.rounded_rectangle((54, 44, 118, 108), 16, fill=MARK, outline=INK, width=5)
    d.line([(66, 78), (78, 78), (85, 60), (96, 96), (103, 78), (108, 78)], fill=INK, width=5, joint="curve")
    d.text((140, 54), "Model Pulse", font=font("fredoka-600.ttf", 40), fill=INK)
    d.text((W - 60, 66), right, font=font("ibm-plex-mono-500.ttf", 22), fill=MUTED, anchor="ra")


def png(img) -> bytes:
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def author_card(author: str, summary: dict, models: list) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    header(d, "on Hugging Face")
    text, f = fit(d, author, "fredoka-600.ttf", 84, W - 140)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((52, 160, 52 + tw + 32, 160 + f.size + 26), 14, fill=MARK)
    d.text((68, 168), text, font=f, fill=INK)
    stats = [(compact(summary.get("dl30")), "downloads, last 30 days"), (compact(summary.get("dl_all")), "downloads all time"),
             (f"{summary.get('models', 0):,}", "tracked models")]
    x, y, w = 60, 300, 330
    for i, (v, label) in enumerate(stats):
        card(d, (x, y, x + w, y + 128), SURF if i else "#3B6FF5")
        d.text((x + 24, y + 12), v, font=font("fredoka-600.ttf", 60), fill="#FFFFFF" if i == 0 else INK)
        d.text((x + 26, y + 90), label, font=font("ibm-plex-mono-400.ttf", 19), fill="#E8EEFF" if i == 0 else MUTED)
        x += w + 35
    y = 458
    for k, m in enumerate(models[:3]):
        name = m["id"].split("/", 1)[-1]
        name, f2 = fit(d, name, "source-sans-3-600.ttf", 28, 760, 20)
        d.text((60, y), f"{k + 1}.", font=font("ibm-plex-mono-500.ttf", 24), fill=MUTED)
        d.text((100, y - 3), name, font=f2, fill=INK)
        d.text((W - 60, y), f"{compact(m.get('dl30'))}/mo", font=font("ibm-plex-mono-500.ttf", 24), fill=INK, anchor="ra")
        y += 37
    d.text((60, H - 40), "modelpulse.ifsp.dev", font=font("ibm-plex-mono-500.ttf", 20), fill=MUTED)
    return png(img)


def model_card(m: dict, series: dict) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    header(d, "download history")

    mid = m["id"]
    org, name = mid.split("/", 1) if "/" in mid else ("", mid)
    if org:
        d.text((60, 150), org + "/", font=font("ibm-plex-mono-500.ttf", 28), fill=MUTED)
    text, f = fit(d, name, "fredoka-600.ttf", 78, W - 140)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((52, 192, 52 + tw + 32, 192 + f.size + 26), 14, fill=MARK)
    d.text((68, 200), text, font=f, fill=INK)

    # numbers
    stats = [(compact(m.get("dl30")), "downloads, last 30 days"), (compact(m.get("dl_all")), "downloads all time"), (compact(m.get("likes")), "likes")]
    if not m.get("dl_all"):
        stats.pop(1)
    x, y, w = 60, 318, 330
    for i, (v, label) in enumerate(stats):
        card(d, (x, y, x + w, y + 128), SURF if i else "#3B6FF5")
        d.text((x + 24, y + 12), v, font=font("fredoka-600.ttf", 60), fill="#FFFFFF" if i == 0 else INK)
        d.text((x + 26, y + 90), label, font=font("ibm-plex-mono-400.ttf", 19), fill="#E8EEFF" if i == 0 else MUTED)
        x += w + 35

    # 30-day downloads, one bar a week over the last six months
    vals = [v for v in (series.get("dl30") or []) if v is not None]
    pts = vals[::-1][::7][:26][::-1]
    if len(pts) >= 4:
        bx0, bx1, by0, by1 = 60, W - 60, 478, 566
        mx = max(pts) or 1
        gap = 8
        bw = (bx1 - bx0 - gap * (len(pts) - 1)) / len(pts)
        for k, v in enumerate(pts):
            h = max(5, (v / mx) * (by1 - by0))
            xx = bx0 + k * (bw + gap)
            d.rounded_rectangle((xx, by1 - h, xx + bw, by1), 4, fill=MARK if k == len(pts) - 1 else SURF, outline=INK, width=3)

    d.text((60, H - 46), "modelpulse.ifsp.dev", font=font("ibm-plex-mono-500.ttf", 20), fill=MUTED)
    d.text((W - 60, H - 46), "30-day downloads, last 6 months", font=font("ibm-plex-mono-400.ttf", 18), fill=MUTED, anchor="ra")
    return png(img)


def space_card(s: dict, series: dict) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    header(d, "likes over time")
    d.text((60, 150), s["id"], font=font("ibm-plex-mono-500.ttf", 26), fill=MUTED)
    text, f = fit(d, s.get("title") or s["id"].split("/")[-1], "fredoka-600.ttf", 70, W - 140)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((52, 192, 52 + tw + 32, 192 + f.size + 26), 14, fill=MARK)
    d.text((68, 200), text, font=f, fill=INK)
    stats = [(compact(s.get("likes")), "likes"), (f"+{compact(s.get('likes_7d') or 0)}", "last 7 days"), (f"+{compact(s.get('likes_30d') or 0)}", "last 30 days")]
    x, y, w = 60, 318, 330
    for i, (v, label) in enumerate(stats):
        card(d, (x, y, x + w, y + 128), SURF if i else "#2F8F5B")
        d.text((x + 24, y + 12), v, font=font("fredoka-600.ttf", 60), fill="#FFFFFF" if i == 0 else INK)
        d.text((x + 26, y + 90), label, font=font("ibm-plex-mono-400.ttf", 19), fill="#E3F2E9" if i == 0 else MUTED)
        x += w + 35
    # likes gained per week, last six months
    days, likes = series.get("day") or [], series.get("likes") or []
    pts = [(dd, v) for dd, v in zip(days, likes) if v is not None]
    weekly = []
    for k in range(26, 0, -1):
        lo, hi = len(pts) - 7 * k - 1, len(pts) - 7 * (k - 1) - 1
        if lo >= 0 and hi < len(pts):
            weekly.append(max(0, pts[hi][1] - pts[lo][1]))
    if len(weekly) >= 4 and max(weekly) > 0:
        bx0, bx1, by0, by1 = 60, W - 60, 478, 566
        mx, gap = max(weekly), 8
        bw = (bx1 - bx0 - gap * (len(weekly) - 1)) / len(weekly)
        for k, v in enumerate(weekly):
            h = max(5, (v / mx) * (by1 - by0))
            xx = bx0 + k * (bw + gap)
            d.rounded_rectangle((xx, by1 - h, xx + bw, by1), 4, fill=MARK if k == len(weekly) - 1 else SURF, outline=INK, width=3)
    d.text((60, H - 46), "modelpulse.ifsp.dev", font=font("ibm-plex-mono-500.ttf", 20), fill=MUTED)
    d.text((W - 60, H - 46), "likes gained per week, last 6 months", font=font("ibm-plex-mono-400.ttf", 18), fill=MUTED, anchor="ra")
    return png(img)


# ---------- galaxy (an orrery, like the site's) ----------

REL_COLORS = ["#3b6ff5", "#ff8a1f", "#2f8f5b", "#a35bf0"]   # quantized, fine-tuned, adapters, merges
REL_LABELS = ["Quantized", "Fine-tuned", "Adapters", "Merges"]
SECTOR_ORDER = [1, 2, 0, 3]
RING = [0, 330, 590, 800, 960]


def _hash(i: int, s: int) -> float:
    h = (i * 2654435761 + (s + 1) * 2246822519) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 3266489917) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296


def galaxy_layout(g: dict):
    """The site's orrery layout: one orbit per generation, one sector per kind, each subtree inside its parent's slice."""
    import math
    parent, rel, dl = g["nodes"]["parent"], g["nodes"]["rel"], g["nodes"]["dl30"]
    n = len(parent)
    rel = [r if r >= 0 else 1 for r in rel]
    depth, kids, sub = [0] * n, [[] for _ in range(n)], [1] * n
    for i in range(1, n):
        depth[i] = min(4, depth[parent[i]] + 1)
        kids[parent[i]].append(i)
    for i in range(n - 1, 0, -1):
        sub[parent[i]] += sub[i]
    weight = lambda i: 1 + (sub[i] - 1) ** 0.8
    ang, span = [0.0] * n, [0.0] * n

    def spread(ids, a0, a1):
        ids = sorted(ids, key=lambda i: (-weight(i), -(dl[i] or 0)))
        arranged = []
        for k, i in enumerate(ids):
            (arranged.insert(0, i) if k % 2 else arranged.append(i))
        total = sum(weight(i) for i in arranged) or 1
        a = a0
        for i in arranged:
            w = (a1 - a0) * weight(i) / total
            ang[i], span[i] = a + w / 2, w
            a += w

    groups = [[i for i in kids[0] if rel[i] == r] for r in range(4)]
    present = [r for r in SECTOR_ORDER if groups[r]]
    gap = 0.05 if len(present) > 1 else 0
    raw = [math.sqrt(sum(weight(i) for i in groups[r])) for r in present]
    tot = sum(raw) or 1
    shares = [max(0.12 if len(present) > 1 else 1, v / tot) for v in raw]
    st, usable = sum(shares), 2 * math.pi - gap * len(present)
    a = -math.pi / 2 - shares[0] / st * usable / 2
    sectors = []
    for r, sh in zip(present, shares):
        w = sh / st * usable
        sectors.append((r, a, a + w, len(groups[r])))
        spread(groups[r], a, a + w)
        a += w + gap
    for p in range(1, n):
        if kids[p]:
            spread(kids[p], ang[p] - span[p] / 2, ang[p] + span[p] / 2)
    max_dl = max([dl[i] or 0 for i in range(1, n)] + [1])
    size = [0.0] + [min(24, 1.6 + 22 * math.sqrt((dl[i] or 0) / max_dl)) if (dl[i] or 0) > 0 else 1.2 for i in range(1, n)]
    gens = [0] * 5
    for i in range(1, n):
        gens[depth[i]] += 1
    band = [max(14, min(120, math.sqrt(c) * 1.3)) for c in gens]
    xy = [(0.0, 0.0)] * n
    for i in range(1, n):
        big = size[i] >= 5
        r = RING[depth[i]] + (0 if big else (_hash(i, 1) - 0.5) * band[depth[i]])
        t = ang[i] if big else ang[i] + (_hash(i, 2) - 0.5) * min(span[i] * 0.9, 0.08)
        xy[i] = (math.cos(t) * r, math.sin(t) * r)
    deepest = max([d for d in range(1, 5) if gens[d]] or [1])
    extent = RING[deepest] + band[deepest] / 2 + 60
    return {"n": n, "xy": xy, "size": size, "rel": rel, "sectors": sectors, "rings": RING[1:deepest + 1], "extent": extent, "ang": ang}


def galaxy_card(g: dict) -> bytes:
    import math
    S = 2                                                     # draw at 2x, then shrink: smooth edges
    WW, HH = W * S, H * S
    base = Image.new("RGBA", (WW, HH), PAPER)
    L = galaxy_layout(g)
    cx, cy = WW - 330 * S, HH // 2
    k = (HH / 2 - 26 * S) / L["extent"]
    P = lambda x, y: (cx + x * k, cy + y * k)
    over = Image.new("RGBA", (WW, HH), (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    R = (L["extent"] - 30) * k
    for r, a0, a1, _ in L["sectors"]:                         # faint sector wedges
        c = REL_COLORS[r]
        o.pieslice((cx - R, cy - R, cx + R, cy + R), math.degrees(a0), math.degrees(a1), fill=c + "14")
    base = Image.alpha_composite(base, over)
    d = ImageDraw.Draw(base)
    for rr in L["rings"]:                                     # dashed orbits
        rad = rr * k
        steps = int(2 * math.pi * rad / (9 * S))
        for s in range(0, steps, 2):
            a0, a1 = 360 * s / steps, 360 * (s + 1) / steps
            d.arc((cx - rad, cy - rad, cx + rad, cy + rad), a0, a1, fill="#1b1b1f55", width=S)
    xy, size, rel, dl = L["xy"], L["size"], L["rel"], g["nodes"]["dl30"]
    order = sorted(range(1, L["n"]), key=lambda i: -(dl[i] or 0))
    parent = g["nodes"]["parent"]
    links = Image.new("RGBA", (WW, HH), (0, 0, 0, 0))
    ld = ImageDraw.Draw(links)
    for i in order[:120]:
        if (dl[i] or 0) > 0:
            ld.line([P(*xy[parent[i]]), P(*xy[i])], fill="#1b1b1f30", width=S)
    dots = Image.new("RGBA", (WW, HH), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for i in range(1, L["n"]):                                # the belt
        if size[i] < 5:
            x, y = P(*xy[i])
            s = max(1.0, size[i] * S * 0.9)
            dd.ellipse((x - s, y - s, x + s, y + s), fill=REL_COLORS[rel[i]] + "88")
    base = Image.alpha_composite(Image.alpha_composite(base, links), dots)
    d = ImageDraw.Draw(base)
    for i in reversed(order):                                 # planets, biggest on top
        if size[i] >= 5:
            x, y = P(*xy[i])
            s = size[i] * S * 0.9
            d.ellipse((x - s, y - s, x + s, y + s), fill=REL_COLORS[rel[i]], outline=INK, width=2 * S)
    sr = 20 * S                                               # the sun, with the site's hard shadow
    d.ellipse((cx - sr + 4 * S, cy - sr + 4 * S, cx + sr + 4 * S, cy + sr + 4 * S), fill=INK)
    d.ellipse((cx - sr, cy - sr, cx + sr, cy + sr), fill=MARK, outline=INK, width=3 * S)
    lab = font("source-sans-3-600.ttf", 13 * S)
    boxes = [(cx - sr, cy - sr, cx + sr, cy + sr)]
    shown = 0
    for i in order[:200]:                                     # a few names, clear of each other
        if shown >= 7 or not (dl[i] or 0):
            break
        name = g["nodes"]["id"][i].split("/")[-1]
        x, y = P(*xy[i])
        s = size[i] * S * 0.9
        w = d.textlength(name, font=lab)
        right = math.cos(L["ang"][i]) >= -0.1
        bx = x + s + 5 * S if right else x - s - 5 * S - w
        box = (bx - 2, y - 10 * S, bx + w + 2, y + 10 * S)
        if bx < 600 * S or box[2] > WW - 10 * S or box[1] < 10 * S or box[3] > HH - 10 * S:
            continue
        if any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in boxes):
            continue
        boxes.append(box)
        d.text((bx, y), name, font=lab, fill=INK, anchor="lm", stroke_width=3 * S, stroke_fill=PAPER)
        shown += 1
    # the words, on the left
    d.rounded_rectangle((60 * S, 50 * S, 124 * S, 114 * S), 16 * S, fill=INK)
    d.rounded_rectangle((54 * S, 44 * S, 118 * S, 108 * S), 16 * S, fill=MARK, outline=INK, width=5 * S)
    d.line([(66 * S, 78 * S), (78 * S, 78 * S), (85 * S, 60 * S), (96 * S, 96 * S), (103 * S, 78 * S), (108 * S, 78 * S)], fill=INK, width=5 * S, joint="curve")
    d.text((140 * S, 54 * S), "Model Pulse Galaxy", font=font("fredoka-600.ttf", 36 * S), fill=INK)
    rid = g["root"]["id"]
    org, name = rid.split("/", 1) if "/" in rid else ("", rid)
    if org:
        d.text((60 * S, 150 * S), org + "/", font=font("ibm-plex-mono-500.ttf", 24 * S), fill=MUTED)
    text, f = fit(d, name, "fredoka-600.ttf", 62 * S, 470 * S, 28 * S)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((52 * S, 188 * S, 52 * S + tw + 30 * S, 188 * S + f.size + 24 * S), 14 * S, fill=MARK)
    d.text((66 * S, 196 * S), text, font=f, fill=INK)
    d.text((60 * S, 300 * S), f"{g['total']:,}", font=font("fredoka-600.ttf", 64 * S), fill=INK)
    d.text((62 * S, 378 * S), "models built on it", font=font("ibm-plex-mono-500.ttf", 21 * S), fill=MUTED)
    counts = [sum(1 for i in range(1, L["n"]) if rel[i] == r) for r in range(4)]
    y = 440 * S
    for r in SECTOR_ORDER:
        if not counts[r]:
            continue
        d.ellipse((60 * S, y - 9 * S, 78 * S, y + 9 * S), fill=REL_COLORS[r], outline=INK, width=2 * S)
        d.text((92 * S, y), f"{REL_LABELS[r]}  {counts[r]:,}", font=font("ibm-plex-mono-500.ttf", 20 * S), fill=INK, anchor="lm")
        y += 34 * S
    d.text((60 * S, HH - 46 * S), "modelpulse.ifsp.dev", font=font("ibm-plex-mono-500.ttf", 20 * S), fill=MUTED)
    return png(base.convert("RGB").resize((W, H), Image.LANCZOS))
