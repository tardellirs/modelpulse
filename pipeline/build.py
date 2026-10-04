"""Build the Model Pulse dataset from raw daily snapshots.

Inputs:  raw/<day>.parquet (id, downloads, downloadsAllTime, likes) + latest hub-stats meta
Outputs (OUT dir):
  series/<YYYY-MM>.parquet   long table (id, day, dl30, dl_all, likes), sorted by id
  models.parquet             one row per tracked model: metadata + derived metrics
  family_series.parquet      (id, day, dl30, dl_all) summed over a base model's whole family
  author_series.parquet      (author, day, dl30, dl_all, likes) for active authors
  leaderboards.json          precomputed rankings
  meta.json                  days list + build info
"""
import datetime as dt
import glob
import json
import os
import sys
import time

import polars as pl

import stalls
import pyarrow.parquet as pq


RAW = OUT = None  # set by main() or by daily.py
SRC = "https://huggingface.co/datasets/cfahlgren1/hub-stats/resolve/main/models.parquet"
FAMILY_MIN_MEMBERS = 3
AUTHOR_MIN_ALL = 1_000
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def day_files():
    files = sorted(glob.glob(os.path.join(RAW, "2*.parquet")))
    return [(dt.date.fromisoformat(os.path.basename(f)[:10]), f) for f in files]


def read_day(day, path):
    return (pl.read_parquet(path)
            .rename({"downloads": "dl30", "downloadsAllTime": "dl_all"})
            .with_columns(pl.lit(day).alias("day"),
                          pl.col("dl30").cast(pl.Int64), pl.col("likes").cast(pl.Int32)))


def universe(days):
    """Models that were ever active, sampled weekly (dl30 is a 30-day window, so weekly sampling misses nothing)."""
    picks = days[::7] + [days[-1]]
    ids = set()
    for day, path in picks:
        d = read_day(day, path).filter((pl.col("dl30") >= 10) | (pl.col("likes") >= 1) | (pl.col("dl_all") >= 50))
        ids.update(d["id"].to_list())
    return pl.DataFrame({"id": sorted(ids)})


def write_series(days, uni):
    os.makedirs(os.path.join(OUT, "series"), exist_ok=True)
    months = sorted({d.strftime("%Y-%m") for d, _ in days})
    for m in months:
        frames = [read_day(d, p).join(uni, on="id", how="semi") for d, p in days if d.strftime("%Y-%m") == m]
        df = (pl.concat(frames).select("id", "day", "dl30", "dl_all", "likes")
              .with_columns(pl.col("dl30").cast(pl.Int32)).sort("id", "day"))
        df.write_parquet(os.path.join(OUT, "series", f"{m}.parquet"), compression="zstd",
                         compression_level=9, row_group_size=200_000, statistics=True)
        log("series", m, df.height)


def write_months(df, name, key):
    """Write a (key, day, ...) table as one parquet file per month, sorted by key for row-group pruning."""
    os.makedirs(os.path.join(OUT, name), exist_ok=True)
    df = df.with_columns(pl.col("day").dt.strftime("%Y-%m").alias("_m"))
    for (m,), part in df.group_by("_m"):
        part.drop("_m").sort(key, "day").write_parquet(os.path.join(OUT, name, f"{m}.parquet"), compression="zstd",
                                                       compression_level=9, row_group_size=200_000, statistics=True)


def month_sources(source=None):
    """One lazy frame per series month (or just the given source), to keep joins small."""
    if source is not None:
        return [source]
    return [pl.scan_parquet(f) for f in sorted(glob.glob(os.path.join(OUT, "series", "*.parquet")))]


def scan_series():
    return pl.scan_parquet(os.path.join(OUT, "series", "*.parquet"))


def latest_meta(path=None):
    if path is None:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download("cfahlgren1/hub-stats", "models.parquet", repo_type="dataset")
    pf = pq.ParquetFile(path)
    t = pf.read(columns=["id", "author", "pipeline_tag", "library_name", "createdAt", "lastModified",
                         "trendingScore", "baseModels", "safetensors", "tags", "gated"]
                if "gated" in pf.schema_arrow.names else
                ["id", "author", "pipeline_tag", "library_name", "createdAt", "lastModified",
                 "trendingScore", "baseModels", "safetensors", "tags"])
    df = pl.from_arrow(t)
    return df.with_columns(
        pl.col("safetensors").struct.field("total").alias("params"),
        pl.col("baseModels").struct.field("relation").alias("base_relation"),
        pl.col("baseModels").struct.field("models").list.eval(pl.element().struct.field("id")).alias("base_ids"),
        pl.col("tags").list.eval(pl.element().filter(pl.element().str.starts_with("license:")))
          .list.first().str.replace("license:", "").alias("license"),
        pl.col("tags").list.contains("gguf").alias("is_gguf"),
    ).drop("safetensors", "baseModels", "tags")


def at_or_before(series_last, ref_day, max_back=10):
    """Value of each model on the latest snapshot day <= ref_day."""
    lo = ref_day - dt.timedelta(days=max_back)
    return (series_last.filter((pl.col("day") <= ref_day) & (pl.col("day") >= lo))
            .sort("day").group_by("id").last())


def derived(days, meta, first=None):
    last = days[-1][0]
    recent = scan_series().filter(pl.col("day") >= last - dt.timedelta(days=40)).collect()
    now = recent.filter(pl.col("day") == last).select("id", "dl30", "dl_all", "likes")
    w1 = at_or_before(recent, last - dt.timedelta(days=7)).select("id", pl.col("dl_all").alias("all_7"), pl.col("likes").alias("likes_7"))
    w2 = at_or_before(recent, last - dt.timedelta(days=14)).select("id", pl.col("dl_all").alias("all_14"))
    w4 = at_or_before(recent, last - dt.timedelta(days=28)).select("id", pl.col("dl_all").alias("all_28"))
    if first is None:
        first = scan_series().group_by("id").agg(pl.col("day").min().alias("first_seen")).collect(engine="streaming")
    m = (now.join(w1, on="id", how="left").join(w2, on="id", how="left").join(w4, on="id", how="left")
         .join(first, on="id", how="left")
         .with_columns(
             # a week can't hold more downloads than the 30-day window that contains it; guards against recounts
             pl.min_horizontal((pl.col("dl_all") - pl.col("all_7")).clip(0), pl.col("dl30")).alias("dl_7d"),
             (pl.col("all_7") - pl.col("all_14")).clip(0).alias("dl_prev7d"),
             ((pl.col("all_7") - pl.col("all_28")).clip(0) / 3).alias("dl_base7d"),
             (pl.col("likes") - pl.col("likes_7")).alias("likes_7d"))
         .with_columns(
             # growth vs the average of the three weeks before, robust to one stalled or backlogged week
             pl.when(pl.col("dl_base7d") >= 100).then(pl.col("dl_7d") / pl.col("dl_base7d") - 1).alias("growth_7d"))
         .drop("all_7", "all_14", "all_28", "likes_7"))
    m = m.join(meta, on="id", how="left")
    m = m.with_columns(
        pl.col("dl30").rank("min", descending=True).cast(pl.Int32).alias("rank_dl30"),
        pl.col("dl30").rank("min", descending=True).over("pipeline_tag").cast(pl.Int32).alias("rank_task"),
        pl.col("dl_7d").rank("min", descending=True).cast(pl.Int32).alias("rank_7d"),
    )
    return m


def families(models):
    """Transitive descendants of every model via base_model edges."""
    edges = (models.select("id", "base_relation", pl.col("base_ids").alias("parent"))
             .explode("parent").drop_nulls("parent").filter(pl.col("parent") != pl.col("id")))
    # ancestor pairs (member, ancestor), iterated to a fixed depth
    pairs = edges.select(pl.col("id").alias("member"), pl.col("parent").alias("anc"))
    frontier = pairs
    for _ in range(6):
        nxt = (frontier.join(edges.select(pl.col("id").alias("anc"), pl.col("parent").alias("anc2")), on="anc")
               .select("member", pl.col("anc2").alias("anc")))
        nxt = nxt.join(pairs, on=["member", "anc"], how="anti").unique()
        if nxt.height == 0:
            break
        pairs = pl.concat([pairs, nxt])
        frontier = nxt
    pairs = pairs.unique()
    rel = edges.select(pl.col("id").alias("member"), "base_relation").unique("member")
    stats = (pairs.join(models.select(pl.col("id").alias("member"), "dl30", "dl_all", "dl_7d"), on="member", how="left")
             .join(rel, on="member", how="left")
             .group_by("anc").agg(
                 pl.len().alias("fam_members"),
                 pl.col("dl30").sum().alias("fam_dl30_desc"),
                 pl.col("dl_all").sum().alias("fam_all_desc"),
                 pl.col("dl_7d").sum().alias("fam_7d_desc"),
                 *[(pl.col("base_relation") == r).sum().alias(f"n_{r}") for r in ("quantized", "finetune", "adapter", "merge")])
             .rename({"anc": "id"}))
    return pairs, stats


def family_series(pairs, fam_ids, source=None):
    p = pairs.filter(pl.col("anc").is_in(fam_ids))
    p = pl.concat([p, pl.DataFrame({"member": fam_ids, "anc": fam_ids})])  # include the base itself
    n = 0
    for src in month_sources(source):
        out = (src.join(p.lazy(), left_on="id", right_on="member")
               .group_by("anc", "day").agg(pl.col("dl30").cast(pl.Int64).sum(), pl.col("dl_all").sum(), pl.len().alias("members"))
               .rename({"anc": "id"}).collect(engine="streaming"))
        write_months(out, "family_series", "id")
        n += out.height
    log("family_series", n)


def author_series(models, source=None):
    authors = (models.group_by("author").agg(pl.col("dl_all").sum()).filter(pl.col("dl_all") >= AUTHOR_MIN_ALL)
               .select("author"))
    idauth = models.select("id", "author").join(authors, on="author", how="semi")
    n = 0
    for src in month_sources(source):
        out = (src.join(idauth.lazy(), on="id")
               .group_by("author", "day").agg(pl.col("dl30").cast(pl.Int64).sum(), pl.col("dl_all").sum(),
                                              pl.col("likes").cast(pl.Int64).sum(), pl.len().alias("models"))
               .collect(engine="streaming"))
        write_months(out, "author_series", "author")
        n += out.height
    log("author_series", n)


def hub_series(models, days):
    """Hub-wide daily downloads per pipeline_tag: sum of positive dl_all deltas between consecutive snapshots."""
    tags = models.select("id", pl.col("pipeline_tag").fill_null("other"))
    out = []
    prev = None
    for day, path in days:
        cur = read_day(day, path).select("id", "dl_all", "dl30").drop_nulls("dl_all")
        if prev is not None and cur.height:
            gap = (day - prev[0]).days
            d = (cur.join(prev[1], on="id", suffix="_p")
                 .with_columns(((pl.col("dl_all") - pl.col("dl_all_p")).clip(0) / gap).alias("dl"))
                 .join(tags, on="id", how="left").with_columns(pl.col("pipeline_tag").fill_null("other"))
                 .group_by("pipeline_tag").agg(pl.col("dl").sum()))
            # one row per calendar day: a gap's per-day average is written to every day it covers, so sums stay exact
            for k in range(gap - 1, -1, -1):
                out.append(d.with_columns(pl.lit(day - dt.timedelta(days=k)).alias("day")))
        if cur.height:
            prev = (day, cur.select("id", "dl_all"))
    hub = pl.concat(out).select("day", "pipeline_tag", pl.col("dl").round(0).cast(pl.Int64)).sort("day", "pipeline_tag")
    wins = stalls.windows(hub)
    hub = stalls.smooth(hub, wins)
    hub.write_parquet(os.path.join(OUT, "hub_series.parquet"))
    log("stalls", len(wins))
    return stalls.skip_days(wins)
    log("hub_series", hub.height)


SKIP: set[str] = set()  # days whose snapshot is ignored (see stalls.py); set by the caller from meta.json


def sparks(ids, last):
    """Daily downloads over the last ~28 days for a set of models."""
    skip = [dt.date.fromisoformat(d) for d in SKIP]
    s = (scan_series().filter(pl.col("id").is_in(ids) & (pl.col("day") >= last - dt.timedelta(days=29)) & ~pl.col("day").is_in(skip))
         .select("id", "day", "dl_all").collect().sort("id", "day")
         .with_columns((pl.col("dl_all").diff().over("id").clip(0)
                        / pl.col("day").diff().over("id").dt.total_days().clip(1)).alias("d"))
         .drop_nulls("d").group_by("id", maintain_order=True).agg(pl.col("d")))
    return dict(zip(s["id"].to_list(), s["d"].to_list()))


def leaderboards(models, last):
    cols = ["id", "author", "pipeline_tag", "params", "dl30", "dl_all", "dl_7d", "dl_prev7d", "dl_base7d", "growth_7d",
            "likes", "likes_7d", "created_at", "fam_members", "fam_dl30"]
    m = models.select([c for c in cols if c in models.columns])

    def top(df, by, n=100):
        rows = df.sort(by, descending=True, nulls_last=True).head(n).to_dicts()
        sp = sparks([r["id"] for r in rows if "id" in r], last) if rows and "id" in rows[0] else {}
        for r in rows:
            if "id" in r:
                r["spark"] = sp.get(r["id"], [])
        return rows

    authors = (models.group_by("author").agg(
        pl.col("dl30").sum(), pl.col("dl_7d").sum(), pl.col("dl_base7d").sum(), pl.col("dl_all").sum(),
        pl.col("likes").sum(), pl.len().alias("models"))
        .drop_nulls("author")
        .with_columns(pl.when(pl.col("dl_base7d") >= 1_000).then(pl.col("dl_7d") / pl.col("dl_base7d") - 1).alias("growth_7d")))
    lb = {
        "updated": str(last),
        "gainers_7d": top(m, "dl_7d"),
        "growth_7d": top(m.filter((pl.col("dl_base7d") >= 1_000) & (pl.col("dl30") >= 10_000)), "growth_7d"),
        "breakouts": top(m.filter(pl.col("created_at") >= dt.datetime.combine(last - dt.timedelta(days=30), dt.time())), "dl_7d"),
        "likes_7d": top(m.filter(pl.col("dl30") >= 1_000), "likes_7d"),
        "families": top(m.filter(pl.col("fam_members") >= 10), "fam_dl30"),
        "authors_dl30": top(authors, "dl30"),
        "authors_7d": top(authors, "dl_7d"),
    }
    json.dump(lb, open(os.path.join(OUT, "leaderboards.json"), "w"), default=str)


def main():
    global RAW, OUT
    RAW, OUT = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    days = day_files()
    log("days", len(days), days[0][0], days[-1][0])
    if "--skip-series" not in sys.argv:
        uni = universe(days)
        log("universe", uni.height)
        write_series(days, uni)
    meta = latest_meta().rename({"createdAt": "created_at", "lastModified": "last_modified", "trendingScore": "trending"})
    log("meta", meta.height)
    models = derived(days, meta)
    pairs, fam = families(models)
    models = (models.join(fam, on="id", how="left")
              .with_columns(pl.col("fam_members").fill_null(0))
              .with_columns((pl.col("dl30") + pl.col("fam_dl30_desc").fill_null(0)).alias("fam_dl30"),
                            (pl.col("dl_all") + pl.col("fam_all_desc").fill_null(0)).alias("fam_all"),
                            (pl.col("dl_7d") + pl.col("fam_7d_desc").fill_null(0)).alias("fam_7d"))
              .sort("id"))
    models.write_parquet(os.path.join(OUT, "models.parquet"), compression="zstd", row_group_size=100_000)
    log("models", models.height)
    children = (models.select(pl.col("base_ids").alias("parent"), "id", "base_relation", "author", "dl30", "dl_all", "dl_7d", "likes")
                .explode("parent").drop_nulls("parent").filter(pl.col("parent") != pl.col("id"))
                .sort(["parent", "dl30"], descending=[False, True], nulls_last=True))
    children.write_parquet(os.path.join(OUT, "children.parquet"), compression="zstd", row_group_size=100_000)
    log("children", children.height)
    fam_ids = models.filter(pl.col("fam_members") >= FAMILY_MIN_MEMBERS)["id"].to_list()
    log("families >=", FAMILY_MIN_MEMBERS, len(fam_ids))
    family_series(pairs, fam_ids)
    author_series(models)
    leaderboards(models, days[-1][0])
    skip = hub_series(models, days)
    json.dump({"days": [str(d) for d, _ in days], "built": dt.datetime.utcnow().isoformat() + "Z",
               "models": models.height, "families": len(fam_ids), "skip_days": skip},
              open(os.path.join(OUT, "meta.json"), "w"))
    log("done")


if __name__ == "__main__":
    main()
