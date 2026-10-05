"""D stage 5: are low_days false positives of a 15-day median rule given the weekly cycle? Weekday factors are the
median of tot/med15 per weekday over clean days (not in skip_days, not low_days, not within a snapshot gap)."""
import json, polars as pl, datetime as dt
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad/d"
t=pl.read_csv(f"{S}/hub_tot.csv",try_parse_dates=True); m=json.load(open(f"{S}/meta.json"))
low=set(m["low_days"]); days=sorted(dt.date.fromisoformat(d) for d in m["days"]); have=set(days)
names=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
# a day is "measured" if its own snapshot exists and the previous day's snapshot exists (gap 1)
t=t.with_columns(pl.col("day").map_elements(lambda d: d in have and (d-dt.timedelta(days=1)) in have,return_dtype=pl.Boolean).alias("meas"),
                 pl.col("day").cast(pl.Utf8).is_in(list(low)).alias("low"))
clean=t.filter(pl.col("meas")&~pl.col("in_skip")&~pl.col("low")&pl.col("r").is_not_null())
f=clean.group_by("dow").agg(pl.col("r").median().alias("f"),pl.len().alias("n")).sort("dow")
print("weekday factor (tot/med15), clean days:",[(names[a-1],round(b,3),n) for a,b,n in f.iter_rows()])
fm=dict(zip(f["dow"],f["f"]))
t=t.with_columns((pl.col("r")/pl.col("dow").replace_strict(fm)).alias("r_adj"))
print("\nlow days: raw r, weekday-adjusted r, still <0.7 after adjusting?")
n_keep=0
for r in t.filter(pl.col("low")).iter_rows(named=True):
    keep=r["r_adj"]<0.7; n_keep+=keep
    print(r["day"],names[r["dow"]-1],round(r["r"],3),round(r["r_adj"],3),"measured" if r["meas"] else "GAP-spread", "" if keep else "<- would not flag")
print("kept",n_keep,"of",len(low))
# conversely: days that adjusted rule would flag but raw does not
extra=t.filter((pl.col("r_adj")<0.7)&~pl.col("low")&pl.col("meas")&~pl.col("in_skip"))
print("\nadjusted<0.7 but not in low_days:",[(str(r["day"]),names[r["dow"]-1],round(r["r"],2),round(r["r_adj"],2)) for r in extra.iter_rows(named=True)])
# false-positive rate: how often does the raw rule fire on measured clean days by weekday
fire=t.filter(pl.col("meas")).group_by("dow").agg((pl.col("low")).sum().alias("low"),pl.len().alias("n")).sort("dow")
print("low days by weekday:",[(names[a-1],b,n) for a,b,n in fire.iter_rows()])
# gap-spread low days
print("low days in gaps:",[str(r["day"]) for r in t.filter(pl.col("low")&~pl.col("meas")).iter_rows(named=True)])
# 7-day sum comparisons: low windows
