"""D stage 7: for each low-day run, is the deficit made up by surplus within +-6 days (counting spread gap days as is)?
Baseline = median of the published daily totals in days -21..-8 and +8..+21 around the run (weekday not adjusted)."""
import json, polars as pl, datetime as dt
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad/d"
t=pl.read_csv(f"{S}/hub_tot.csv",try_parse_dates=True); m=json.load(open(f"{S}/meta.json"))
tot=dict(zip(t["day"],t["tot"])); low=sorted(dt.date.fromisoformat(d) for d in m["low_days"])
runs=[]
for d in low:
    if runs and (d-runs[-1][-1]).days<=1: runs[-1].append(d)
    else: runs.append([d])
import statistics
print("run | deficit vs baseline (M) | surplus before (-6..-1) | surplus after (+1..+6) | net over run+-6 | baseline M")
for r in runs:
    a,b=r[0],r[-1]
    base_days=[a+dt.timedelta(days=k) for k in range(-21,-7)]+[b+dt.timedelta(days=k) for k in range(8,22)]
    vals=[tot[x] for x in base_days if x in tot]
    base=statistics.median(vals)
    deficit=sum(base-tot[x] for x in r)
    pre=sum(tot.get(a-dt.timedelta(days=k),base)-base for k in range(1,7))
    post=sum(tot.get(b+dt.timedelta(days=k),base)-base for k in range(1,7))
    net=pre+post-deficit
    print(f"{a}..{b} ({len(r)}d) | -{deficit/1e6:.0f} | {pre/1e6:+.0f} | {post/1e6:+.0f} | {net/1e6:+.0f} | {base/1e6:.0f}  made-up {100*(pre+post)/deficit:.0f}%")

print()
print("run | net balance over run+-3 days and +-5 days, in 'normal days' (sum(tot-base)/base); ~0 means made up locally")
for r in runs:
    a,b=r[0],r[-1]
    base_days=[a+dt.timedelta(days=k) for k in range(-21,-7)]+[b+dt.timedelta(days=k) for k in range(8,22)]
    base=statistics.median([tot[x] for x in base_days if x in tot])
    out=[]
    for w in (3,5):
        days=[a+dt.timedelta(days=k) for k in range(-w,(b-a).days+w+1)]
        out.append(sum(tot.get(x,base)-base for x in days)/base)
    print(f"{a}..{b}: net(+-3)={out[0]:+.2f}  net(+-5)={out[1]:+.2f} days; run length {len(r)}")
