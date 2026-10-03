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


def model_card(m: dict, series: dict) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # logo and wordmark
    d.rounded_rectangle((60, 50, 124, 114), 16, fill=INK)
    d.rounded_rectangle((54, 44, 118, 108), 16, fill=MARK, outline=INK, width=5)
    d.line([(66, 78), (78, 78), (85, 60), (96, 96), (103, 78), (108, 78)], fill=INK, width=5, joint="curve")
    d.text((140, 54), "Model Pulse", font=font("fredoka-600.ttf", 40), fill=INK)
    d.text((W - 60, 66), "download history", font=font("ibm-plex-mono-500.ttf", 22), fill=MUTED, anchor="ra")

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
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
