# downloads datasets/spaces parts of the HF dataset to the scratchpad
import sys
from huggingface_hub import snapshot_download
snapshot_download("modelpulse/model-pulse-data", repo_type="dataset", local_dir=sys.argv[1],
  allow_patterns=["datasets/series/*","datasets/hub_series.parquet","datasets/datasets.parquet","datasets/leaderboards.json","spaces/*","spaces/series/*","repos_meta.json","uses.parquet","meta.json","hub_series.parquet"])
