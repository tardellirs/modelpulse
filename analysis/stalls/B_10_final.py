"""Stage 10: recommended rule (current | frozen-share | pair), optional high-water-mark correction, windows, skip_days vs published, roughness."""
import datetime as dt, json, math, statistics as S
import polars as pl
from B_common import *
pl.Config.set_tbl_rows(100); pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(220)
D = dt.date
meta = json.load(open("/data/meta.json")); skip_pub = set(meta["skip_days"])
hw = pl.read_parquet(f"{W}/hub_hwm.parquet").sort("day")
def expand(col):
    rows = []
    for x in hw.iter_rows(named=True):
        for k in range(x["gap"]): rows.append((x["day"] - dt.timedelta(days=k), "all", round(x[col] / x["gap"])))
    return pl.DataFrame(rows, schema=["day", "pipeline_tag", "dl"], orient="row").with_columns(pl.col("dl").cast(pl.Int64)).sort("day")
clip = expand("tot_clip"); hwm = expand("tot_hwm")
fz = pl.read_parquet(f"{W}/frozen.parquet"); share = {}
for row in fz.iter_rows(named=True):
    for k in range(row["gap"]): share[row["day"] - dt.timedelta(days=k)] = row["share"]
def analyse(hub, label):
    t = totals(hub); days = t["day"].to_list(); r = t["r"].to_list()
    f = [(x < LOW) or (share.get(d, 0) > .35) for x, d in zip(r, days)]
    pairs = pair_pairs(days, r, lo=0.7, hi=HIGH, s_lo=1.6, s_hi=2.6)
    w_u = windows_flags(days, r, f)
    w = merge(days, w_u + [sorted([a, b]) for a, b in pairs])
    return t, days, r, w, pairs
def smooth_tot(hub, ws): return st.smooth(hub, ws)
def stats(hub, label, wk=None):
    tt = totals(hub); rr = tt["r"].to_list(); dd = tt["day"].to_list(); n = len(dd) - 3
    return dict(series=label, out_07_13=sum(1 for v in rr[:n] if v < .7 or v > 1.3), lt05=sum(1 for v in rr[:n] if v < .5), gt1_5=sum(1 for v in rr[:n] if v > 1.5), gt2=sum(1 for v in rr[:n] if v > 2),
                max_r=round(max(rr[:n]), 2), std_log=round(S.pstdev([math.log(max(v, 1e-3)) for v in rr[:n]]), 4), total=int(tt["tot"].sum()))
t_c, days, r_c, w_c, p_c = analyse(clip, "clip")
t_h, days_h, r_h, w_h, p_h = analyse(hwm, "hwm")
cur_c = st.windows(clip)
rows = [stats(clip, "clip raw"), stats(smooth_tot(clip, cur_c), "clip + current rule"), stats(smooth_tot(clip, w_c), "clip + REC (cur|frozen|pair)"),
        stats(hwm, "hwm raw"), stats(smooth_tot(hwm, st.windows(hwm)), "hwm + current rule"), stats(smooth_tot(hwm, w_h), "hwm + REC")]
print(pl.DataFrame(rows))
ix = {d: i for i, d in enumerate(days)}; tot = t_c["tot"].to_list(); med = t_c["med"].to_list()
dow = [d.weekday() for d in days]
print("\n== REC windows on clip series (cur | frozen>0.35 | pair 0.7/1.3/sum1.6-2.6)")
for w in w_c:
    ii = [ix[d] for d in w]
    tags = []
    if any(r_c[i] < LOW for i in ii): tags.append("tot<0.3")
    if any(share.get(d, 0) > .35 for d in w): tags.append("frozen")
    if any(a in w for a, b in p_c): tags.append("pair")
    print(" ", w[0], w[0].strftime("%a"), "..", w[-1], len(w), "r", [round(r_c[i], 2) for i in ii], "+".join(tags), "| in cur rule:", any(d in {x for ww in cur_c for x in ww} for d in w))
sk = set(st.skip_days(w_c)); print("REC skip_days n=%d; published n=%d" % (len(sk), len(skip_pub)))
print(" new (not in published):", sorted(sk - skip_pub)); print(" in published but dropped by REC:", sorted(skip_pub - sk))
print("\n== REC on hwm series: windows differing from REC on clip")
sc = {(w[0], w[-1]) for w in w_c}; sh_ = {(w[0], w[-1]) for w in w_h}
print(" only clip:", sorted(map(str, sc - sh_)), "\n only hwm :", sorted(map(str, sh_ - sc)))
print("\n== clip vs hwm daily totals (M) and ratio")
th = totals(hwm); rh = th["r"].to_list(); toth = th["tot"].to_list()
for a, b in (("2025-05-17", "2025-05-24"), ("2026-06-11", "2026-06-21")):
    for d in days:
        if D.fromisoformat(a) <= d <= D.fromisoformat(b): print(d, d.strftime("%a"), "clip %.1f r %.2f | hwm %.1f r %.2f" % (tot[ix[d]] / 1e6, r_c[ix[d]], toth[ix[d]] / 1e6, rh[ix[d]]))
print("\n== days with r>1.5 left after REC+hwm:", [(str(d), round(v, 2)) for d, v in zip(totals(smooth_tot(hwm, w_h))["day"], totals(smooth_tot(hwm, w_h))["r"]) if v > 1.5])
print("== days with r>1.5 left after REC (clip):", [(str(d), round(v, 2)) for d, v in zip(totals(smooth_tot(clip, w_c))["day"], totals(smooth_tot(clip, w_c))["r"]) if v > 1.5])
print("\n== standing deficit (sum of running max - current, models below their max)")
for d in ("2025-05-18", "2025-05-20", "2025-05-21", "2025-06-30", "2026-06-12", "2026-06-13", "2026-06-19", "2026-07-30", "2026-10-04"):
    x = hw.filter(pl.col("day") == D.fromisoformat(d))
    if x.height: print(d, "deficit_M", round(x["deficit"][0] / 1e6, 1), "n_below", x["n_below"][0], "of", x["n"][0])
print("hwm vs clip grand total (B):", hw["tot_hwm"].sum() / 1e9, hw["tot_clip"].sum() / 1e9)
json.dump({"REC_clip": [[str(d) for d in w] for w in w_c], "REC_hwm": [[str(d) for d in w] for w in w_h]}, open(f"{W}/rules10.json", "w"))
