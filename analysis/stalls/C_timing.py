"""Map Model Pulse snapshot days to hub-stats commit times (same rule as the pipeline: latest commit of each UTC day).
Writes C_snapshots.csv: day, models_ts, datasets_ts, spaces_ts, prev-intervals in hours."""
import polars as pl
c = pl.read_csv("C_commits.csv").with_columns(pl.col("created_at").str.to_datetime(time_zone="UTC"))
out = None
for k in ["models", "datasets", "spaces"]:
    x = (c.filter(pl.col("title").str.contains(f"Upload {k}.parquet")).with_columns(pl.col("created_at").dt.date().alias("day"))
         .group_by("day").agg(pl.col("created_at").max().alias(f"{k}_ts"), pl.col("created_at").min().alias(f"{k}_first"), pl.len().alias(f"{k}_ncommits")).sort("day"))
    x = x.with_columns(((pl.col(f"{k}_ts") - pl.col(f"{k}_ts").shift(1)).dt.total_seconds() / 3600).alias(f"{k}_int_h"))
    out = x if out is None else out.join(x, on="day", how="full", coalesce=True)
out = out.sort("day").with_columns(((pl.col("datasets_ts") - pl.col("models_ts")).dt.total_seconds() / 60).alias("ds_minus_models_min"))
out.write_csv("C_snapshots.csv")
r = out.filter(pl.col("day") >= pl.date(2025, 2, 27))
print(r.select("models_int_h", "datasets_int_h", "ds_minus_models_min").describe())
print("multi-commit days since 2025-02-27:", r.filter(pl.col("models_ncommits") > 1).height)
print(r.select(pl.col("models_ts").dt.hour().alias("h")).group_by("h").len().sort("h"))
print(r.filter(pl.col("models_int_h") < 20).select("day", "models_int_h", "models_ncommits"))
print(r.filter(pl.col("models_int_h") > 30).select("day", "models_int_h"))
