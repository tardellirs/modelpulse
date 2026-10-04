"""Backfill daily snapshots of datasets and Spaces from cfahlgren1/hub-stats history.

    python backfill_repos.py datasets raw_datasets
    python backfill_repos.py spaces raw_spaces

Keeps the latest upload of each UTC day (as for models), downloads the whole file with hf_xet, keeps the few columns
that change day to day, writes one small parquet per day and deletes the download. Reruns skip finished days.
"""
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download

SRC = "cfahlgren1/hub-stats"
COLUMNS = {
    "datasets": [("id", pa.string()), ("downloads", pa.int64()), ("downloadsAllTime", pa.int64()), ("likes", pa.int64())],
    "spaces": [("id", pa.string()), ("likes", pa.int64()), ("trendingScore", pa.float64())],
}
KIND, OUT = sys.argv[1], sys.argv[2]
CACHE = os.environ.get("XET_CACHE", f"/root/hfc_{KIND}")
SCHEMA = pa.schema(COLUMNS[KIND])


def list_days():
    by_day = {}
    for c in HfApi().list_repo_commits(SRC, repo_type="dataset"):
        if f"{KIND}.parquet" not in (c.title or ""):
            continue
        d = c.created_at.date().isoformat()
        if d not in by_day or c.created_at > by_day[d][1]:
            by_day[d] = (c.commit_id, c.created_at)
    return sorted((d, sha) for d, (sha, _) in by_day.items())


def one(day, sha):
    cache = os.path.join(CACHE, day)
    path = hf_hub_download(SRC, f"{KIND}.parquet", repo_type="dataset", revision=sha, cache_dir=cache)
    pf = pq.ParquetFile(path)
    names = [n for n, _ in COLUMNS[KIND]]
    t = pf.read(columns=[c for c in names if c in pf.schema_arrow.names])
    for c, typ in COLUMNS[KIND]:
        if c not in t.column_names:
            t = t.append_column(c, pa.nulls(t.num_rows, typ))
    t = t.select(names).cast(SCHEMA)
    dst = os.path.join(OUT, f"{day}.parquet")
    pq.write_table(t, dst + ".tmp", compression="zstd")
    os.replace(dst + ".tmp", dst)
    shutil.rmtree(cache, ignore_errors=True)
    return day, t.num_rows


def main():
    os.makedirs(OUT, exist_ok=True)
    days_path = os.path.join(OUT, "_days.json")
    if not os.path.exists(days_path):
        json.dump(list_days(), open(days_path, "w"))
    days = json.load(open(days_path))
    todo = [(d, s) for d, s in days if not os.path.exists(os.path.join(OUT, f"{d}.parquet"))]
    print(KIND, len(days), "days,", len(todo), "to fetch", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(int(os.environ.get("WORKERS", "6"))) as ex:
        futs = {ex.submit(one, d, s): d for d, s in todo}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                d, n = f.result()
                print(f"[{i}/{len(todo)} {time.time() - t0:.0f}s] {d} {n}", flush=True)
            except Exception as e:
                print("FAILED", futs[f], repr(e), flush=True)


if __name__ == "__main__":
    main()
