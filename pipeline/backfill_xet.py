"""Faster backfill for Xet-backed snapshots: download whole files with hf_xet, keep 4 columns, delete."""
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

OUT = sys.argv[1] if len(sys.argv) > 1 else "raw"
CACHE = os.environ.get("XET_CACHE", "/root/hfc")
WANT = ["id", "downloads", "downloadsAllTime", "likes"]
SCHEMA = pa.schema([("id", pa.string()), ("downloads", pa.int64()), ("downloadsAllTime", pa.int64()), ("likes", pa.int64())])


def one(day, sha):
    cache = os.path.join(CACHE, day)
    path = hf_hub_download("cfahlgren1/hub-stats", "models.parquet", repo_type="dataset", revision=sha, cache_dir=cache)
    pf = pq.ParquetFile(path)
    t = pf.read(columns=[c for c in WANT if c in pf.schema_arrow.names])
    for c in WANT:
        if c not in t.column_names:
            t = t.append_column(c, pa.nulls(t.num_rows, pa.int64()))
    t = t.select(WANT).cast(SCHEMA)
    dst = os.path.join(OUT, f"{day}.parquet")
    pq.write_table(t, dst + ".tmp", compression="zstd")
    os.replace(dst + ".tmp", dst)
    shutil.rmtree(cache, ignore_errors=True)
    return day, t.num_rows


def main():
    days = json.load(open(os.path.join(OUT, "_days.json")))
    todo = [(d, s) for d, s in days if not os.path.exists(os.path.join(OUT, f"{d}.parquet"))]
    print(len(todo), "days to fetch", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(int(os.environ.get("WORKERS", "4"))) as ex:
        futs = {ex.submit(one, d, s): d for d, s in todo}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                d, n = f.result()
                print(f"[{i}/{len(todo)} {time.time() - t0:.0f}s] {d} {n}", flush=True)
            except Exception as e:
                print("FAILED", futs[f], repr(e), flush=True)


if __name__ == "__main__":
    main()
