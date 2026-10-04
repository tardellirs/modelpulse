"""Stage 4: Q4 conservation per episode (frozen models), what happened on 2026-06-25 / 2026-08-01, Q5 real spikes."""
import datetime as dt, json, math
import polars as pl, statistics as S
nan = float('nan')
from B_common import *
pl.Config.set_tbl_rows(100); pl.Config.set_tbl_cols(30); pl.Config.set_fmt_str_lengths(50); pl.Config.set_tbl_width_chars(250)
D = dt.date
raw = raw_hub(); t = totals(raw); days = t["day"].to_list(); r = t["r"].to_list(); tot = t["tot"].to_list(); med = t["med"].to_list()
ix = {d: i for i, d in enumerate(days)}
rules = {k: [[D.fromisoformat(s) for s in w] for w in ws] for k, ws in json.load(open(f"{W}/rules.json")).items()}
fz = pl.read_parquet(f"{W}/frozen.parquet"); share = {}
for row in fz.iter_rows(named=True):
    for k in range(row["gap"]): share[row["day"] - dt.timedelta(days=k)] = row["share"]
models = pl.read_parquet("/data/models.parquet", columns=["id", "author", "pipeline_tag", "library_name"])
big = pl.read_parquet(f"{W}/big_ids.parquet")
bb = pl.read_parquet(f"{W}/big_deltas.parquet").join(big.select("id"), on="id", how="semi")
bb = bb.with_columns((pl.col("delta").clip(lower_bound=0) / pl.col("gap")).alias("v"), (pl.col("prev") + dt.timedelta(days=1)).alias("start"))
print("big models", big.height, "rows", bb.height)
allwin = {d for ws in rules.values() for w in ws for d in w}
exc = set(allwin)
# also exclude every day flagged by any seed (cur/frozen) plus their immediate neighbours
for d in days:
    if r[ix[d]] < 0.7 or share.get(d, 0) > 0.35: exc |= {d, d + dt.timedelta(days=1), d - dt.timedelta(days=1)}
rowkeys = bb.select("day", "start").unique()
exc_rows = {(a, b) for a, b in rowkeys.iter_rows() if any((a + dt.timedelta(days=k)) in exc for k in range((b - a).days + 1))}
bb = bb.with_columns(pl.struct("start", "day").map_elements(lambda s: (s["start"], s["day"]) in exc_rows, return_dtype=pl.Boolean).alias("exc"))
tagmap = models.select("id", pl.col("pipeline_tag").fill_null("other"))

def baseline(a, b, pad=28):
    s = bb.filter((pl.col("start") >= a - dt.timedelta(days=pad)) & (pl.col("day") <= b + dt.timedelta(days=pad)) & ~pl.col("exc"))
    return s.group_by("id").agg(pl.col("v").median().alias("base"))
def actual(a, b, ids=None):
    s = bb.filter((pl.col("start") <= b) & (pl.col("day") >= a))
    s = s.with_columns(((pl.min_horizontal(pl.col("day"), pl.lit(b)) - pl.max_horizontal(pl.col("start"), pl.lit(a))).dt.total_days() + 1).alias("ov"))
    return s.group_by("id").agg((pl.col("v") * pl.col("ov")).sum().alias("act"))
def perday(a, b):
    """per-model per calendar day v over [a,b]"""
    rows = []
    s = bb.filter((pl.col("start") <= b) & (pl.col("day") >= a)).select("id", "start", "day", "v")
    out = []
    for k in range((b - a).days + 1):
        d = a + dt.timedelta(days=k)
        out.append(s.filter((pl.col("start") <= d) & (pl.col("day") >= d)).select("id", pl.lit(d).alias("d"), "v"))
    return pl.concat(out)

# ----- episodes: cluster windows of every rule that overlap
allw = sorted([(w[0], w[-1]) for ws in rules.values() for w in ws])
eps = []
for a, b in allw:
    if eps and a <= eps[-1][1] + dt.timedelta(days=0): eps[-1] = (eps[-1][0], max(b, eps[-1][1]))
    else: eps.append((a, b))
print("episodes", len(eps))
def inrule(k, d): return any(d in w for w in rules[k])
out_rows = []
prof_lines = []
for a, b in eps:
    n = (b - a).days + 1
    span = [a + dt.timedelta(days=k) for k in range(n)]
    dstar = max(span, key=lambda d: share.get(d, 0))
    base = baseline(a, b); act = actual(a, b)
    row = bb.filter((pl.col("start") <= dstar) & (pl.col("day") >= dstar)).select("id", "delta")
    F = set(row.filter(pl.col("delta") == 0)["id"].to_list())
    x = base.join(act, on="id", how="left").with_columns(pl.col("act").fill_null(0), pl.col("id").is_in(list(F)).alias("F"))
    x = x.filter(pl.col("base") > 0).with_columns((pl.col("base") * n).alias("exp"), (pl.col("act") / (pl.col("base") * n)).alias("ratio"))
    def agg(f):
        s = x.filter(f); 
        return (s.height, float(s["act"].sum() / s["exp"].sum()) if s.height else float("nan"), float(s["ratio"].median()) if s.height else float("nan"), float((s["ratio"] >= 0.8).mean()) if s.height else float("nan"))
    nF, rF, mF, fF = agg(pl.col("F")); nG, rG, mG, fG = agg(~pl.col("F"))
    # control: same F, windows shifted by multiples of 7 days that avoid excluded days
    ctrl = []
    Fids = x.filter(pl.col("F"))
    for sft in (-28, -21, -14, -7, 7, 14, 21, 28):
        a2, b2 = a + dt.timedelta(days=sft), b + dt.timedelta(days=sft)
        if any((a2 + dt.timedelta(days=k)) in exc for k in range(n)): continue
        a3 = actual(a2, b2).join(Fids.select("id", "exp"), on="id", how="semi")
        if Fids.height: ctrl.append(float(a3["act"].sum() / Fids["exp"].sum()))
    # per-day profile relative to baseline
    pdv = perday(a - dt.timedelta(days=1), b + dt.timedelta(days=2)).join(base, on="id")
    prof = {}
    for nm, ids in (("F", F), ("G", None)):
        s = pdv.filter(pl.col("id").is_in(list(F))) if nm == "F" else pdv.filter(~pl.col("id").is_in(list(F)))
        g = s.group_by("d").agg(pl.col("v").sum(), pl.col("base").sum()).sort("d")
        prof[nm] = [round(v / bs, 2) for v, bs in zip(g["v"], g["base"])]
    hub_exp = sum(med[ix[d]] for d in span)
    out_rows.append(dict(episode=f"{a}..{b}", n=n, dstar=str(dstar), dow=dstar.strftime("%a"), r_dstar=round(r[ix[dstar]], 2), share=round(share.get(dstar, nan), 2),
                         cur=any(inrule("current", d) for d in span), pair=any(inrule("pair", d) for d in span), fz=any(inrule("frozen", d) for d in span),
                         nF=nF, F_act_over_exp=round(rF, 3), F_med_ratio=round(mF, 3), F_ge08=round(fF, 2), nG=nG, G_act_over_exp=round(rG, 3),
                         ctrlF_med=round(float(S.median(ctrl)), 3) if ctrl else None, ctrl_n=len(ctrl), hub_win_over_med=round(sum(tot[ix[d]] for d in span) / hub_exp, 3)))
    prof_lines.append(f"{a}..{b} d*={dstar}  days {a - dt.timedelta(days=1)}..{b + dt.timedelta(days=2)}  F-profile(v/base) {prof['F']}  G-profile {prof['G']}")
print("\n== Q4 conservation per episode (F = big models with delta==0 on d* = the day of max frozen share; ratio = window actual / (baseline*n); baseline = median v of the model over +-28d outside any window/dip)")
print(pl.DataFrame(out_rows))
pl.DataFrame(out_rows).write_csv(f"{W}/q4_episodes.csv")
print("\n".join(prof_lines))

# ----- what happened on pair-only days
def explain(d, partner=None, topn=12):
    i = ix[d]
    a = b = d
    base = baseline(a, b); act = actual(a, b)
    x = base.join(act, on="id", how="left").with_columns(pl.col("act").fill_null(0)).with_columns((pl.col("act") - pl.col("base")).alias("exc")).join(tagmap, on="id", how="left").join(models.select("id", "author"), on="id", how="left")
    dev = tot[i] - med[i]
    print(f"\n### {d} {d.strftime('%a')} total {tot[i]:,.0f} median15 {med[i]:,.0f} ratio {r[i]:.2f} deviation {dev:,.0f}; frozen share {share.get(d, float('nan')):.3f}; same weekday +-7d ratios: {[round(r[ix[d + dt.timedelta(days=k)]], 2) for k in (-14, -7, 7, 14) if d + dt.timedelta(days=k) in ix]}")
    xs = x.sort("exc", descending=(dev > 0))
    print("big-model excess sum", f"{x['exc'].sum():,.0f}", "(models n=", x.height, ") ; top rows:")
    top = xs.head(topn).with_columns((pl.col("exc") / dev).round(3).alias("share_of_dev"))
    print(top.select("id", "pipeline_tag", "author", "base", "act", "exc", "share_of_dev"))
    print("top1 share of hub deviation", round(float(xs["exc"][0] / dev), 3), " top5", round(float(xs["exc"].head(5).sum() / dev), 3), " top20", round(float(xs["exc"].head(20).sum() / dev), 3))
    # tags: hub raw per tag vs tag median of surrounding days
    tg = raw.filter((pl.col("day") >= d - dt.timedelta(days=14)) & (pl.col("day") <= d + dt.timedelta(days=14)) & ~pl.col("day").is_in(list(exc)))
    tm = tg.group_by("pipeline_tag").agg(pl.col("dl").median().alias("tag_med"))
    td = raw.filter(pl.col("day") == d).select("pipeline_tag", pl.col("dl").alias("tag_day")).join(tm, on="pipeline_tag").with_columns((pl.col("tag_day") - pl.col("tag_med")).alias("dev"), (pl.col("tag_day") / pl.col("tag_med")).round(2).alias("ratio")).sort("dev", descending=(dev > 0))
    print("tags (largest deviations):"); print(td.head(6)); print("tag share of total deviation top1", round(float(td["dev"][0] / dev), 2))
    print("number of big models with act<0.2*base:", x.filter(pl.col("act") < 0.2 * pl.col("base")).height, " act>2*base:", x.filter(pl.col("act") > 2 * pl.col("base")).height, " of", x.height)
    return dict(day=str(d), top1=float(xs["exc"][0] / dev), top5=float(xs["exc"].head(5).sum() / dev))
summ = []
for d in ["2026-06-25", "2026-06-24", "2026-06-26", "2026-08-01", "2026-07-31", "2026-08-02"]:
    summ.append(explain(D.fromisoformat(d)))
print("\n== concentration over all candidate days (top1/top5 share of hub deviation by big models)")
cd = "2025-07-16 2025-08-13 2025-10-01 2025-10-08 2025-11-26 2026-02-11 2026-04-29 2026-06-25 2026-07-29 2026-08-01 2026-08-05 2026-08-12 2025-07-23 2025-09-17 2025-11-05 2025-12-17 2026-01-28 2026-05-12 2026-07-08 2026-09-02".split()
rows = []
for s in cd:
    d = D.fromisoformat(s); i = ix[d]; dev = tot[i] - med[i]
    base = baseline(d, d); act = actual(d, d)
    x = base.join(act, on="id", how="left").with_columns(pl.col("act").fill_null(0)).with_columns((pl.col("act") - pl.col("base")).alias("exc")).sort("exc", descending=(dev > 0))
    rows.append(dict(day=s, dow=d.strftime("%a"), r=round(r[i], 2), share=round(share.get(d, nan), 2), dev=int(dev), top1=round(float(x["exc"][0] / dev), 2), top5=round(float(x["exc"].head(5).sum() / dev), 2),
                     bigsum=round(float(x["exc"].sum() / dev), 2), n_dead=x.filter(pl.col("act") < 0.2 * pl.col("base")).height, n=x.height))
print(pl.DataFrame(rows))

# ----- Q5 spikes
print("\n== Q5 days with raw ratio > 1.5 (flag: in any rule window / within 3d of a seed)")
seeds = [d for d in days if r[ix[d]] < 0.7 or share.get(d, 0) > 0.35]
rows = []
for d in days:
    i = ix[d]
    if r[i] > 1.5:
        near = min([abs((d - s).days) for s in seeds] or [99])
        rows.append(dict(day=str(d), dow=d.strftime("%a"), r=round(r[i], 2), tot=int(tot[i]), nearest_seed_days=near, **{k: inrule(k, d) for k in rules}))
print(pl.DataFrame(rows))
for s in ["2025-05-21"] + [x["day"] for x in rows if x["r"] > 2 and x["day"] != "2025-05-21"]:
    d = D.fromisoformat(s); explain(d, topn=10)
