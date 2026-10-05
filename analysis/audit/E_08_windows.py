"""Replay, from the day lists only, which window the 7-day numbers really span on each build day (build.derived / space_metrics logic).
Datasets: snapshots in skip_days are ignored (except the last day); at_or_before looks back up to 10 days.
Spaces: no skip handling. If nothing in [ref-10, ref] -> NULL: datasets dl_7d falls to dl30 (min_horizontal ignores nulls), Spaces likes_7d = all likes (fill_null(0)).
usage: E_08_windows.py HFDIR"""
import json, sys, datetime as dt, glob, polars as pl
H=sys.argv[1]
m=json.load(open(f"{H}/repos_meta.json"))
ds=sorted(dt.date.fromisoformat(x) for x in m["datasets_days"]); skip={dt.date.fromisoformat(x) for x in m["skip_days"]}
sp=sorted(pl.concat([pl.read_parquet(f,columns=["day"]).unique() for f in sorted(glob.glob(f"{H}/spaces/series/*.parquet"))])["day"].unique().to_list())
def eff(days,D,back,use_skip):
    ref=D-dt.timedelta(days=back); lo=ref-dt.timedelta(days=10)
    c=[d for d in days if lo<=d<=ref and not (use_skip and d in skip and d!=D)]
    return (D-max(c)).days if c else None
def report(name,days,use_skip,start):
    rows=[]
    for D in days:
        if D<start: continue
        rows.append((D,eff(days,D,7,use_skip),eff(days,D,28,use_skip)))
    bad=[(D,w) for D,w,_ in rows if w!=7]
    nul=[D for D,w,_ in rows if w is None]
    print(f"{name}: build days {len(rows)}; 7d window not 7 days on {len(bad)} days ({len(bad)/len(rows):.1%}); NULL on {len(nul)}")
    from collections import Counter
    print("  window length counts:",sorted(Counter(w for _,w in bad).items(),key=lambda x:(x[0] is None,x[0])))
    print("  NULL days:",[str(d) for d in nul])
    big=[(str(D),w) for D,w in bad if w and w>=9]; print("  >=9-day windows:",big)
    return rows
report("datasets (with skip days)",ds,True,dt.date(2025,3,10))
report("datasets (if skip days were NOT excluded)",ds,False,dt.date(2025,3,10))
report("spaces",sp,False,dt.date(2024,8,10))
# last day itself a stall day (it is always kept): then every dataset's 7d number is 6/7 of a week
last_stall=[str(d) for d in ds if d in skip and d>=dt.date(2025,3,10)]
print("build days that are themselves skip days (7d numbers deflated): ",len(last_stall))
