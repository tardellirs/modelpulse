"""D stage 11: 'this week' number (leaderboards dl_7d = counter difference last-vs-(last-7), skip days excluded except the last
day) vs the smoothed hub 7-day sum. For every possible 'last' day: raw 7-day sum from per-snapshot positive deltas
(snapshot D vs latest usable snapshot <= D-7, no more than 10 back) vs published hub_series 7-day sum ending D."""
import json, polars as pl, datetime as dt
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
st=pl.read_parquet(S+"/out/stats.parquet").sort("day").filter(pl.col("pos").is_not_null())
t=pl.read_csv(S+"/d/hub_tot.csv",try_parse_dates=True); m=json.load(open(S+"/d/meta.json")); skip=set(m["skip_days"])
tot=dict(zip(t["day"],t["tot"]))
raw={r["day"]:(r["pos"],r["gap"]) for r in st.iter_rows(named=True)}
days=sorted(raw)
# cumulative raw pos per calendar day (gap-spread) - equivalent to counter differences for positive part
cum={}; c=0; 
d=days[0]
daily={}
for day in days:
    p,g=raw[day]
    for k in range(g): daily[day-dt.timedelta(days=k)]=p/g
rows=[]
for D in days:
    if D<dt.date(2025,4,10): continue
    # published 7 day sum
    pub=sum(tot.get(D-dt.timedelta(days=k),0) for k in range(7))
    # leaderboard window: from usable snapshot <= D-7 (>= D-17, not skip) to D
    cand=[x for x in days if x<=D-dt.timedelta(days=7) and x>=D-dt.timedelta(days=17) and str(x) not in skip]
    if not cand: continue
    A=cand[-1]; span=(D-A).days
    lb=sum(daily.get(A+dt.timedelta(days=k),0) for k in range(1,span+1))
    rows.append((D,span,lb,pub))
df=pl.DataFrame(rows,schema=["day","span","lb","pub"],orient="row").with_columns((pl.col("lb")/pl.col("pub")-1).alias("dev"))
print("days",df.height,"span!=7:",df.filter(pl.col("span")!=7).height)
print("dev quantiles (leaderboard-style 7-day vs published 7-day):",[round(df["dev"].quantile(q),3) for q in (0.01,0.05,0.5,0.95,0.99)])
print("|dev|>5%:",df.filter(pl.col("dev").abs()>0.05).height,"of",df.height," <-5%:",df.filter(pl.col("dev")<-0.05).height)
print(df.filter(pl.col("dev")<-0.05).select("day","span","dev").with_columns(pl.col("day").dt.weekday().alias("dow")))
print("share of days where last-7 snapshot is replaced because skip:",df.filter(pl.col("span")>7).height/df.height)
# raw last-day stall effect: dev conditional on D being a stall day (D in skip or in windows)
