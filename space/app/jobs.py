"""Background jobs: pull new dataset versions, and link viewed models from the public Space's README."""
import logging
import os
import threading
import time

import yaml
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

log = logging.getLogger("modelpulse.jobs")

DATA_REPO = os.environ.get("DATA_REPO", "modelpulse/model-pulse-data")
SITE_REPO = os.environ.get("SITE_REPO", "tardellirs/model-pulse")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
REFRESH_EVERY = int(os.environ.get("REFRESH_EVERY", "3600"))
LINK_EVERY = int(os.environ.get("LINK_EVERY", str(3 * 3600)))
LINK_CAP = int(os.environ.get("LINK_CAP", "5000"))
DATASET_LINK_CAP = int(os.environ.get("DATASET_LINK_CAP", "5000"))
# the Hub rejects a README over about 1.02 MB ("request entity too large"), whatever the caps say
README_MAX = int(os.environ.get("README_MAX", "1000000"))


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
    """Keeps the public Space's README `models:` list current, so Model Pulse shows up under "Spaces using".

    Each flush adds models people opened, plus automatic candidates (trending on the Hub, Model Pulse
    rankings, most downloaded). Over LINK_CAP, protected models (trending, rankings) always stay and the
    least downloaded of the rest are dropped. The README must also stay under README_MAX bytes: past it, the least
    downloaded models and datasets go first, compared by monthly downloads.
    """

    def __init__(self, exists, popularity, candidates, datasets=None, ds_popularity=None):
        self.exists = exists            # id -> bool, model is tracked
        self.popularity = popularity    # id -> monthly downloads
        self.candidates = candidates    # () -> (ids to add, ids that must never be dropped)
        self.datasets = datasets        # () -> dataset ids, most used first, for the card's `datasets:` list
        self.ds_popularity = ds_popularity or (lambda did: 0)  # id -> monthly downloads
        self.pending: set[str] = set()
        self.lock = threading.Lock()
        self.api = HfApi()

    def add(self, mid: str):
        with self.lock:
            self.pending.add(mid)

    def flush(self):
        with self.lock:
            opened, self.pending = self.pending, set()
        auto, protected = self.candidates()
        batch = {m for m in opened if self.exists(m)} | set(auto)
        path = hf_hub_download(SITE_REPO, "README.md", repo_type="space", force_download=True)
        original = open(path, encoding="utf-8").read()
        _, front, body = original.split("---", 2)
        meta = yaml.safe_load(front) or {}
        models = list(meta.get("models") or [])
        new = sorted(batch - set(models))
        # datasets: the most downloaded, so Model Pulse also shows up under "Spaces using this dataset"
        old_ds = list(meta.get("datasets") or [])
        ds = (self.datasets() or [])[:DATASET_LINK_CAP] if self.datasets else old_ds
        ds_changed = bool(ds) and set(ds) != set(old_ds)
        if not new and not ds_changed:
            return 0
        models = models + new
        dropped = 0
        if len(models) > LINK_CAP:
            rest = sorted((m for m in models if m not in protected), key=lambda m: self.popularity(m) or 0, reverse=True)
            keep = set(protected) | set(rest[:max(0, LINK_CAP - len(protected & set(models)))])
            dropped = len(models) - len(keep & set(models))
            models = [m for m in models if m in keep]
        meta["models"] = models
        if ds:
            meta["datasets"] = ds

        def render():
            return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000) + "---" + body
        out = render()
        if len(out.encode()) > README_MAX:
            # least downloaded first, models and datasets alike; trending and ranked models always stay
            pool = sorted([(self.popularity(m) or 0, "models", m) for m in meta["models"] if m not in protected]
                          + [(self.ds_popularity(d) or 0, "datasets", d) for d in meta.get("datasets", [])])
            per = len(out.encode()) / max(1, len(meta["models"]) + len(meta.get("datasets", [])))
            k = 0
            while len(out.encode()) > README_MAX and k < len(pool):
                step = max(1, int((len(out.encode()) - README_MAX) / per) + 10)
                gone = {(kind, rid) for _, kind, rid in pool[k:k + step]}
                k += step
                for kind in ("models", "datasets"):
                    meta[kind] = [r for r in meta.get(kind, []) if (kind, r) not in gone]
                out = render()
            dropped += sum(1 for _, kind, _ in pool[:k] if kind == "models")
            models, ds = meta["models"], meta.get("datasets", [])
        if out == original:  # the trim undid the change
            return 0
        self.api.upload_file(path_or_fileobj=out.encode(), path_in_repo="README.md", repo_id=SITE_REPO, repo_type="space",
                             commit_message=f"Link {len(new)} models" + (f", drop {dropped}" if dropped else "") + (f", {len(ds)} datasets" if ds_changed else ""))
        log.info("linked %d models, dropped %d (%d total), datasets %d%s", len(new), dropped, len(models), len(ds), " (updated)" if ds_changed else "")
        return len(new)

    def run(self):
        time.sleep(120)  # let the store settle after startup
        while True:
            try:
                self.flush()
            except Exception:
                log.exception("link flush failed")
            time.sleep(LINK_EVERY)


def trending_models(limit: int = 300):
    try:
        return [m.id for m in HfApi().list_models(sort="trending_score", limit=limit)]
    except Exception:
        log.exception("could not list trending models")
        return []


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

