"""Backfill daily model stats from cfahlgren1/hub-stats revision history.

For every UTC day that has a models.parquet upload, reads only the columns we
need (via HTTP range requests against the resolved CDN URL) and writes
raw/<YYYY-MM-DD>.parquet. Resumable: days already on disk are skipped.
"""
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pyarrow as pa
import pyarrow.parquet as pq

REPO = "cfahlgren1/hub-stats"
API = f"https://huggingface.co/api/datasets/{REPO}/commits/main"
WANT = ["id", "downloads", "downloadsAllTime", "likes"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "raw"
WORKERS = int(os.environ.get("WORKERS", "6"))
HEADERS = {"User-Agent": "modelpulse-backfill/0.1"}
if os.environ.get("HF_TOKEN"):
    HEADERS["Authorization"] = f"Bearer {os.environ['HF_TOKEN']}"


def get(url, headers=None, method="GET", tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method=method, headers={**HEADERS, **(headers or {})})
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(300, 15 * 2**i))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i < tries - 1:
                time.sleep(10 * 2**i)
                continue
            raise


class RangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests."""

    def __init__(self, url):
        r = get(url, method="HEAD")
        self.url = r.geturl()  # signed CDN URL after redirects
        self.size = int(r.headers["Content-Length"])
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        if n <= 0:
            return b""
        rng = {"Range": f"bytes={self.pos}-{self.pos + n - 1}"}
        b = urllib.request.urlopen(urllib.request.Request(self.url, headers=rng), timeout=300).read()
        self.pos += len(b)
        return b

    def readinto(self, buf):
        d = self.read(len(buf))
        buf[: len(d)] = d
        return len(d)


def list_days():
    commits, p = [], 0
    while True:
        page = json.load(get(f"{API}?limit=1000&p={p}"))
        if not page:
            break
        commits += [c for c in page if "models.parquet" in c["title"]]
        p += 1
    by_day = {}
    for c in commits:  # keep the latest upload of each UTC day
        d = c["date"][:10]
        if d not in by_day or c["date"] > by_day[d]["date"]:
            by_day[d] = c
    return sorted((d, c["id"]) for d, c in by_day.items())


def fetch_day(day, sha):
    dst = os.path.join(OUT, f"{day}.parquet")
    if os.path.exists(dst):
        return day, "skip"
    f = RangeFile(f"https://huggingface.co/datasets/{REPO}/resolve/{sha}/models.parquet")
    pf = pq.ParquetFile(f, pre_buffer=True)
    cols = [c for c in WANT if c in pf.schema_arrow.names]
    t = pf.read(columns=cols)
    for c in WANT:
        if c not in t.column_names:
            t = t.append_column(c, pa.nulls(t.num_rows, pa.int64()))
    t = t.select(WANT).cast(pa.schema([("id", pa.string()), ("downloads", pa.int64()),
                                        ("downloadsAllTime", pa.int64()), ("likes", pa.int64())]))
    tmp = dst + ".tmp"
    pq.write_table(t, tmp, compression="zstd")
    os.replace(tmp, dst)
    return day, f"{t.num_rows} rows, {f.size / 1e6:.0f}MB src"


def main():
    os.makedirs(OUT, exist_ok=True)
    days = list_days()
    json.dump(days, open(os.path.join(OUT, "_days.json"), "w"))
    print(f"{len(days)} days {days[0][0]} -> {days[-1][0]}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fetch_day, d, s): d for d, s in days}
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                day, msg = fu.result()
                print(f"[{i}/{len(days)} {time.time() - t0:.0f}s] {day} {msg}", flush=True)
            except Exception as e:
                print(f"[{i}/{len(days)}] {futs[fu]} FAILED {e!r}", flush=True)


if __name__ == "__main__":
    main()
