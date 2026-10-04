"""Fetch all commits of cfahlgren1/hub-stats and save them to C_commits.csv (sha, created_at, title)."""
import csv
from huggingface_hub import HfApi
cs = HfApi().list_repo_commits("cfahlgren1/hub-stats", repo_type="dataset")
with open("C_commits.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["sha", "created_at", "title"])
    for c in cs: w.writerow([c.commit_id, c.created_at.isoformat(), c.title])
print(len(cs))
