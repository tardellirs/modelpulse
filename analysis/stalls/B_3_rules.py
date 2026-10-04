"""Stage 3: Q1 raw vs published, Q2 rules & agreement, Q3 effect of smoothing."""
import datetime as dt, json, math
import polars as pl, statistics as S
nan = float('nan')
def q(v, ps):
    v = sorted(v); return [v[min(len(v)-1, int(p*(len(v)-1)+0.5))] for p in ps]
def mean(v): v = list(v); return sum(v)/len(v)
def std(v): return S.pstdev(list(v))
from B_common import *
pl.Config.set_tbl_rows(200); pl.Config.set_tbl_cols(30); pl.Config.set_fmt_str_lengths(60); pl.Config.set_tbl_width_chars(250)
D = dt.date
raw = raw_hub()
pub = pl.read_parquet("/data/hub_series.parquet")
meta = json.load(open("/data/meta.json")); skip_pub = meta["skip_days"]
t = totals(raw); days = t["day"].to_list(); r = t["r"].to_list(); tot = t["tot"].to_list(); med = t["med"].to_list()
dayidx = {d: i for i, d in enumerate(days)}
print("raw days", days[0], days[-1], len(days))

# ---------- Q1
wins_cur = st.windows(raw)
print("\n== current rule on RAW series: windows")
for w in wins_cur: print(w[0], w[-1], len(w), [round(r[dayidx[d]], 2) for d in w])
print("skip_days from raw windows :", st.skip_days(wins_cur))
print("published meta skip_days   :", skip_pub)
print("only in raw-rule skip:", sorted(set(st.skip_days(wins_cur)) - set(skip_pub)), " only in published:", sorted(set(skip_pub) - set(st.skip_days(wins_cur))))
pt = pub.group_by("day").agg(pl.col("dl").sum().alias("pub")).sort("day")
j = t.select("day", "tot").join(pt, on="day", how="full", coalesce=True).sort("day")
inwin = {d for w in wins_cur for d in w} | {dt.date.fromisoformat(s) + dt.timedelta(days=k) for s in skip_pub for k in (0, 1)}
j = j.with_columns(pl.col("day").is_in(list(inwin)).alias("inwin"), ((pl.col("pub") - pl.col("tot")) / pl.col("tot")).alias("rel"))
o = j.filter(~pl.col("inwin"))
print("\n== Q1 outside windows: days", o.height, "missing in either:", o.filter(pl.col("tot").is_null() | pl.col("pub").is_null()).height)
oo = o.drop_nulls()
print("max |rel diff|", oo["rel"].abs().max(), " n>1e-4:", oo.filter(pl.col("rel").abs() > 1e-4).height, " n>1e-3:", oo.filter(pl.col("rel").abs() > 1e-3).height)
print(oo.filter(pl.col("rel").abs() > 1e-4))
print("sum raw", j.filter(pl.col("tot").is_not_null())["tot"].sum(), " sum pub", pub["dl"].sum())
print("window sums raw vs published")
for w in wins_cur:
    a = j.filter(pl.col("day").is_in(w)); print(w[0], w[-1], a["tot"].sum(), a["pub"].sum())
print("days only in one series:", j.filter(pl.col("tot").is_null() | pl.col("pub").is_null()))
# per-tag comparison outside windows
pt2 = pub.filter(~pl.col("day").is_in(list(inwin))).join(raw, on=["day", "pipeline_tag"], how="full", coalesce=True, suffix="_raw").fill_null(0)
bad = pt2.filter((pt2["dl"] - pt2["dl_raw"]).abs() > 2)
print("per-tag rows differing >2 outside windows:", bad.height, "of", pt2.height, " abs diff sum", (pt2["dl"] - pt2["dl_raw"]).abs().sum(), "of", pt2["dl"].sum())

# ---------- Q2 rules
fz = pl.read_parquet(f"{W}/frozen.parquet")
share = {}
for row in fz.iter_rows(named=True):
    for k in range(row["gap"]): share[row["day"] - dt.timedelta(days=k)] = row["share"]
sh = [share.get(d, float("nan")) for d in days]
FZ = 0.35
f_cur = [x < LOW for x in r]
f_fz = [(not math.isnan(s)) and s > FZ for s in sh]
pairs = pair_pairs(days, r)
print("\n== pair candidates (low<0.7, nbr>1.3, sum in [1.6,2.4]):")
for a, b in pairs: print(a, a.strftime("%a"), round(r[dayidx[a]], 2), "|", b, round(r[dayidx[b]], 2), "sum", round(r[dayidx[a]] + r[dayidx[b]], 2), "share", round(share.get(a, nan), 3))
print("looser pair (sum 1.3-3.0) extra:", [(a, b, round(r[dayidx[a]] + r[dayidx[b]], 2)) for a, b in pair_pairs(days, r, s_lo=1.3, s_hi=3.0) if (a, b) not in pairs])
w_pair = merge(days, wins_cur + [[a, b] if a < b else [b, a] for a, b in pairs])
w_fz = windows_flags(days, r, f_fz)
w_fzc = windows_flags(days, r, [x or y for x, y in zip(f_fz, f_cur)])
rules = {"current": wins_cur, "pair": w_pair, "frozen": w_fz, "frozen+cur": w_fzc}
# also pair+frozen union
rules["pair|frozen"] = merge(days, w_pair + w_fzc)
print("\n== windows per rule")
for k, ws in rules.items():
    print(f"--- {k}: {len(ws)} windows, {sum(len(w) for w in ws)} days, skip_days {len(st.skip_days(ws))}")
    for w in ws:
        print("  ", w[0], w[0].strftime("%a"), "->", w[-1], len(w), "r=", [round(r[dayidx[d]], 2) for d in w], "share=", [round(share.get(d, nan), 2) for d in w])
json.dump({k: [[str(d) for d in w] for w in ws] for k, ws in rules.items()}, open(f"{W}/rules.json", "w"))

# agreement table over seeds
pairlow = {a for a, b in pairs}; pairpart = {b for a, b in pairs}
seed = sorted({d for d, x in zip(days, f_cur) if x} | {d for d, x in zip(days, f_fz) if x} | pairlow | pairpart)
mem = {k: {d for w in ws for d in w} for k, ws in rules.items()}
print("\n== agreement table (seed days: r<0.3, frozen>0.35, pair low/partner). flag: seed rule fires; W: in a window of that rule")
print("date  dow  r  share | cur_flag pair_flag fz_flag | W_cur W_pair W_fz W_fz+cur")
rev = {D.fromisoformat(s) for s in "2025-07-16 2025-08-13 2025-10-01 2025-10-08 2025-11-26 2026-02-11 2026-04-29 2026-06-25 2026-07-29 2026-08-01 2026-08-05 2026-08-12".split()}
extra = {D.fromisoformat(s) for s in "2025-07-23 2025-09-17 2025-11-05 2025-12-17 2026-01-28 2026-05-12 2026-07-08 2026-09-02".split()}
rows = []
for d in seed:
    i = dayidx[d]
    rows.append(dict(day=d, dow=d.strftime("%a"), r=round(r[i], 2), share=round(share.get(d, nan), 3), cur=f_cur[i], pair=d in pairlow, pair_partner=d in pairpart, fz=f_fz[i],
                     W_cur=d in mem["current"], W_pair=d in mem["pair"], W_fz=d in mem["frozen"], W_fzc=d in mem["frozen+cur"], in_review=d in rev, in_extra=d in extra))
ag = pl.DataFrame(rows); print(ag)
ag.write_csv(f"{W}/agreement.csv")
missing = [d for d in sorted(rev | extra) if d not in seed]
print("reviewer/extra days not in seed:", missing)
for d in sorted(rev | extra | {D(2025, 5, 21)}):
    i = dayidx[d]; print(d, d.strftime("%a"), "r", round(r[i], 2), "prev", round(r[i-1], 2), "next", round(r[i+1], 2), "share", round(share.get(d, nan), 3), "share_prev", round(share.get(d - dt.timedelta(days=1), nan), 3), "share_next", round(share.get(d + dt.timedelta(days=1), nan), 3))
# threshold sensitivity for frozen share
print("\nfrozen-share sensitivity (days flagged / n windows):")
for th in (0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
    fl = [(not math.isnan(s)) and s > th for s in sh]; print(th, sum(fl), len(windows_flags(days, r, fl)))
sv = [s for s in sh if not math.isnan(s)]
print("share distribution (all days) quantiles .5 .9 .95 .99:", [round(x,3) for x in q(sv, [.5, .9, .95, .99])])
print("share days <0.3 total flagged (cur):", [(str(d), round(share.get(d, nan), 2)) for d, x in zip(days, f_cur) if x])

# ---------- Q3 effect
allwin = {d for ws in rules.values() for w in ws for d in w}
def stats(h, label):
    tt = totals(h); rr = tt["r"].to_list(); dd = tt["day"].to_list()
    x = [v for v, d in zip(rr, dd) if d <= days[-4]]
    mx = S.median(x)
    return dict(rule=label, outside_07_13=sum(1 for v in x if v < .7 or v > 1.3), below07=sum(1 for v in x if v < .7), above13=sum(1 for v in x if v > 1.3), below05=sum(1 for v in x if v < .5), above2=sum(1 for v in x if v > 2),
                std_log=round(std([math.log(max(v, 1e-3)) for v in x]), 4), mad=round(S.median([abs(v - mx) for v in x]), 4), sumtot=int(tt["tot"].sum()))
res = [stats(raw, "raw")]; sm = {}
for k, ws in rules.items():
    sm[k] = st.smooth(raw, ws); res.append(stats(sm[k], k))
print("\n== Q3 roughness (ratio to centred 15d median of the series itself; days up to last-3)"); print(pl.DataFrame(res))
dow = [d.weekday() for d in days]
outside = [d not in allwin for d in days]
wk = [mean([r[i] for i in range(len(days)) if outside[i] and dow[i] == k]) for k in range(7)]
print("\nweekday mean ratio (days outside every rule's windows, from raw), Mon..Sun:", [round(x, 3) for x in wk])
for k in ["raw"] + list(rules):
    h = raw if k == "raw" else sm[k]; rr = totals(h)["r"].to_list()
    print(f"  {k:12s} weekday means over ALL days:", [round(mean([rr[i] for i in range(len(days)) if dow[i] == q_]), 3) for q_ in range(7)], "  std of log(r / weekday-profile):",
          round(std([math.log(rr[i] / wk[dow[i]]) for i in range(len(days)) if rr[i] > 0]), 4),
          " n days |r/wk-1|>0.3:", sum(1 for i in range(len(days) - 3) if abs(rr[i] / wk[dow[i]] - 1) > 0.3))
print("\n== per-window: raw ratio / weekday-expected vs smoothed; last col = window total / sum(median*wk)")
for k, ws in rules.items():
    rs = totals(sm[k])["r"].to_list()
    print("---", k)
    for w in ws:
        ii = [dayidx[d] for d in w]
        rawdev = [round(r[i] / wk[dow[i]], 2) for i in ii]; smdev = [round(rs[i] / wk[dow[i]], 2) for i in ii]
        wsum_ratio = sum(tot[i] for i in ii) / sum(med[i] * wk[dow[i]] for i in ii)
        print(f"  {w[0]}..{w[-1]} n={len(w)} wk-adj raw {rawdev} smoothed {smdev}  ratio {wsum_ratio:.2f}")
