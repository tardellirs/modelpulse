"""One-off repair: give hub_series.parquet one row per calendar day (gap averages spread over the gap)."""
import datetime as dt
import os
import sys

import polars as pl
from huggingface_hub import HfApi

path = sys.argv[1]
h = pl.read_parquet(path)
days = sorted(h["day"].unique().to_list())
prev = {b: a for a, b in zip(days, days[1:])}
parts = []
for (d,), g in h.group_by("day"):
    gap = (d - prev[d]).days if d in prev else 1
    for k in range(gap):
        parts.append(g.with_columns(pl.lit(d - dt.timedelta(days=k)).alias("day")))
fixed = pl.concat(parts).sort("day", "pipeline_tag")
before, after = h["dl"].sum(), fixed["dl"].sum()
n_days = fixed["day"].n_unique()
span = (fixed["day"].max() - fixed["day"].min()).days + 1
print(f"rows {h.height} -> {fixed.height}; days {len(days)} -> {n_days} (calendar span {span}); sum {before/1e9:.2f}B -> {after/1e9:.2f}B")
assert n_days == span, "still missing days"
fixed.write_parquet(path)
if "--upload" in sys.argv:
    print(HfApi().upload_file(path_or_fileobj=path, path_in_repo="hub_series.parquet", repo_id=os.environ.get("DATA_REPO", "modelpulse/model-pulse-data"),
                              repo_type="dataset", commit_message="hub_series: one row per calendar day so sums stay exact across snapshot gaps"))
