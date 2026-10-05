import polars as pl, json, datetime as dt, sys
H=sys.argv[1]
hub=pl.read_parquet(f"{H}/datasets/hub_series.parquet")
print(hub.schema, hub.height)
t=hub.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
t=t.with_columns(pl.col("tot").rolling_median(15,center=True,min_samples=5).alias("med")).with_columns((pl.col("tot")/pl.col("med")).alias("r"))
m=json.load(open(f"{H}/repos_meta.json"))
low=set(m["low_days"]); skip=set(m["skip_days"])
pl.Config.set_tbl_rows(100)
print(t.head(3), t.tail(3))
x=t.filter(pl.col("day").cast(pl.String).is_in(list(low)))
print(x)
# around runs
for a,b in [("2025-06-10","2025-07-20"),("2026-07-01","2026-07-25")]:
    print(t.filter((pl.col("day")>=dt.date.fromisoformat(a))&(pl.col("day")<=dt.date.fromisoformat(b))).with_columns(pl.col("day").cast(pl.String).is_in(list(skip)).alias("skip")))
t.write_csv("E_hub_daily_datasets.csv")
