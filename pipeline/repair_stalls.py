"""One-off: spread the Hub's stalled counter days in the published hub_series and record them in meta.json.

    HF_TOKEN=... python repair_stalls.py [--repo modelpulse/model-pulse-data] [--dry-run]
"""
import argparse
import json
import os
import tempfile

import polars as pl
from huggingface_hub import HfApi, hf_hub_download

import stalls

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default="modelpulse/model-pulse-data")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

hub = pl.read_parquet(hf_hub_download(a.repo, "hub_series.parquet", repo_type="dataset", force_download=True))
meta = json.load(open(hf_hub_download(a.repo, "meta.json", repo_type="dataset", force_download=True)))
wins = stalls.windows(hub)
fixed = stalls.smooth(hub, wins)
skip = sorted(set(meta.get("skip_days", [])) | set(stalls.skip_days(wins)))
print(len(wins), "windows:", [f"{w[0]}..{w[-1]}" for w in wins])
print("total", hub["dl"].sum(), "->", fixed["dl"].sum(), "| days", hub["day"].n_unique(), "->", fixed["day"].n_unique())
print("skip_days", skip)
if a.dry_run:
    raise SystemExit
meta["skip_days"] = skip
with tempfile.TemporaryDirectory() as d:
    fixed.write_parquet(os.path.join(d, "hub_series.parquet"))
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))
    print(HfApi().upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=d,
                                commit_message="Spread days when the Hub's download counters stood still"))
