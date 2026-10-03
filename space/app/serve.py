"""Fetch the dataset snapshot, then serve the app."""
import os

from huggingface_hub import snapshot_download

DATA_DIR = os.environ.get("DATA_DIR", "/data")

if __name__ == "__main__":
    if os.environ.get("DATA_REPO") and not os.path.exists(os.path.join(DATA_DIR, "meta.json")):
        from huggingface_hub import HfApi
        sha = HfApi().dataset_info(os.environ["DATA_REPO"]).sha
        snapshot_download(os.environ["DATA_REPO"], repo_type="dataset", local_dir=DATA_DIR, revision=sha, max_workers=8)
        open(os.path.join(DATA_DIR, ".sha"), "w").write(sha)
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7860, workers=1, proxy_headers=True, forwarded_allow_ips="*")
