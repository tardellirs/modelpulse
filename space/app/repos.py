"""Datasets and Spaces: lookups over the tables written by pipeline/build_repos.py, on the Store's connection."""
import json
import os
import urllib.request
from datetime import date
from functools import lru_cache


@lru_cache(maxsize=4096)
def legacy_id(kind: str, rid: str):
    """Old names without an org ("imdb", "gpt2"): ask the Hub where they live now. kind is "models" or "datasets"."""
    if "/" in rid or not rid.replace("-", "").replace("_", "").replace(".", "").isalnum():
        return None
    try:
        req = urllib.request.Request(f"https://huggingface.co/api/{kind}/{rid}", headers={"User-Agent": "modelpulse"})
        with urllib.request.urlopen(req, timeout=5) as r:
            new = json.loads(r.read()).get("id")
        return new if new and new != rid else None
    except Exception:
        return None


class Repos:
    def __init__(self, store):
        self.s = store
        root = store.root
        self.ok = os.path.exists(os.path.join(root, "repos_meta.json"))
        if not self.ok:
            return
        self.meta = json.load(open(os.path.join(root, "repos_meta.json")))
        self.lb = {k: json.load(open(os.path.join(root, k, "leaderboards.json"))) for k in ("datasets", "spaces")}
        p = lambda f: os.path.join(root, f).replace("'", "''")
        con = store._con
        con.execute(f"CREATE VIEW ds_series AS SELECT * FROM read_parquet('{p('datasets/series/*.parquet')}')")
        con.execute(f"CREATE VIEW ds_author_series AS SELECT * FROM read_parquet('{p('datasets/author_series/*.parquet')}')")
        con.execute(f"CREATE VIEW sp_series AS SELECT * FROM read_parquet('{p('spaces/series/*.parquet')}')")
        con.execute(f"CREATE TABLE datasets AS SELECT * FROM read_parquet('{p('datasets/datasets.parquet')}')")
        con.execute(f"CREATE TABLE spaces AS SELECT * FROM read_parquet('{p('spaces/spaces.parquet')}')")
        con.execute(f"CREATE TABLE uses AS SELECT * FROM read_parquet('{p('uses.parquet')}')")
        con.execute(f"CREATE TABLE new_by_sdk AS SELECT * FROM read_parquet('{p('spaces/new_by_sdk.parquet')}')")
        con.execute(f"CREATE TABLE ds_hub AS SELECT * FROM read_parquet('{p('datasets/hub_series.parquet')}')")
        con.execute("CREATE TABLE ds_skip_days (day DATE)")
        for d in self.meta.get("skip_days", []):
            con.execute("INSERT INTO ds_skip_days VALUES (?)", [d])
        con.execute("CREATE TABLE ds_search AS SELECT id, lower(id) AS lid, dl30 FROM datasets")
        con.execute("CREATE TABLE sp_search AS SELECT id, lower(id) AS lid, lower(coalesce(title, '')) AS ltitle, likes FROM spaces")

    # ---------- lookups ----------

    def _one(self, table: str, rid: str):
        rows = self.s._rows(f"SELECT * FROM {table} WHERE id = ?", [rid]) or self.s._rows(f"SELECT * FROM {table} WHERE lower(id) = lower(?)", [rid])
        return rows[0] if rows else None

    def dataset(self, rid: str):
        return self._one("datasets", rid) if self.ok else None

    def space(self, rid: str):
        return self._one("spaces", rid) if self.ok else None

    def dataset_series(self, rid: str):
        return self.s._columns("SELECT day, dl30, dl_all, likes FROM ds_series WHERE id = ? AND day NOT IN (SELECT day FROM ds_skip_days) ORDER BY day", [rid])

    def space_series(self, rid: str):
        return self.s._columns("SELECT day, likes, trending FROM sp_series WHERE id = ? ORDER BY day", [rid])

    def used_by(self, dst_kind: str, dst: str, src_kind: str, limit: int = 12):
        """Who uses a model or dataset: a count, a month-by-month count of new users, and the biggest users."""
        con = self.s.con()
        n = con.execute("SELECT count(*) FROM uses WHERE dst_kind = ? AND dst = ? AND src_kind = ?", [dst_kind, dst, src_kind]).fetchone()[0]
        if not n:
            return {"count": 0, "months": {"month": [], "n": []}, "top": []}
        months = self.s._columns(
            "SELECT strftime(date_trunc('month', created), '%Y-%m') AS month, count(*) AS n FROM uses "
            "WHERE dst_kind = ? AND dst = ? AND src_kind = ? AND created IS NOT NULL GROUP BY 1 ORDER BY 1", [dst_kind, dst, src_kind])
        if src_kind == "space":
            top = self.s._rows(
                "SELECT u.src AS id, s.title, s.emoji, s.sdk, coalesce(s.likes, u.weight) AS likes, s.likes_7d FROM uses u "
                "LEFT JOIN spaces s ON s.id = u.src WHERE u.dst_kind = ? AND u.dst = ? AND u.src_kind = 'space' "
                "ORDER BY coalesce(s.likes, u.weight) DESC NULLS LAST LIMIT ?", [dst_kind, dst, limit])
        else:
            top = self.s._rows(
                "SELECT u.src AS id, m.pipeline_tag, m.dl30, m.likes FROM uses u LEFT JOIN models m ON m.id = u.src "
                "WHERE u.dst_kind = ? AND u.dst = ? AND u.src_kind = 'model' ORDER BY m.dl30 DESC NULLS LAST LIMIT ?", [dst_kind, dst, limit])
        return {"count": n, "months": months, "top": top}

    def space_uses(self, sid: str):
        """The models and datasets a Space lists in its card, with their downloads."""
        models = self.s._rows(
            "SELECT u.dst AS id, m.pipeline_tag, m.dl30 FROM uses u LEFT JOIN models m ON m.id = u.dst "
            "WHERE u.src_kind = 'space' AND u.src = ? AND u.dst_kind = 'model' ORDER BY m.dl30 DESC NULLS LAST LIMIT 40", [sid])
        datasets = self.s._rows(
            "SELECT u.dst AS id, d.pipeline_tag, d.dl30 FROM uses u LEFT JOIN datasets d ON d.id = u.dst "
            "WHERE u.src_kind = 'space' AND u.src = ? AND u.dst_kind = 'dataset' ORDER BY d.dl30 DESC NULLS LAST LIMIT 40", [sid])
        return {"models": models, "datasets": datasets}

    def model_datasets(self, mid: str):
        return self.s._rows(
            "SELECT u.dst AS id, d.dl30 FROM uses u LEFT JOIN datasets d ON d.id = u.dst "
            "WHERE u.src_kind = 'model' AND u.src = ? AND u.dst_kind = 'dataset' ORDER BY d.dl30 DESC NULLS LAST LIMIT 20", [mid])

    def search(self, q: str, limit: int = 6):
        q = q.strip().lower()
        if not q or not self.ok:
            return {"datasets": [], "spaces": []}
        # the repo name matters more than the org: "fineweb" should find HuggingFaceFW/fineweb before fineweb-x/whatever
        ds = self.s._rows("SELECT id, dl30 FROM ds_search WHERE lid LIKE ? ORDER BY (lid = ? OR split_part(lid,'/',2) = ?) DESC, "
                          "starts_with(split_part(lid,'/',2), ?) DESC, dl30 DESC NULLS LAST LIMIT ?", [f"%{q}%", q, q, q, limit])
        sp = self.s._rows("SELECT s.id, s.likes, sp.title, sp.emoji FROM sp_search s JOIN spaces sp USING (id) "
                          "WHERE s.lid LIKE ? OR s.ltitle LIKE ? ORDER BY (s.lid = ? OR split_part(s.lid,'/',2) = ? OR s.ltitle = ?) DESC, "
                          "s.likes DESC NULLS LAST LIMIT ?", [f"%{q}%", f"%{q}%", q, q, q, limit])
        return {"datasets": ds, "spaces": sp}

    def new_spaces(self):
        """Spaces created per week, by SDK (the five biggest, the rest as other)."""
        sdks = [r[0] for r in self.s.con().execute(
            "SELECT sdk FROM new_by_sdk WHERE day >= current_date - INTERVAL 365 DAY AND sdk <> 'other' GROUP BY 1 ORDER BY sum(n) DESC LIMIT 5").fetchall()]
        data = self.s._columns(
            "SELECT strftime(date_trunc('week', day), '%Y-%m-%d') AS week, CASE WHEN list_contains(?, sdk) THEN sdk ELSE 'other' END AS sdk, "
            "sum(n)::BIGINT AS n FROM new_by_sdk WHERE day >= DATE '2022-01-01' GROUP BY ALL ORDER BY 1", [sdks])
        return {"sdks": sdks + ["other"], **data}

    def top_ids(self, kind: str, n: int):
        table, col = ("datasets", "dl30") if kind == "datasets" else ("spaces", "likes")
        return [r[0] for r in self.s.con().execute(f"SELECT id FROM {table} ORDER BY {col} DESC NULLS LAST LIMIT ?", [n]).fetchall()]


def clean_day(v):
    return v.isoformat() if isinstance(v, date) else v
