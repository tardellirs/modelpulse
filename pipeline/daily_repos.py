"""Daily update of the datasets and Spaces parts, run after the models update.

    HF_TOKEN=... python daily_repos.py WORKDIR [--repo modelpulse/model-pulse-data] [--no-upload] [--force]

Appends the newest hub-stats snapshot of datasets.parquet and spaces.parquet to this month's partitions, recomputes
metrics, usage and rankings, and uploads what changed. Model -> dataset references come from WORKDIR/model_refs.parquet,
written by daily.py from the same day's models snapshot (kept from the last run if it's missing).
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
import build_repos as br
import stalls
from daily import months_back

SRC = "cfahlgren1/hub-stats"


def latest_commit(api, kind):
    for c in api.list_repo_commits(SRC, repo_type="dataset"):  # newest first
        if f"{kind}.parquet" in (c.title or ""):
            return c.created_at.date(), c.commit_id, c.created_at
    raise RuntimeError(f"no {kind}.parquet commit found")


def append_month(path, today):
    cur = pl.read_parquet(path).filter(pl.col("day") != today["day"][0]) if os.path.exists(path) else today.clear()
    df = pl.concat([cur, today.cast(cur.schema) if cur.height else today]).sort("id", "day")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.write_parquet(path, compression="zstd", compression_level=9, row_group_size=200_000, statistics=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--repo", default="modelpulse/model-pulse-data")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    api = HfApi()
    out = os.path.join(a.workdir, "repos")
    cache = os.path.join(a.workdir, "cache_repos")
    ds_day, ds_sha, ds_taken = latest_commit(api, "datasets")
    sp_day, sp_sha, _ = latest_commit(api, "spaces")

    rmeta = json.load(open(hf_hub_download(a.repo, "repos_meta.json", repo_type="dataset", local_dir=out)))
    if str(ds_day) in rmeta["datasets_days"] and str(sp_day) <= rmeta["spaces_last"] and not a.force:
        print(f"datasets {ds_day} and spaces {sp_day} already in dataset, nothing to do")
        return
    months = months_back(max(ds_day, sp_day), 3)
    patterns = ["datasets/datasets.parquet", "datasets/hub_series.parquet", "datasets/renames.parquet", "spaces/spaces.parquet", "uses.parquet"] + [
        f"{d}/{m}.parquet" for d in ("datasets/series", "datasets/author_series", "spaces/series") for m in months]
    snapshot_download(a.repo, repo_type="dataset", local_dir=out, allow_patterns=patterns)
    changed = ["repos_meta.json", "uses.parquet"]

    # ---- datasets ----
    build.OUT = os.path.join(out, "datasets")
    ds_path = hf_hub_download(SRC, "datasets.parquet", repo_type="dataset", revision=ds_sha, cache_dir=cache)
    snap = pl.from_arrow(pq.read_table(ds_path, columns=["id", "downloads", "downloadsAllTime", "likes"]))
    meta = br.dataset_meta(ds_path)
    today = (snap.rename({"downloads": "dl30", "downloadsAllTime": "dl_all"})
             .with_columns(pl.lit(ds_day).alias("day"), pl.col("dl30").cast(pl.Int32), pl.col("likes").cast(pl.Int32))
             .select("id", "day", "dl30", "dl_all", "likes"))
    old = pl.read_parquet(os.path.join(build.OUT, "datasets.parquet"), columns=["id", "first_seen"])
    active = today.filter((pl.col("dl30") >= 10) | (pl.col("likes") >= 1) | (pl.col("dl_all") >= 50)).select("id")
    today = today.join(pl.concat([old.select("id"), active]).unique(), on="id", how="semi").unique("id", keep="last")
    m = ds_day.strftime("%Y-%m")
    sp_month = os.path.join(build.OUT, "series", f"{m}.parquet")
    partial = set(rmeta.get("partial", []))  # incomplete snapshots are never measured from (see stalls.py)
    prev_day = dt.date.fromisoformat(max(d for d in rmeta["datasets_days"] if d != str(ds_day) and d not in partial))
    append_month(sp_month, today)
    # how the counters moved since the last snapshot: frozen share (stalls) and rollbacks (see stalls.py)
    def snap(d):
        return (pl.scan_parquet(os.path.join(build.OUT, "series", "*.parquet")).filter(pl.col("day") == d)
                .select("id", "dl_all", "dl30").collect())
    prev = snap(prev_day)
    if stalls.is_partial(prev.drop_nulls("dl_all"), today.drop_nulls("dl_all")):
        build.log("partial dataset snapshot:", today.height, "rows against", prev.height, "the day before; left out")
        rmeta["partial"] = sorted(partial | {str(ds_day)})
        skip = set(rmeta.get("skip_days", [])) | {str(ds_day)}
        chain = []
    else:
        frozen, back = stalls.signals(prev, today)
        rb = stalls.Rollbacks(rmeta.get("rollback"))
        if (ds_day - prev_day).days == 1 and rb.state is None:
            rmeta.setdefault("frozen", {})[str(ds_day)] = frozen
        base_day = dt.date.fromisoformat(rb.state["base"]) if rb.state else prev_day
        base = prev if base_day == prev_day else snap(base_day)
        verdict = rb.check(base_day, base, ds_day, today, back)
        skip = set(rmeta.get("skip_days", []))
        if verdict == "hold":
            rmeta["rollback"] = rb.state
            skip.add(str(ds_day))
            build.log("rollback: dataset counters went down for", f"{back:.1%}", "; snapshot set aside, measuring from", base_day)
        else:
            rmeta.pop("rollback", None)
            if verdict == "release":  # the drop lasted: a correction, so the held snapshots count after all
                skip -= set(rb.released)
            if rb.recovered:  # their catch-up joins them in a stall window (see stalls.settle)
                rmeta["pending"] = sorted(set(rmeta.get("pending", [])) | set(rb.recovered))
                build.log("no rollback after all; using", rb.released)
        # measured from the base snapshot to today, through the held ones when they were released
        chain = [] if verdict == "hold" else [(base_day, base)] + [(dt.date.fromisoformat(d), snap(dt.date.fromisoformat(d))) for d in rb.released] + [(ds_day, today)]
    rmeta["skip_days"] = sorted(skip)
    build.SKIP = skip
    # a snapshot taken soon after the one before makes a short day, never a low one (see stalls.py)
    if rmeta.get("snapshot_at"):
        hours = (ds_taken - dt.datetime.fromisoformat(rmeta["snapshot_at"])).total_seconds() / 3600
        if hours < stalls.SHORT_HOURS:
            rmeta["short_days"] = sorted(set(rmeta.get("short_days", [])) | {str(ds_day)})
            build.log("short dataset day:", ds_day, f"{hours:.1f}h after the previous snapshot")
    rmeta["snapshot_at"] = ds_taken.isoformat()
    # datasets renamed since the last snapshot keep their history under the new id (see build.find_renames)
    if chain:
        new_rn = build.find_renames(prev.select("id", "dl_all").drop_nulls(), today.select("id", "dl_all").drop_nulls())
        if new_rn.height:
            rp = os.path.join(build.OUT, "renames.parquet")
            add = new_rn.with_columns(pl.lit(prev_day).alias("gone"), pl.lit(ds_day).alias("came"))
            old_rn = pl.read_parquet(rp) if os.path.exists(rp) else None
            (pl.concat([old_rn.select(add.columns), add]) if old_rn is not None else add).unique("old", keep="last").write_parquet(rp)
            build.log("datasets renamed:", new_rn.height, new_rn.head(5).rows())
            changed.append("datasets/renames.parquet")
    days = [(dt.date.fromisoformat(d), None) for d in rmeta["datasets_days"] if d != str(ds_day)] + [(ds_day, None)]
    first = pl.concat([old.drop_nulls("first_seen"), today.select("id", pl.col("day").alias("first_seen"))]).group_by("id").agg(pl.col("first_seen").min())
    ds = build.derived(days, meta, first=first).sort("id")
    build.author_series(ds, source=pl.scan_parquet(sp_month))
    # Hub-wide dataset downloads for the days since the base snapshot, then settle any stalled counters
    hp = os.path.join(build.OUT, "hub_series.parquet")
    hub = pl.read_parquet(hp)
    tags = ds.select("id", pl.col("pipeline_tag").fill_null("other"))
    for frm, to in zip(chain, chain[1:]):
        new = stalls.increment(frm, to, tags)
        hub = pl.concat([hub.filter(~pl.col("day").is_in(new["day"].unique().implode())), new]).sort("day", "pipeline_tag")
    snaps = [dt.date.fromisoformat(d) for d in sorted(set(rmeta["datasets_days"]) | {str(ds_day)}) if d not in set(rmeta.get("partial", []))]
    hub, wins = stalls.settle(hub, rmeta, ds_day, min_frozen=stalls.FROZEN_DATASETS, snaps=snaps)
    hub.write_parquet(hp)
    build.SKIP = set(rmeta.get("skip_days", []))
    ds_days = [(d, None) for d, _ in days]
    changed += ["datasets/datasets.parquet", "datasets/hub_series.parquet", "datasets/leaderboards.json",
                f"datasets/series/{m}.parquet", f"datasets/author_series/{m}.parquet"]

    # ---- Spaces ----
    sdir = os.path.join(out, "spaces")
    sp_path = hf_hub_download(SRC, "spaces.parquet", repo_type="dataset", revision=sp_sha, cache_dir=cache)
    stoday = br.read_space_day(sp_day, sp_path).select("id", "day", "likes", "trending")
    old_sp = pl.read_parquet(os.path.join(sdir, "spaces.parquet"), columns=["id", "first_seen"])
    stoday = stoday.join(pl.concat([old_sp.select("id"), stoday.filter(pl.col("likes") >= br.SPACE_MIN_LIKES).select("id")]).unique(), on="id", how="semi")
    sm = sp_day.strftime("%Y-%m")
    if stoday.height < stalls.PARTIAL * old_sp.height:
        # a truncated snapshot (2026-01-17..22 held 1,000 Spaces): keep yesterday's Spaces as they are
        build.log("partial Spaces snapshot:", stoday.height, "rows against", old_sp.height, "tracked; Spaces left as they were")
        sp = pl.read_parquet(os.path.join(sdir, "spaces.parquet"))
    else:
        append_month(os.path.join(sdir, "series", f"{sm}.parquet"), stoday)
        sfirst = pl.concat([old_sp.drop_nulls("first_seen"), stoday.select("id", pl.col("day").alias("first_seen"))]).group_by("id").agg(pl.col("first_seen").min())
        sp = br.space_metrics(sdir, sp_day, br.space_meta(sp_path), first=sfirst)
        br.new_by_sdk(sdir, sp_path)
        changed += ["spaces/spaces.parquet", "spaces/new_by_sdk.parquet", "spaces/leaderboards.json", f"spaces/series/{sm}.parquet"]

    # ---- who uses what ----
    refs_path = os.path.join(a.workdir, "model_refs.parquet")
    if os.path.exists(refs_path):
        refs = pl.read_parquet(refs_path)
    else:  # keep yesterday's model -> dataset references
        refs = pl.read_parquet(os.path.join(out, "uses.parquet")).filter(pl.col("src_kind") == "model").with_columns(
            pl.col("created").cast(pl.Datetime))
    uses = br.build_uses(out, sp_path, refs)
    shutil.rmtree(cache, ignore_errors=True)
    br.finish(out, ds, sp, uses, ds_days, sp_day, {k: rmeta[k] for k in ("skip_days", "low_days", "short_days", "snapshot_at", "partial", "frozen", "rollback", "pending") if k in rmeta})

    if a.no_upload:
        build.log("done (no upload)")
        return
    api.upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=out, allow_patterns=changed,
                      commit_message=f"Daily update: datasets {ds_day}, spaces {sp_day}")
    build.log("uploaded datasets", ds_day, "spaces", sp_day)


if __name__ == "__main__":
    main()
