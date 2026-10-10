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


def peak_share(recent, w1):
    """Share of a repo's downloads this week that came in its single biggest step between snapshots (a CI job or a
    bot pulling one repo for a day shows up as a share near 1)."""
    wk = (recent.join(w1.select("id", "d7"), on="id", how="left")
          .filter(pl.col("d7").is_null() | (pl.col("day") >= pl.col("d7"))).sort("id", "day")
          .with_columns((pl.col("dl_all") - pl.col("dl_all").shift(1).over("id")).clip(0).alias("step"))
          .group_by("id").agg(pl.col("step").max().alias("peak"), pl.col("step").sum().alias("gain"), pl.col("step").count().alias("steps")))
    return wk.select("id", pl.when(pl.col("gain") > 0).then(pl.col("peak") / pl.col("gain")).alias("peak_share"), "steps")


SPIKY = 0.6          # growth boards leave out repos whose week came mostly from one step...
SPIKY_NEW = 0.8      # ...or, for repos created this month, almost all of it once they have a few steps to judge


def steady(df, share=SPIKY, min_steps=0):
    """Rows whose week isn't one spike (unknown shares stay)."""
    return df.filter(pl.col("peak_share").is_null() | (pl.col("steps") < min_steps) | (pl.col("peak_share") <= share))


def derived(days, meta, first=None):
    last = days[-1][0]
    skip = [dt.date.fromisoformat(d) for d in SKIP]
    recent = scan_series().filter((pl.col("day") >= last - dt.timedelta(days=40))
                                  & (~pl.col("day").is_in(skip) | (pl.col("day") == last))).collect()
    now = recent.filter(pl.col("day") == last).select("id", "dl30", "dl_all", "likes")
    # the reference snapshots can be more than 7, 14, 28 days back (skipped stall days, missing days): every change
    # is turned into a rate per 7 days over the days it really spans
    w1 = at_or_before(recent, last - dt.timedelta(days=7)).select("id", pl.col("dl_all").alias("all_7"), pl.col("likes").alias("likes_7"), pl.col("day").alias("d7"))
    w2 = at_or_before(recent, last - dt.timedelta(days=14)).select("id", pl.col("dl_all").alias("all_14"), pl.col("day").alias("d14"))
    w4 = at_or_before(recent, last - dt.timedelta(days=28)).select("id", pl.col("dl_all").alias("all_28"), pl.col("day").alias("d28"))
    w31 = at_or_before(recent, last - dt.timedelta(days=31)).select("id", pl.col("dl_all").alias("all_31"))
    if first is None:
        first = scan_series().group_by("id").agg(pl.col("day").min().alias("first_seen")).collect(engine="streaming")

    def per_week(a, b, d_a, d_b):
        # null when both ends are the same snapshot (two references fell on one day across a gap)
        span = ((pl.lit(d_a) if isinstance(d_a, dt.date) else pl.col(d_a)) - pl.col(d_b)).dt.total_days()
        return pl.when(span > 0).then((pl.col(a) - pl.col(b)).clip(0) * 7 / span)

    new = pl.col("first_seen") > last - dt.timedelta(days=7)   # all of a new repo's downloads fall in this week
    m = (now.join(w1, on="id", how="left").join(w2, on="id", how="left").join(w4, on="id", how="left")
         .join(w31, on="id", how="left").join(first, on="id", how="left")
         # an all-time counter that hasn't moved in 31 days means no downloads in the last 30, whatever the Hub's
         # stale 30-day count still says
         .with_columns(pl.when(pl.col("all_31").is_not_null() & (pl.col("dl_all") == pl.col("all_31"))).then(0)
                       .otherwise(pl.col("dl30")).alias("dl30"))
         .with_columns(
             # a week can't hold more downloads than the 30-day window that contains it; guards against recounts.
             # No reference snapshot and not new: unknown, not the 30-day count
             pl.when(pl.col("all_7").is_not_null()).then(pl.min_horizontal(per_week("dl_all", "all_7", last, "d7"), pl.col("dl30")))
             .when(new).then(pl.min_horizontal(pl.col("dl_all"), pl.col("dl30"))).round(0).cast(pl.Int64).alias("dl_7d"),
             per_week("all_7", "all_14", "d7", "d14").round(0).cast(pl.Int64).alias("dl_prev7d"),
             per_week("all_7", "all_28", "d7", "d28").alias("dl_base7d"),
             pl.when(pl.col("likes_7").is_not_null()).then((pl.col("likes") - pl.col("likes_7")) * 7 / (pl.lit(last) - pl.col("d7")).dt.total_days())
             .when(new).then(pl.col("likes")).round(0).cast(pl.Int64).alias("likes_7d"))
         .with_columns(
             # growth vs the average of the three weeks before, robust to one stalled or backlogged week
             pl.when(pl.col("dl_base7d") >= 100).then(pl.col("dl_7d") / pl.col("dl_base7d") - 1).alias("growth_7d"))
         .join(peak_share(recent, w1), on="id", how="left")
         .drop("all_7", "all_14", "all_28", "all_31", "likes_7", "d7", "d14", "d28"))
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


# ---------- renamed repos ----------
# A repo renamed on the Hub gets a new id: its series ends under the old one and starts again under the new one at
# the same all-time count. renames.parquet (old, new, gone, came) links them, so the new id keeps its history.

def find_renames(prev: pl.DataFrame, cur: pl.DataFrame, min_all: int = 1000) -> pl.DataFrame:
    """Pairs (old, new) between two snapshots of (id, dl_all): an id gone from cur and one new in cur, with the same
    name under another owner or the same owner under another name, at the same all-time count (within 1%)."""
    gone = prev.join(cur.select("id"), on="id", how="anti").filter(pl.col("dl_all") >= min_all)
    came = cur.join(prev.select("id"), on="id", how="anti").filter(pl.col("dl_all") >= min_all * 0.99)
    if not gone.height or not came.height:
        return pl.DataFrame(schema={"old": pl.String, "new": pl.String})
    part = lambda df, c, p: df.select(pl.col("id").alias(c), pl.col("dl_all").alias(p + "all"),
                                      pl.col("id").str.split("/").list.first().str.to_lowercase().alias(p + "org"),
                                      pl.col("id").str.split("/").list.last().str.to_lowercase().alias(p + "name"))
    o, n = part(gone, "old", "o"), part(came, "new", "n")
    pairs = pl.concat([o.join(n, left_on="oname", right_on="nname"), o.join(n, left_on="oorg", right_on="norg")], how="diagonal")
    pairs = (pairs.filter(((pl.col("nall") - pl.col("oall")).abs() <= 0.01 * pl.col("oall")))
             .unique(["old", "new"]).filter(pl.len().over("old") == 1).filter(pl.len().over("new") == 1))
    return pairs.select("old", "new")


def renames() -> pl.DataFrame | None:
    """Known renames (OUT/renames.parquet), each old id pointing at the id the repo has now, with the day it came."""
    p = os.path.join(OUT, "renames.parquet")
    if not os.path.exists(p):
        return None
    r = pl.read_parquet(p, columns=["old", "new", "came"])
    step = dict(zip(r["old"].to_list(), r["new"].to_list()))
    final = []
    for old in r["old"].to_list():
        new, seen = step[old], {old}
        while new in step and new not in seen:
            seen.add(new)
            new = step[new]
        final.append(new)
    return r.with_columns(pl.Series("new", final))


def add_renamed(df: pl.DataFrame, key: str, rn: pl.DataFrame | None) -> pl.DataFrame:
    """Rows of df for current ids, repeated for the old ids that are the same repo."""
    if rn is None or not rn.height:
        return df
    old = rn.select("old", "new").join(df, left_on="new", right_on=key).drop("new").rename({"old": key}).select(df.columns)
    return pl.concat([df, old]).unique()


def before_rename(src: pl.LazyFrame, rn: pl.DataFrame | None) -> pl.LazyFrame:
    """Drop an old id's rows from the day its new id appears (the two can overlap a day)."""
    if rn is None or not rn.height:
        return src
    cut = rn.select(pl.col("old").alias("id"), pl.col("came").alias("_cut")).lazy()
    return src.join(cut, on="id", how="left").filter(pl.col("_cut").is_null() | (pl.col("day") < pl.col("_cut"))).drop("_cut")


# all-time counters start on 2025-02-27: before that a sum of nothing is no data, not 0
DL_ALL_SUM = pl.when(pl.col("dl_all").count() > 0).then(pl.col("dl_all").sum()).alias("dl_all")


def family_series(pairs, fam_ids, source=None):
    p = pairs.filter(pl.col("anc").is_in(fam_ids))
    p = pl.concat([p, pl.DataFrame({"member": fam_ids, "anc": fam_ids})])  # include the base itself
    rn = renames()
    p = add_renamed(p, "member", rn)
    n = 0
    for src in month_sources(source):
        out = (before_rename(src, rn).join(p.lazy(), left_on="id", right_on="member")
               .group_by("anc", "day").agg(pl.col("dl30").cast(pl.Int64).sum(), DL_ALL_SUM, pl.len().alias("members"))
               .rename({"anc": "id"}).collect(engine="streaming"))
        write_months(out, "family_series", "id")
        n += out.height
    log("family_series", n)


def author_series(models, source=None):
    authors = (models.group_by("author").agg(pl.coalesce("dl_all", "dl30").sum().alias("tot")).filter(pl.col("tot") >= AUTHOR_MIN_ALL)
               .select("author"))
    idauth = models.select("id", "author").join(authors, on="author", how="semi")
    rn = renames()
    idauth = add_renamed(idauth, "id", rn)
    n = 0
    for src in month_sources(source):
        out = (before_rename(src, rn).join(idauth.lazy(), on="id")
               .group_by("author", "day").agg(pl.col("dl30").cast(pl.Int64).sum(), DL_ALL_SUM,
                                              pl.col("likes").cast(pl.Int64).sum(), pl.len().alias("models"))
               .collect(engine="streaming"))
        write_months(out, "author_series", "author")
        n += out.height
    log("author_series", n)


def hub_series(models, days, min_frozen=stalls.FROZEN):
    """Hub-wide daily downloads per pipeline_tag: sum of positive dl_all deltas between consecutive snapshots."""
    tags = models.select("id", pl.col("pipeline_tag").fill_null("other"))
    snaps = ((day, read_day(day, path).select("id", "dl_all", "dl30")) for day, path in days)
    raw, frozen, aside, state, partial = stalls.measure(snaps, tags)
    if not raw.height:  # no all-time totals in these snapshots yet
        raw.write_parquet(os.path.join(OUT, "hub_series.parquet"))
        return [], []
    snaps = [d for d, _ in days if d not in set(partial)]
    hub, wins = stalls.settle_history(raw, frozen | {d: 1.0 for d in aside}, min_frozen, snaps)
    hub.write_parquet(os.path.join(OUT, "hub_series.parquet"))
    log("stalls", len(wins), "rollbacks", [str(d) for d in aside])
    return sorted(set(stalls.skip_days(wins)) | {d.isoformat() for d in aside + partial}), stalls.low_days(hub, (), snaps)


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


def family_roots(fams: pl.DataFrame, pairs, n: int = 300) -> pl.DataFrame:
    """The biggest families, leaving out those that sit inside a bigger one on the same board (a base model's
    family already counts its fine-tunes' families)."""
    if pairs is None:
        return fams
    cand = fams.sort("fam_dl30", descending=True, nulls_last=True).head(n)
    inner = pairs.filter(pl.col("member").is_in(cand["id"].implode()) & pl.col("anc").is_in(cand["id"].implode()))["member"]
    return cand.filter(~pl.col("id").is_in(inner.implode()))


def leaderboards(models, last, pairs=None):
    cols = ["id", "author", "pipeline_tag", "params", "dl30", "dl_all", "dl_7d", "dl_prev7d", "dl_base7d", "growth_7d",
            "likes", "likes_7d", "created_at", "fam_members", "fam_dl30", "peak_share", "steps"]
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
        "dl30": top(m, "dl30"),
        "dl_all": top(m, "dl_all"),
        "growth_7d": top(steady(m.filter((pl.col("dl_base7d") >= 1_000) & (pl.col("dl30") >= 10_000))), "growth_7d"),
        "breakouts": top(steady(m.filter(pl.col("created_at") >= dt.datetime.combine(last - dt.timedelta(days=30), dt.time())), SPIKY_NEW, 3), "dl_7d"),
        "likes_7d": top(m.filter(pl.col("dl30") >= 1_000), "likes_7d"),
        "families": top(family_roots(m.filter(pl.col("fam_members") >= 10), pairs), "fam_dl30"),
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
    leaderboards(models, days[-1][0], pairs)
    skip, low = hub_series(models, days)
    json.dump({"days": [str(d) for d, _ in days], "built": dt.datetime.utcnow().isoformat() + "Z",
               "models": models.height, "families": len(fam_ids), "skip_days": skip, "low_days": low},
              open(os.path.join(OUT, "meta.json"), "w"))
    log("done")


if __name__ == "__main__":
    main()
