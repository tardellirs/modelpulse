"""Stage 6: tight-extension variants and final recommended rule: windows, roughness, skip_days vs published."""
import datetime as dt, json, math, statistics as S
import polars as pl
from B_common import *
pl.Config.set_tbl_rows(100); pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(220)
raw = raw_hub(); t = totals(raw); days = t["day"].to_list(); r = t["r"].to_list(); tot = t["tot"].to_list(); med = t["med"].to_list(); ix = {d: i for i, d in enumerate(days)}
fz = pl.read_parquet(f"{W}/frozen.parquet"); share = {}
for row in fz.iter_rows(named=True):
    for k in range(row["gap"]): share[row["day"] - dt.timedelta(days=k)] = row["share"]
sh = [share.get(d, 0.0) for d in days]
meta = json.load(open("/data/meta.json")); skip_pub = set(meta["skip_days"])

def windows_tight(flag, prev_thr=1.5, hi=HIGH):
    """flagged runs + the next day always + following days only while consecutively > hi (no look-ahead jump); day before if > prev_thr."""
    n = len(days); out = []; k = 0
    while k < n:
        if not flag[k]: k += 1; continue
        a = b = k
        while b + 1 < n and flag[b + 1]: b += 1
        e = b + 1
        while e + 1 < n and e + 1 <= b + 4 and r[e] > hi and r[e + 1] > hi: e += 1
        while a - 1 >= 0 and a - 1 >= k - 1 and r[a - 1] > prev_thr and not flag[a - 1]: a -= 1
        if e >= n - 1: break
        if out and (days[a] - out[-1][-1]).days <= 2:
            first = out[-1][0]; out[-1] = [d for d in days if first <= d <= days[e]]
        else: out.append(days[a:e + 1])
        k = e + 1
    return out
f_cur = [x < LOW for x in r]; f_fz = [s > 0.35 for s in sh]; f_u = [a or b for a, b in zip(f_cur, f_fz)]
rules = {"current": st.windows(raw), "frozen+cur": windows_flags(days, r, f_u), "frozen+cur TIGHT": windows_tight(f_u), "frozen+cur TIGHT prev1.3": windows_tight(f_u, prev_thr=1.3)}
pairs = pair_pairs(days, r, s_lo=1.3, s_hi=3.0)
rules["TIGHT + pair(1.3-3.0)"] = merge(days, rules["frozen+cur TIGHT"] + [sorted([a, b]) for a, b in pairs])
# pair-only extras (not frozen): which pairs add on top of frozen+cur TIGHT
mem = lambda ws: {d for w in ws for d in w}
extra = [(a, b, round(r[ix[a]], 2), round(r[ix[b]], 2)) for a, b in pairs if a not in mem(rules["frozen+cur TIGHT"])]
print("pairs (sum 1.3-3.0) not already inside frozen+cur TIGHT windows:", extra)
allwin = set().union(*[mem(w) for w in rules.values()]); dow = [d.weekday() for d in days]
wk = [S.mean([r[i] for i in range(len(days)) if d_ not in allwin and dow[i] == k]) for k in range(7) for d_ in [None]] if False else [S.mean([r[i] for i in range(len(days)) if days[i] not in allwin and dow[i] == k]) for k in range(7)]
print("weekday profile outside windows", [round(x, 3) for x in wk])
def stats(h, label):
    tt = totals(h); rr = tt["r"].to_list(); dd = tt["day"].to_list(); x = [v for v, d in zip(rr, dd) if d <= days[-4]]
    adj = [rr[i] / wk[dow[i]] for i in range(len(rr) - 3)]
    return dict(rule=label, wins=0, days_in_wins=0, out_07_13=sum(1 for v in x if v < .7 or v > 1.3), lt07=sum(1 for v in x if v < .7), gt13=sum(1 for v in x if v > 1.3), lt05=sum(1 for v in x if v < .5), gt2=sum(1 for v in x if v > 2),
                std_logr_wkadj=round(S.pstdev([math.log(max(v, 1e-3)) for v in adj]), 4), wkadj_outside_0_75_1_25=sum(1 for v in adj if v < .75 or v > 1.25))
rows = [stats(raw, "raw")]
for k, ws in rules.items():
    s = stats(st.smooth(raw, ws), k); s["wins"] = len(ws); s["days_in_wins"] = sum(len(w) for w in ws); rows.append(s)
print(pl.DataFrame(rows))
for k in ["frozen+cur TIGHT", "frozen+cur TIGHT prev1.3", "TIGHT + pair(1.3-3.0)"]:
    print(f"\n--- {k}: windows (r raw; wk-adj r; window total / (sum median*wk) = conservation ratio)")
    for w in rules[k]:
        ii = [ix[d] for d in w]; cons = sum(tot[i] for i in ii) / sum(med[i] * wk[dow[i]] for i in ii)
        print(" ", w[0], w[0].strftime("%a"), w[-1], len(w), [round(r[i], 2) for i in ii], [round(sh[i], 2) for i in ii], "cons", round(cons, 2), "LOST?" if cons < 0.75 else ("surge" if cons > 1.3 else ""))
    sk = set(st.skip_days(rules[k]))
    print(f"  skip_days: {len(sk)}; added vs published {sorted(sk - skip_pub)}; in published but dropped {sorted(skip_pub - sk)}")
# Wednesday share
for k, ws in rules.items():
    lows = [w[0] for w in ws]; print(k, "windows starting on Wed:", sum(1 for d in lows if d.weekday() == 2), "of", len(lows))
print("Wednesdays in range:", sum(1 for d in days if d.weekday() == 2))
print("Wed with frozen>0.35:", sum(1 for d, s in zip(days, sh) if d.weekday() == 2 and s > .35), " non-Wed with frozen>0.35:", [str(d) for d, s in zip(days, sh) if d.weekday() != 2 and s > .35])
json.dump({k: [[str(d) for d in w] for w in ws] for k, ws in rules.items()}, open(f"{W}/rules6.json", "w"))
