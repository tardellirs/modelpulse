"""Background jobs: pull new dataset versions, and link viewed models from the public Space's README."""
import logging
import os
import threading
import time

import yaml
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

log = logging.getLogger("modelpulse.jobs")

DATA_REPO = os.environ.get("DATA_REPO", "modelpulse/model-pulse-data")
SITE_REPO = os.environ.get("SITE_REPO", "modelpulse/model-pulse")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
REFRESH_EVERY = int(os.environ.get("REFRESH_EVERY", "3600"))
LINK_EVERY = int(os.environ.get("LINK_EVERY", str(3 * 3600)))
LINK_CAP = int(os.environ.get("LINK_CAP", "5000"))


def refresher(current_sha, on_new):
    """Poll the dataset repo; when it moves, sync changed files and swap the store."""
    api = HfApi()
    sha = current_sha
    while True:
        try:
            latest = api.dataset_info(DATA_REPO).sha
            if latest != sha:
                snapshot_download(DATA_REPO, repo_type="dataset", local_dir=DATA_DIR, revision=latest, max_workers=8)
                on_new()
                sha = latest
                open(os.path.join(DATA_DIR, ".sha"), "w").write(latest)
                log.info("dataset refreshed to %s", latest)
        except Exception:
            log.exception("refresh failed")
        time.sleep(REFRESH_EVERY)


class Linker:
    """Collects model ids people open and periodically lists them in the Space README `models:` field."""

    def __init__(self, exists, popularity):
        self.exists = exists
        self.popularity = popularity  # id -> monthly downloads, used to decide what to drop at the cap
        self.pending: set[str] = set()
        self.lock = threading.Lock()
        self.api = HfApi()

    def add(self, mid: str):
        with self.lock:
            self.pending.add(mid)

    def flush(self):
        with self.lock:
            batch, self.pending = self.pending, set()
        batch = {m for m in batch if self.exists(m)}
        if not batch:
            return 0
        path = hf_hub_download(SITE_REPO, "README.md", repo_type="space", force_download=True)
        text = open(path, encoding="utf-8").read()
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front) or {}
        models = list(meta.get("models") or [])
        known = set(models)
        new = sorted(batch - known)
        if not new:
            return 0
        models = models + new
        if len(models) > LINK_CAP:
            # keep the most downloaded models listed; drop the least downloaded ones
            keep = set(sorted(models, key=lambda m: self.popularity(m) or 0, reverse=True)[:LINK_CAP])
            models = [m for m in models if m in keep]
        meta["models"] = models
        out = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000) + "---" + body
        self.api.upload_file(path_or_fileobj=out.encode(), path_in_repo="README.md", repo_id=SITE_REPO,
                             repo_type="space", commit_message=f"Link {len(new)} model{'s' if len(new) > 1 else ''}")
        log.info("linked %d models (%d total)", len(new), len(models))
        return len(new)

    def run(self):
        while True:
            time.sleep(LINK_EVERY)
            try:
                self.flush()
            except Exception:
                log.exception("link flush failed")


def updater(work_dir: str, check_every: int = 3600):
    """Run the daily incremental build whenever hub-stats publishes a new snapshot."""
    import subprocess
    import sys

    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline", "daily.py")
    while True:
        try:
            r = subprocess.run([sys.executable, script, work_dir, "--repo", DATA_REPO],
                               cwd=os.path.dirname(script), capture_output=True, text=True, timeout=3 * 3600)
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            log.info("daily update exit=%s %s", r.returncode, " | ".join(tail))
        except Exception:
            log.exception("daily update failed")
        time.sleep(check_every)
