"""Rebuild the Hub-wide daily series and its skip days from the per-repo snapshots, with the rules in stalls.py.

    python rebuild_hub.py models   /path/to/data /path/to/out
    python rebuild_hub.py datasets /path/to/data /path/to/out

Reads <data>/series (or <data>/datasets/series) one snapshot at a time and writes hub_series.parquet plus the updated
meta (meta.json for models, repos_meta.json for datasets) to <out>, for review before uploading. Prints the windows,
the rollbacks and how the totals moved against the published series.
"""
import datetime as dt
import glob
import json
import os
import sys

import duckdb
import polars as pl

import stalls

kind, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
root = data if kind == "models" else os.path.join(data, "datasets")
meta_name = "meta.json" if kind == "models" else "repos_meta.json"
meta = json.load(open(os.path.join(data, meta_name)))
day_list = meta["days"] if kind == "models" else meta["datasets_days"]
repos = os.path.join(root, "models.parquet" if kind == "models" else "datasets.parquet")
tags = pl.read_parquet(repos, columns=["id", "pipeline_tag"]).with_columns(pl.col("pipeline_tag").fill_null("other"))

con = duckdb.connect()
con.execute("SET memory_limit='3GB'; SET threads=2")
if os.path.isdir("/work/duck_tmp"):
    con.execute("SET temp_directory='/work/duck_tmp'")


def read(day: dt.date) -> pl.DataFrame:
    f = os.path.join(root, "series", f"{day:%Y-%m}.parquet")
    return con.execute(f"SELECT id, dl_all::BIGINT AS dl_all, dl30::BIGINT AS dl30 FROM read_parquet('{f}') "
                       f"WHERE day = DATE '{day}' AND dl_all IS NOT NULL").pl()


days = sorted(dt.date.fromisoformat(d) for d in day_list)


def snapshots():
    for day in days:
        if day.day == 1:
            print(day, flush=True)
        yield day, read(day)


if "--from-raw" in sys.argv:  # windows only, from a previous run's measurements
    raw = pl.read_parquet(os.path.join(out, "hub_series_raw.parquet"))
    m = json.load(open(os.path.join(out, "measured.json")))
    frozen = {dt.date.fromisoformat(d): v for d, v in m["frozen"].items()}
    set_aside, state = [dt.date.fromisoformat(d) for d in m["aside"]], m["state"]
else:
    raw, frozen, set_aside, state = stalls.measure(snapshots(), tags)
    raw.write_parquet(os.path.join(out, "hub_series_raw.parquet"))
    json.dump({"frozen": {d.isoformat(): v for d, v in frozen.items()}, "aside": [d.isoformat() for d in set_aside], "state": state},
              open(os.path.join(out, "measured.json"), "w"))
for d in set_aside:
    print(f"{d} set aside: counters went down", flush=True)
min_frozen = stalls.FROZEN if kind == "models" else stalls.FROZEN_DATASETS
hub, wins = stalls.settle_history(raw, frozen | {d: 1.0 for d in set_aside}, min_frozen)  # a rollback's catch-up joins its window
skip = sorted(set(stalls.skip_days(wins)) | {d.isoformat() for d in set_aside})

# settled history must not reopen in the daily job
meta2 = dict(meta, skip_days=skip, frozen={d.isoformat(): v for d, v in frozen.items() if d >= days[-1] - dt.timedelta(days=30)})
if state:
    meta2["rollback"] = state
else:
    meta2.pop("rollback", None)
_, again = stalls.settle(hub, json.loads(json.dumps(meta2)), days[-1], min_frozen)
assert not again, f"settled history reopens: {again}"

hub.write_parquet(os.path.join(out, "hub_series.parquet"))
json.dump(meta2, open(os.path.join(out, meta_name), "w"))
json.dump({d.isoformat(): v for d, v in frozen.items()}, open(os.path.join(out, "frozen.json"), "w"))

old = pl.read_parquet(os.path.join(root, "hub_series.parquet"))
print(f"\n{len(wins)} windows:")
for w in wins:
    t = raw.filter(pl.col("day").is_in(w))["dl"].sum()
    print(f"  {w[0]}..{w[-1]} ({len(w)} days) {t / len(w) / 1e6:.1f}M/day; frozen {[round(frozen.get(d) or 0, 2) for d in w]}")
print("set aside (rollbacks):", [d.isoformat() for d in set_aside])
print(f"skip_days: {len(meta.get('skip_days', []))} -> {len(skip)}")
print("  added:", sorted(set(skip) - set(meta.get("skip_days", []))))
print("  dropped:", sorted(set(meta.get("skip_days", [])) - set(skip)))
print(f"total: published {old['dl'].sum() / 1e9:.3f}B over {old['day'].n_unique()} days -> {hub['dl'].sum() / 1e9:.3f}B over {hub['day'].n_unique()} days")
