"""Daily incremental update of the Model Pulse dataset.

Downloads the newest hub-stats snapshot, appends it to the current month's partitions,
recomputes models/leaderboards, and uploads only the files that changed.

    HF_TOKEN=... python daily.py WORKDIR [--repo modelpulse/model-pulse-data] [--no-upload]
"""
import argparse
import datetime as dt
import json
import os
import shutil

import polars as pl
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

import build
import build_repos
import stalls

SRC = "cfahlgren1/hub-stats"


def latest_snapshot(api):
    commits = api.list_repo_commits(SRC, repo_type="dataset")
    for c in commits:  # newest first
        if "models.parquet" in c.title:
            return c.created_at.date(), c.commit_id, c.created_at
    raise RuntimeError("no models.parquet commit found")


def months_back(day, n):
    out, y, m = [], day.year, day.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--repo", default="modelpulse/model-pulse-data")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    api = HfApi()
    out = build.OUT = os.path.join(a.workdir, "data")
    day, sha, taken = latest_snapshot(api)
    months = months_back(day, 3)

    # 1. bail out early if the dataset already has this day, then fetch current state
    meta = json.load(open(hf_hub_download(a.repo, "meta.json", repo_type="dataset", local_dir=out)))
    if str(day) in meta["days"] and not a.force:
        print(f"{day} already in dataset, nothing to do")
        return
    patterns = ["models.parquet", "hub_series.parquet", "renames.parquet"] + [
        f"{d}/{m}.parquet" for d in ("series", "family_series", "author_series") for m in months]
    snapshot_download(a.repo, repo_type="dataset", local_dir=out, allow_patterns=patterns)
    partial = set(meta.get("partial", []))  # incomplete snapshots are never measured from (see stalls.py)
    prev_day = dt.date.fromisoformat(max(d for d in meta["days"] if d not in partial))
    build.log("new snapshot", day, sha[:8], "previous", prev_day)

    # 2. today's snapshot
    path = hf_hub_download(SRC, "models.parquet", repo_type="dataset", revision=sha,
                           cache_dir=os.path.join(a.workdir, "cache"))
    snap = pl.from_arrow(pq.read_table(path, columns=["id", "downloads", "downloadsAllTime", "likes"]))
    meta_df = build.latest_meta(path).rename({"createdAt": "created_at", "lastModified": "last_modified", "trendingScore": "trending"})
    # the datasets each model lists as training data, for daily_repos.py
    build_repos.model_refs(path).write_parquet(os.path.join(a.workdir, "model_refs.parquet"))
    try:  # the arXiv papers each model cites, for paper_models.parquet below (Paper Pulse); never worth failing the day over
        papers = build_repos.paper_refs(path)
    except Exception as e:
        papers = None
        build.log("paper refs failed:", str(e).splitlines()[0][:200])
    shutil.rmtree(os.path.join(a.workdir, "cache"), ignore_errors=True)  # 1.5 GB per day otherwise
    today = (snap.rename({"downloads": "dl30", "downloadsAllTime": "dl_all"})
             .with_columns(pl.lit(day).alias("day"), pl.col("dl30").cast(pl.Int32), pl.col("likes").cast(pl.Int32))
             .select("id", "day", "dl30", "dl_all", "likes"))
    old_models = pl.read_parquet(os.path.join(out, "models.parquet"), columns=["id", "first_seen"])
    active = today.filter((pl.col("dl30") >= 10) | (pl.col("likes") >= 1) | (pl.col("dl_all") >= 50)).select("id")
    uni = pl.concat([old_models.select("id"), active]).unique()
    today = today.join(uni, on="id", how="semi").unique("id", keep="last")

    # 3. append to this month's series partition
    m = day.strftime("%Y-%m")
    sp = os.path.join(out, "series", f"{m}.parquet")
    cur = pl.read_parquet(sp).filter(pl.col("day") != day) if os.path.exists(sp) else today.clear()
    month_df = pl.concat([cur, today.cast(cur.schema) if cur.height else today]).sort("id", "day")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    month_df.write_parquet(sp, compression="zstd", compression_level=9, row_group_size=200_000, statistics=True)
    build.log("series", m, month_df.height)

    # 3b. how the counters moved since the last snapshot: frozen share (stalls) and rollbacks (see stalls.py)
    def snap(d):
        return (pl.scan_parquet(os.path.join(out, "series", "*.parquet")).filter(pl.col("day") == d)
                .select("id", "dl_all", "dl30").collect())
    prev = snap(prev_day)
    if stalls.is_partial(prev.drop_nulls("dl_all"), today.drop_nulls("dl_all")):
        build.log("partial snapshot:", today.height, "rows against", prev.height, "the day before; left out")
        meta["partial"] = sorted(partial | {str(day)})
        skip = set(meta.get("skip_days", [])) | {str(day)}
        chain = []
    else:
        frozen, back = stalls.signals(prev, today)
        rb = stalls.Rollbacks(meta.get("rollback"))
        if (day - prev_day).days == 1 and rb.state is None:
            meta.setdefault("frozen", {})[str(day)] = frozen
        base_day = dt.date.fromisoformat(rb.state["base"]) if rb.state else prev_day
        base = prev if base_day == prev_day else snap(base_day)
        verdict = rb.check(base_day, base, day, today, back)
        skip = set(meta.get("skip_days", []))
        if verdict == "hold":
            meta["rollback"] = rb.state
            skip.add(str(day))
            build.log("rollback: models counters went down for", f"{back:.1%}", "; snapshot set aside, measuring from", base_day)
        else:
            meta.pop("rollback", None)
            if verdict == "release":  # the drop lasted: a correction, so the held snapshots count after all
                skip -= set(rb.released)
            if rb.recovered:  # their catch-up joins them in a stall window (see stalls.settle)
                meta["pending"] = sorted(set(meta.get("pending", [])) | set(rb.recovered))
                build.log("no rollback after all; using", rb.released)
        # measured from the base snapshot to today, through the held ones when they were released
        chain = [] if verdict == "hold" else [(base_day, base)] + [(dt.date.fromisoformat(d), snap(dt.date.fromisoformat(d))) for d in rb.released] + [(day, today)]
    meta["skip_days"] = sorted(skip)
    build.SKIP = skip

    # 3c. repos renamed since the last snapshot: the new id keeps the old one's history (see build.find_renames)
    if chain:
        new_rn = build.find_renames(prev.select("id", "dl_all").drop_nulls(), today.select("id", "dl_all").drop_nulls())
        if new_rn.height:
            rp = os.path.join(out, "renames.parquet")
            add = new_rn.with_columns(pl.lit(prev_day).alias("gone"), pl.lit(day).alias("came"))
            old_rn = pl.read_parquet(rp) if os.path.exists(rp) else None
            (pl.concat([old_rn.select(add.columns), add]) if old_rn is not None else add).unique("old", keep="last").write_parquet(rp)
            build.log("renamed:", new_rn.height, new_rn.head(5).rows())

    # 4. models, families, children
    days = [(dt.date.fromisoformat(d), None) for d in meta["days"]] + [(day, None)]
    first = pl.concat([old_models.drop_nulls("first_seen"),
                       today.select("id", pl.col("day").alias("first_seen"))]).group_by("id").agg(pl.col("first_seen").min())
    models = build.derived(days, meta_df, first=first)
    pairs, fam = build.families(models)
    models = (models.join(fam, on="id", how="left")
              .with_columns(pl.col("fam_members").fill_null(0))
              .with_columns((pl.col("dl30") + pl.col("fam_dl30_desc").fill_null(0)).alias("fam_dl30"),
                            (pl.col("dl_all") + pl.col("fam_all_desc").fill_null(0)).alias("fam_all"),
                            (pl.col("dl_7d") + pl.col("fam_7d_desc").fill_null(0)).alias("fam_7d"))
              .sort("id"))
    models.write_parquet(os.path.join(out, "models.parquet"), compression="zstd", row_group_size=100_000)
    children = (models.select(pl.col("base_ids").alias("parent"), "id", "base_relation", "author", "dl30", "dl_all", "dl_7d", "likes")
                .explode("parent").drop_nulls("parent").filter(pl.col("parent") != pl.col("id"))
                .sort(["parent", "dl30"], descending=[False, True], nulls_last=True))
    children.write_parquet(os.path.join(out, "children.parquet"), compression="zstd", row_group_size=100_000)
    if papers is not None:
        try:
            build_repos.paper_models(papers, models, out)
        except Exception as e:
            build.log("paper_models failed:", str(e).splitlines()[0][:200])

    # 5. this month's family and author partitions (recomputed from the month's series)
    fam_ids = models.filter(pl.col("fam_members") >= build.FAMILY_MIN_MEMBERS)["id"].to_list()
    src = pl.scan_parquet(sp)
    build.family_series(pairs, fam_ids, source=src)
    build.author_series(models, source=src)

    # 6. hub-wide daily downloads for the new day
    hp = os.path.join(out, "hub_series.parquet")
    hub = pl.read_parquet(hp)
    tags = models.select("id", pl.col("pipeline_tag").fill_null("other"))
    for frm, to in zip(chain, chain[1:]):
        new = stalls.increment(frm, to, tags)
        hub = pl.concat([hub.filter(~pl.col("day").is_in(new["day"].unique().implode())), new]).sort("day", "pipeline_tag")
    # days when the Hub's counters stood still get spread over their catch-up days (see stalls.py)
    snaps = [dt.date.fromisoformat(d) for d in sorted(set(meta["days"]) | {str(day)}) if d not in set(meta.get("partial", []))]
    hub, wins = stalls.settle(hub, meta, day, snaps=snaps)
    if wins:
        build.log("stalls", [f"{w[0]}..{w[-1]}" for w in wins])
    hub.write_parquet(hp)

    # 7. leaderboards + meta
    build.SKIP = set(meta.get("skip_days", []))
    build.leaderboards(models, day, pairs)
    meta["days"] = sorted(set(meta["days"]) | {str(day)})
    # a snapshot taken soon after the one before makes a short day, never a low one (see stalls.py)
    if meta.get("snapshot_at"):
        hours = (taken - dt.datetime.fromisoformat(meta["snapshot_at"])).total_seconds() / 3600
        if hours < stalls.SHORT_HOURS:
            meta["short_days"] = sorted(set(meta.get("short_days", [])) | {str(day)})
            build.log("short day:", day, f"{hours:.1f}h after the previous snapshot")
    meta["snapshot_at"] = taken.isoformat()
    meta.update(built=dt.datetime.now(dt.timezone.utc).isoformat(), models=models.height, families=len(fam_ids))
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"))

    if a.no_upload:
        build.log("done (no upload)")
        return
    changed = ["meta.json", "models.parquet", "children.parquet", "hub_series.parquet", "leaderboards.json", "renames.parquet",
               f"series/{m}.parquet", f"family_series/{m}.parquet", f"author_series/{m}.parquet"]
    if os.path.exists(os.path.join(out, "paper_models.parquet")):
        changed.append("paper_models.parquet")
    api.upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=out, allow_patterns=changed,
                      commit_message=f"Daily update {day}")
    build.log("uploaded", day)


if __name__ == "__main__":
    main()
