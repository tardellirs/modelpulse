"""D stage 2: hub_series analysis (published, smoothed). Seasonality, spikes, low days, rule false positives."""
import json, polars as pl, datetime as dt
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad/d"
h=pl.read_parquet(f"{S}/hub_series.parquet"); m=json.load(open(f"{S}/meta.json"))
t=h.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
t=t.with_columns(pl.col("tot").rolling_median(15,center=True,min_samples=5).alias("med"))
t=t.with_columns((pl.col("tot")/pl.col("med")).alias("r"),pl.col("day").dt.weekday().alias("dow"))
print("days",t.height,"sum",t["tot"].sum())
# weekday profile: ratio to centered 7-day mean
t=t.with_columns(pl.col("tot").rolling_mean(7,center=True).alias("m7")).with_columns((pl.col("tot")/pl.col("m7")).alias("r7"))
names=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
low=set(m["low_days"]); skip=set(m["skip_days"])
t=t.with_columns(pl.col("day").cast(pl.Utf8).is_in(list(skip)).alias("in_skip"))
clean=t.filter(~pl.col("in_skip"))
for lab,sub in [("all",t),("2025-03..2025-12",t.filter((pl.col("day")>=dt.date(2025,3,1))&(pl.col("day")<dt.date(2026,1,1)))),("2026",t.filter(pl.col("day")>=dt.date(2026,1,1)))]:
    g=sub.group_by("dow").agg(pl.col("r7").median().alias("med"),pl.col("r7").mean().alias("mean"),pl.len().alias("n")).sort("dow")
    print(lab,[(names[d-1],round(a,3)) for d,a in zip(g["dow"],g["med"])])
# per-month weekday/weekend ratio
t=t.with_columns(pl.col("day").dt.strftime("%Y-%m").alias("ym"),(pl.col("dow")>=6).alias("we"))
mm=t.group_by("ym","we").agg(pl.col("tot").mean().alias("a")).pivot(on="we",index="ym",values="a").sort("ym")
mm=mm.with_columns((pl.col("true")/pl.col("false")).alias("we_ratio"))
print(mm)
# low days listing
print("LOW DAYS")
for d in m["low_days"]:
    r=t.filter(pl.col("day")==dt.date.fromisoformat(d)).row(0,named=True)
    print(d,names[r["dow"]-1],round(r["r"],3),f'{r["tot"]/1e6:.0f}M',f'med {r["med"]/1e6:.0f}M', "r7",round(r["r7"] or 0,3))
# spikes
print("SPIKES r>1.3")
win=set()
for d in sorted(skip): win.add(d)
for r in t.filter(pl.col("r")>1.3).iter_rows(named=True):
    print(r["day"],names[r["dow"]-1],round(r["r"],2),f'{r["tot"]/1e6:.0f}M',"in_skip" if r["in_skip"] else "")
t.write_csv(f"{S}/hub_tot.csv")
