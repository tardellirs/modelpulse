"""Build the datasets and Spaces parts of Model Pulse from raw daily snapshots.

    python build_repos.py RAW_DATASETS RAW_SPACES OUT

Outputs (under OUT):
  datasets/series/<YYYY-MM>.parquet   (id, day, dl30, dl_all, likes), like the model series
  datasets/datasets.parquet           one row per tracked dataset: metadata, metrics, usage counts
  datasets/author_series/, datasets/hub_series.parquet, datasets/leaderboards.json
  spaces/series/<YYYY-MM>.parquet     (id, day, likes, trending)
  spaces/spaces.parquet               one row per tracked Space: metadata, metrics, usage counts
  spaces/new_by_sdk.parquet           (day, sdk, n): Spaces created per day, by SDK
  spaces/leaderboards.json
  uses.parquet                        who uses what, from today's cards: a Space using a model or dataset,
                                      a model trained on a dataset (src_kind, src, dst_kind, dst, created, weight)
  repos_meta.json                     days covered, counts, skipped dataset snapshots
"""
import datetime as dt
import glob
import json
import os
import sys

import polars as pl
import pyarrow.compute as pc
import pyarrow.parquet as pq

import build
import stalls

log = build.log
HUB = "cfahlgren1/hub-stats"
SPACE_MIN_LIKES = 1


def latest(kind):
    from huggingface_hub import hf_hub_download
    return hf_hub_download(HUB, f"{kind}.parquet", repo_type="dataset")


def as_list(v):
    """Card fields hold a string or a list of strings."""
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    return [s.strip() for s in items if isinstance(s, str) and s.strip()]


def card_refs(path, field, ids_col="id"):
    """(id, ref) pairs from one list field of each repo's card, without parsing cards that don't mention it."""
    # streamed in batches: the card text of every model on the Hub is several GB, too much to hold at once next to the API
    out_id, out_ref = [], []
    for batch in pq.ParquetFile(path).iter_batches(batch_size=50_000, columns=[ids_col, "cardData"]):
        hit = batch.filter(pc.fill_null(pc.match_substring(batch.column("cardData"), f'"{field}"'), False))
        for rid, card in zip(hit.column(ids_col).to_pylist(), hit.column("cardData").to_pylist()):
            try:
                refs = as_list(json.loads(card).get(field))
            except Exception:
                continue
            for r in dict.fromkeys(refs):
                out_id.append(rid); out_ref.append(r)
    return pl.DataFrame({"src": out_id, "dst": out_ref}, schema={"src": pl.String, "dst": pl.String})


def tag_value(prefix):
    return pl.col("tags").list.eval(pl.element().filter(pl.element().str.starts_with(prefix))).list.first().str.replace(prefix, "")


# ---------- datasets ----------

def dataset_meta(path):
    pf = pq.ParquetFile(path)
    cols = [c for c in ["id", "author", "createdAt", "lastModified", "trendingScore", "tags", "gated", "description"] if c in pf.schema_arrow.names]
    df = pl.from_arrow(pf.read(columns=cols))
    return df.with_columns(
        tag_value("task_categories:").alias("pipeline_tag"),     # named like the model column so ranks and charts reuse it
        tag_value("size_categories:").alias("size"),
        tag_value("license:").alias("license"),
        tag_value("modality:").alias("modality"),
        pl.col("description").str.slice(0, 300).alias("description"),
    ).drop("tags").rename({"createdAt": "created_at", "lastModified": "last_modified", "trendingScore": "trending"})


def build_datasets(raw, out, meta_path):
    build.RAW, build.OUT = raw, os.path.join(out, "datasets")
    os.makedirs(build.OUT, exist_ok=True)
    days = build.day_files()
    log("datasets: days", len(days), days[0][0], days[-1][0])
    uni = build.universe(days)
    log("datasets: universe", uni.height)
    build.write_series(days, uni)
    meta = dataset_meta(meta_path)
    ds = build.derived(days, meta).sort("id")
    build.author_series(ds)
    skip, low = build.hub_series(ds, days, min_frozen=stalls.FROZEN_DATASETS)
    build.SKIP = set(skip)
    return ds, days, skip, low


# ---------- Spaces ----------

def space_meta(path):
    pf = pq.ParquetFile(path)
    df = pl.from_arrow(pf.read(columns=["id", "author", "sdk", "createdAt", "lastModified", "likes", "trendingScore", "cardData"]))
    title = pl.col("cardData").str.json_path_match("$.title")
    return df.with_columns(
        title.alias("title"),
        pl.col("cardData").str.json_path_match("$.emoji").alias("emoji"),
        pl.col("cardData").str.json_path_match("$.short_description").alias("short_description"),
    ).drop("cardData").rename({"createdAt": "created_at", "lastModified": "last_modified", "trendingScore": "trending"})


def read_space_day(day, path):
    return pl.read_parquet(path).with_columns(pl.lit(day).alias("day"), pl.col("likes").cast(pl.Int32),
                                              pl.col("trendingScore").cast(pl.Float32).alias("trending")).drop("trendingScore")


def build_spaces(raw, out, meta_path):
    sdir = os.path.join(out, "spaces")
    os.makedirs(os.path.join(sdir, "series"), exist_ok=True)
    files = sorted(glob.glob(os.path.join(raw, "2*.parquet")))
    days = [(dt.date.fromisoformat(os.path.basename(f)[:10]), f) for f in files]
    log("spaces: days", len(days), days[0][0], days[-1][0])
    # every Space that ever had a like (sampled weekly; likes rarely go back to zero)
    ids = set()
    for day, path in days[::7] + [days[-1]]:
        ids.update(read_space_day(day, path).filter(pl.col("likes") >= SPACE_MIN_LIKES)["id"].to_list())
    uni = pl.DataFrame({"id": sorted(ids)})
    log("spaces: universe", uni.height)
    for m in sorted({d.strftime("%Y-%m") for d, _ in days}):
        frames = [read_space_day(d, p).join(uni, on="id", how="semi") for d, p in days if d.strftime("%Y-%m") == m]
        pl.concat(frames).select("id", "day", "likes", "trending").sort("id", "day").write_parquet(
            os.path.join(sdir, "series", f"{m}.parquet"), compression="zstd", compression_level=9, row_group_size=200_000, statistics=True)
        log("spaces series", m)
    last = days[-1][0]
    sp = space_metrics(sdir, last, space_meta(meta_path))
    new_by_sdk(sdir, meta_path)
    return sp, last


def space_metrics(sdir, last, meta, first=None):
    """Likes now, gained in 7 and 30 days, and ranks, for every Space in the series."""
    series = pl.scan_parquet(os.path.join(sdir, "series", "*.parquet"))
    recent = series.filter(pl.col("day") >= last - dt.timedelta(days=40)).collect()
    now = recent.filter(pl.col("day") == last).select("id", "likes")
    w7 = build.at_or_before(recent, last - dt.timedelta(days=7)).select("id", pl.col("likes").alias("likes_7"), pl.col("day").alias("d7"))
    w30 = build.at_or_before(recent, last - dt.timedelta(days=30)).select("id", pl.col("likes").alias("likes_30"), pl.col("day").alias("d30"))
    if first is None:
        first = series.group_by("id").agg(pl.col("day").min().alias("first_seen")).collect(engine="streaming")

    def gained(ref, d_ref, n, new):
        # per n days over the days really spanned; no reference and not new: unknown, not all-time likes
        return (pl.when(pl.col(ref).is_not_null()).then((pl.col("likes") - pl.col(ref)).clip(0) * n / (pl.lit(last) - pl.col(d_ref)).dt.total_days())
                .when(new).then(pl.col("likes")).round(0).cast(pl.Int64))
    return (now.join(w7, on="id", how="left").join(w30, on="id", how="left").join(first, on="id", how="left")
            .with_columns(gained("likes_7", "d7", 7, pl.col("first_seen") > last - dt.timedelta(days=7)).alias("likes_7d"),
                          gained("likes_30", "d30", 30, pl.col("first_seen") > last - dt.timedelta(days=30)).alias("likes_30d"))
            .drop("likes_7", "likes_30", "d7", "d30")
            .join(meta.drop("likes"), on="id", how="left")
            .with_columns(pl.col("likes").rank("min", descending=True).cast(pl.Int32).alias("rank_likes"),
                          pl.col("likes_7d").rank("min", descending=True).cast(pl.Int32).alias("rank_7d"))
            .sort("id"))


def new_by_sdk(sdir, meta_path):
    """Spaces created per day, by SDK, from the latest snapshot (deleted Spaces aren't in it)."""
    allsp = pl.from_arrow(pq.read_table(meta_path, columns=["sdk", "createdAt"]))
    new = (allsp.drop_nulls("createdAt").with_columns(pl.col("createdAt").dt.date().alias("day"), pl.col("sdk").fill_null("other"))
           .group_by("day", "sdk").agg(pl.len().alias("n")).sort("day", "sdk"))
    new.write_parquet(os.path.join(sdir, "new_by_sdk.parquet"))


# ---------- relations ----------

def model_refs(models_path):
    """Models and the datasets their card lists as training data, with each model's creation date and downloads."""
    info = pl.from_arrow(pq.read_table(models_path, columns=["id", "createdAt", "downloads"])).rename(
        {"id": "src", "createdAt": "created", "downloads": "weight"})
    return (card_refs(models_path, "datasets").join(info, on="src", how="inner")
            .with_columns(pl.lit("model").alias("src_kind"), pl.lit("dataset").alias("dst_kind"), pl.col("weight").cast(pl.Int64)))


def paper_refs(models_path):
    """Models and the arXiv papers their card cites (the Hub's arxiv: tags)."""
    t = pl.from_arrow(pq.read_table(models_path, columns=["id", "tags"]))
    return (t.explode("tags").filter(pl.col("tags").str.starts_with("arxiv:"))
            .select(pl.col("id"), pl.col("tags").str.slice(6).str.strip_chars().alias("arxiv"))
            .filter(pl.col("arxiv").str.contains(r"^\d{4}\.\d{4,5}$")).unique())


def paper_models(refs, models, out):
    """Per arXiv paper: how many models cite it and how much they are downloaded, with the five most downloaded.
    Paper Pulse reads it to put a paper's upvotes next to its use."""
    m = refs.join(models.select("id", "dl30", "dl_all"), on="id", how="inner")
    top = (m.sort("dl30", descending=True, nulls_last=True).group_by("arxiv", maintain_order=True).head(5)
           .group_by("arxiv").agg(pl.struct(pl.col("id"), pl.col("dl30").fill_null(0)).alias("top")))
    pm = (m.group_by("arxiv").agg(pl.len().alias("models"), pl.col("dl30").sum(), pl.col("dl_all").sum())
          .join(top, on="arxiv", how="left").sort("dl30", descending=True))
    pm.write_parquet(os.path.join(out, "paper_models.parquet"), compression="zstd")
    log("paper_models", pm.height, "papers,", m.height, "model citations")
    return pm


def build_uses(out, spaces_path, refs):
    created = pl.from_arrow(pq.read_table(spaces_path, columns=["id", "createdAt", "likes"])).rename(
        {"id": "src", "createdAt": "created", "likes": "weight"}).with_columns(pl.col("weight").cast(pl.Int64))
    sm = card_refs(spaces_path, "models").with_columns(pl.lit("space").alias("src_kind"), pl.lit("model").alias("dst_kind"))
    sd = card_refs(spaces_path, "datasets").with_columns(pl.lit("space").alias("src_kind"), pl.lit("dataset").alias("dst_kind"))
    cols = ["src_kind", "src", "dst_kind", "dst", "created", "weight"]
    uses = (pl.concat([pl.concat([sm, sd]).join(created, on="src", how="left").select(cols), refs.select(cols)])
            .with_columns(pl.col("created").dt.date()).sort("dst_kind", "dst", "created"))
    uses.write_parquet(os.path.join(out, "uses.parquet"), compression="zstd", row_group_size=100_000)
    log("uses", uses.height, uses.group_by("src_kind", "dst_kind").len().to_dicts())
    return uses


def count_uses(uses, dst_kind, src_kind, name):
    return (uses.filter((pl.col("dst_kind") == dst_kind) & (pl.col("src_kind") == src_kind))
            .group_by("dst").agg(pl.len().alias(name)).rename({"dst": "id"}))


# ---------- rankings ----------

def top(df, by, n=100, cols=None, spark=None):
    rows = df.sort(by, descending=True, nulls_last=True).head(n)
    rows = rows.select([c for c in (cols or rows.columns) if c in rows.columns]).to_dicts()
    if spark:
        sp = spark([r["id"] for r in rows])
        for r in rows:
            r["spark"] = sp.get(r["id"], [])
    return rows


def space_sparks(out, last):
    def f(ids):
        s = (pl.scan_parquet(os.path.join(out, "spaces", "series", "*.parquet"))
             .filter(pl.col("id").is_in(ids) & (pl.col("day") >= last - dt.timedelta(days=29)))
             .select("id", "day", "likes").collect().sort("id", "day")
             .with_columns(pl.col("likes").diff().over("id").clip(0).alias("d")).drop_nulls("d")
             .group_by("id", maintain_order=True).agg(pl.col("d")))
        return dict(zip(s["id"].to_list(), s["d"].to_list()))
    return f


def leaderboards(out, ds, sp, last_ds, last_sp):
    since = lambda last: dt.datetime.combine(last - dt.timedelta(days=30), dt.time())
    dcols = ["id", "author", "pipeline_tag", "size", "dl30", "dl_all", "dl_7d", "dl_base7d", "growth_7d", "likes", "likes_7d",
             "created_at", "used_by_models", "used_by_spaces"]
    spark = lambda ids: build.sparks(ids, last_ds)
    dlb = {
        "updated": str(last_ds),
        "gainers_7d": top(ds, "dl_7d", cols=dcols, spark=spark),
        "dl30": top(ds, "dl30", cols=dcols, spark=spark),
        "dl_all": top(ds, "dl_all", cols=dcols, spark=spark),
        "growth_7d": top(build.steady(ds.filter((pl.col("dl_base7d") >= 1_000) & (pl.col("dl30") >= 10_000))), "growth_7d", cols=dcols, spark=spark),
        "breakouts": top(build.steady(ds.filter(pl.col("created_at") >= since(last_ds)), build.SPIKY_NEW, 3), "dl_7d", cols=dcols, spark=spark),
        "used_by_models": top(ds, "used_by_models", cols=dcols, spark=spark),
    }
    json.dump(dlb, open(os.path.join(out, "datasets", "leaderboards.json"), "w"), default=str)
    scols = ["id", "author", "title", "emoji", "sdk", "likes", "likes_7d", "likes_30d", "trending", "created_at", "uses"]
    sspark = space_sparks(out, last_sp)
    slb = {
        "updated": str(last_sp),
        "likes_7d": top(sp, "likes_7d", cols=scols, spark=sspark),
        "likes_30d": top(sp, "likes_30d", cols=scols, spark=sspark),
        "trending": top(sp, "trending", cols=scols, spark=sspark),
        "breakouts": top(sp.filter(pl.col("created_at") >= since(last_sp)), "likes_7d", cols=scols, spark=sspark),
        "most_liked": top(sp, "likes", cols=scols, spark=sspark),
    }
    json.dump(slb, open(os.path.join(out, "spaces", "leaderboards.json"), "w"), default=str)
    log("leaderboards written")


def finish(out, ds, sp, uses, ds_days, last_sp, counters):
    """Usage counts, tables, rankings and meta: shared by the full build and the daily update.

    `counters` is the stall state kept in repos_meta.json: skip_days, low_days, and frozen / rollback when known (see stalls.py).
    """
    ds = (ds.drop("used_by_models", "used_by_spaces", strict=False)
            .join(count_uses(uses, "dataset", "model", "used_by_models"), on="id", how="left")
            .join(count_uses(uses, "dataset", "space", "used_by_spaces"), on="id", how="left")
            .with_columns(pl.col("used_by_models").fill_null(0), pl.col("used_by_spaces").fill_null(0)))
    sp = sp.drop("uses", strict=False).join(
        uses.filter(pl.col("src_kind") == "space").group_by("src").agg(pl.len().alias("uses")).rename({"src": "id"}), on="id", how="left")
    ds.write_parquet(os.path.join(out, "datasets", "datasets.parquet"), compression="zstd", row_group_size=100_000)
    sp.write_parquet(os.path.join(out, "spaces", "spaces.parquet"), compression="zstd", row_group_size=100_000)
    leaderboards(out, ds, sp, ds_days[-1][0], last_sp)
    json.dump({"datasets_days": [str(d) for d, _ in ds_days], "datasets": ds.height, "spaces": sp.height,
               "spaces_last": str(last_sp), **counters, "built": dt.datetime.now(dt.timezone.utc).isoformat()},
              open(os.path.join(out, "repos_meta.json"), "w"))
    log("done: datasets", ds.height, "spaces", sp.height)


def main():
    raw_ds, raw_sp, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    ds_path, sp_path, md_path = latest("datasets"), latest("spaces"), latest("models")
    ds, ds_days, skip, low = build_datasets(raw_ds, out, ds_path)
    sp, last_sp = build_spaces(raw_sp, out, sp_path)
    uses = build_uses(out, sp_path, model_refs(md_path))
    finish(out, ds, sp, uses, ds_days, last_sp, {"skip_days": skip, "low_days": low})


if __name__ == "__main__":
    main()
