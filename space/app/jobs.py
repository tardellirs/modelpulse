"""Background jobs: pull new dataset versions, and keep the public Space's card to its sources."""
import logging
import os
import time

import yaml
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

log = logging.getLogger("modelpulse.jobs")

DATA_REPO = os.environ.get("DATA_REPO", "modelpulse/model-pulse-data")
SITE_REPO = os.environ.get("SITE_REPO", "tardellirs/model-pulse")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
REFRESH_EVERY = int(os.environ.get("REFRESH_EVERY", "3600"))
# the datasets Model Pulse is built from: the only repos the public Space's card names
SOURCES = ["cfahlgren1/hub-stats", DATA_REPO]


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


def card_sources():
    """Set the public Space's card once: no `models:` list (Model Pulse reads models' public stats but runs none of
    them), and `datasets:` only the sources it is built from. Retries hourly until the README matches."""
    time.sleep(120)  # let the store settle after startup
    while True:
        try:
            path = hf_hub_download(SITE_REPO, "README.md", repo_type="space", force_download=True)
            original = open(path, encoding="utf-8").read()
            _, header, body = original.split("---", 2)
            meta = yaml.safe_load(header) or {}
            meta.pop("models", None)
            meta["datasets"] = SOURCES
            out = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000) + "---" + body
            if out != original:
                HfApi().upload_file(path_or_fileobj=out.encode(), path_in_repo="README.md", repo_id=SITE_REPO, repo_type="space",
                                    commit_message="Card: no models list; the datasets are the two sources Model Pulse is built from")
                log.info("card set to its sources")
            return
        except Exception:
            log.exception("card update failed")
            time.sleep(3600)


def updater(work_dir: str, check_every: int = 3600):
    """Run the daily incremental build whenever hub-stats publishes a new snapshot."""
    import subprocess
    import sys

    pipeline = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline")
    while True:
        # models first: it leaves today's model -> dataset references for the datasets and Spaces update
        for name in ("daily.py", "daily_repos.py"):
            try:
                r = subprocess.run([sys.executable, os.path.join(pipeline, name), work_dir, "--repo", DATA_REPO],
                                   cwd=pipeline, capture_output=True, text=True, timeout=3 * 3600)
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                log.info("%s exit=%s %s", name, r.returncode, " | ".join(tail))
            except Exception:
                log.exception("%s failed", name)
        time.sleep(check_every)


INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "c72eb45891620dc99ed7f5774930994b")


def indexnow(urls: list[str], site: str = "https://modelpulse.ifsp.dev"):
    """Tell Bing and other IndexNow engines which pages changed (up to 10,000 per call)."""
    import json
    import urllib.request
    for i in range(0, len(urls), 10_000):
        body = json.dumps({"host": site.split("//", 1)[1], "key": INDEXNOW_KEY, "keyLocation": f"{site}/{INDEXNOW_KEY}.txt",
                           "urlList": urls[i:i + 10_000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                log.info("indexnow: %d urls, HTTP %s", len(urls[i:i + 10_000]), r.status)
        except Exception as e:
            log.warning("indexnow failed: %s", e)

