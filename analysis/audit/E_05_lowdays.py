"""Classify the dataset low_days: weekday effect, gap blocks, position vs stall windows. usage: E_05_lowdays.py HFDIR"""
import polars as pl, json, sys, datetime as dt
H=sys.argv[1]
t=pl.read_csv("E_hub_daily_datasets.csv",try_parse_dates=True)
m=json.load(open(f"{H}/repos_meta.json"))
snap={dt.date.fromisoformat(x) for x in m["datasets_days"]}; skip={dt.date.fromisoformat(x) for x in m["skip_days"]}; low=[dt.date.fromisoformat(x) for x in m["low_days"]]
t=t.filter(pl.col("day")>=dt.date(2025,3,10)).with_columns(pl.col("day").dt.weekday().alias("wd"))
print("ratio (settled hub / 15d median) by weekday (1=Mon), since 2025-03-10")
print(t.group_by("wd").agg(pl.col("r").mean().alias("mean"),pl.col("r").median().alias("median"),(pl.col("r")<0.7).sum().alias("n_low"),pl.len().alias("n")).sort("wd"))
print("low days weekday:",{d.isoformat():d.isoweekday() for d in low})
# flatness: low day whose total equals the previous or next day total => spread/gap-average artifact
tot=dict(zip(t["day"].to_list(),t["tot"].to_list()))
allt=pl.read_csv("E_hub_daily_datasets.csv",try_parse_dates=True); tot=dict(zip(allt["day"],allt["tot"]))
for d in low:
    flat=(tot.get(d-dt.timedelta(1))==tot[d]) or (tot.get(d+dt.timedelta(1))==tot[d])
    print(d, "snapshot" if d in snap else "NO-SNAPSHOT(gap block)", "skip" if d in skip else "", "flat-with-neighbour" if flat else "", d.strftime("%a"))
