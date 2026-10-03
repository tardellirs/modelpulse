"""Read-only data access over the Model Pulse parquet dataset (DuckDB)."""
import json
import os
import threading
from datetime import date

import duckdb

DATA_DIR = os.environ.get("DATA_DIR", "/data")


class Store:
    def __init__(self, root: str = DATA_DIR):
        self.root = root
        self.local = threading.local()
        self.meta = json.load(open(os.path.join(root, "meta.json")))
        self.leaderboards = json.load(open(os.path.join(root, "leaderboards.json")))
        con = duckdb.connect()
        con.execute("SET enable_object_cache=true")
        # big Wrapped queries may spill; keep them bounded and away from the read-only app dir
        con.execute("SET temp_directory='/tmp/duckdb'")
        con.execute(f"SET memory_limit='{os.environ.get('DUCKDB_MEMORY', '4GB')}'")
        self._con = con
        p = lambda f: os.path.join(root, f).replace("'", "''")
        con.execute(f"CREATE VIEW series AS SELECT * FROM read_parquet('{p('series/*.parquet')}')")
        con.execute(f"CREATE VIEW family_series AS SELECT * FROM read_parquet('{p('family_series/*.parquet')}')")
        con.execute(f"CREATE VIEW author_series AS SELECT * FROM read_parquet('{p('author_series/*.parquet')}')")
        con.execute(f"CREATE VIEW children AS SELECT * FROM read_parquet('{p('children.parquet')}')")
        # models is small enough to keep in memory; it powers search and lookups
        con.execute(f"CREATE TABLE models AS SELECT * FROM read_parquet('{p('models.parquet')}')")
        con.execute(f"CREATE TABLE hub AS SELECT * FROM read_parquet('{p('hub_series.parquet')}')")
        con.execute("CREATE TABLE search_ix AS SELECT id, lower(id) AS lid, author, pipeline_tag, dl30 FROM models")

    def con(self):
        c = getattr(self.local, "c", None)
        if c is None:
            c = self.local.c = self._con.cursor()
        return c

    def _rows(self, sql, args=()):
        cur = self.con().execute(sql, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def model(self, mid: str):
        rows = self._rows("SELECT * FROM models WHERE id = ?", [mid])
        if not rows:
            rows = self._rows("SELECT * FROM models WHERE lower(id) = lower(?)", [mid])
        return rows[0] if rows else None

    def series(self, mid: str):
        return self._columns("SELECT day, dl30, dl_all, likes FROM series WHERE id = ? ORDER BY day", [mid])

    def family_series(self, mid: str):
        return self._columns("SELECT day, dl30, dl_all, members FROM family_series WHERE id = ? ORDER BY day", [mid])

    def author_series(self, author: str):
        return self._columns("SELECT day, dl30, dl_all, likes, models FROM author_series WHERE author = ? ORDER BY day", [author])

    def children(self, mid: str, limit: int = 50):
        return self._rows("SELECT id, base_relation AS relation, author, dl30, dl_all, dl_7d, likes FROM children "
                          "WHERE parent = ? ORDER BY dl30 DESC NULLS LAST LIMIT ?", [mid, limit])

    RELATIONS = ("quantized", "finetune", "adapter", "merge")

    def galaxy(self, mid: str, cap: int = 50_000):
        """Every model built on mid, level by level (biggest first), as parallel arrays; index 0 is mid itself."""
        root = self.model(mid)
        if not root:
            return None
        con, code = self.con(), {r: i for i, r in enumerate(self.RELATIONS)}
        ids, parent, rel, dl, idx = [root["id"]], [-1], [-1], [root.get("dl30") or 0], {root["id"]: 0}
        frontier = [root["id"]]
        for _ in range(8):
            if not frontier or len(ids) >= cap:
                break
            rows = con.execute("SELECT parent, id, base_relation, coalesce(dl30, 0) FROM children WHERE parent IN (SELECT unnest(?)) "
                               "ORDER BY dl30 DESC NULLS LAST", [frontier]).fetchall()
            frontier = []
            for p, i, r, v in rows:
                if i in idx or len(ids) >= cap:
                    continue  # a merge can descend from several members; keep its first (shallowest) parent
                idx[i] = len(ids)
                ids.append(i); parent.append(idx[p]); rel.append(code.get(r, 1)); dl.append(v); frontier.append(i)
        # where this model sits in a bigger family, if it is itself a derivative
        lineage, cur = [], root
        for _ in range(8):
            b = con.execute("SELECT base_ids[1] FROM models WHERE id = ?", [cur["id"]]).fetchone()
            nxt = self.model(b[0]) if b and b[0] else None
            if not nxt or nxt["id"] in lineage or nxt["id"] == root["id"]:
                break
            lineage.append(nxt["id"]); cur = nxt
        keep = ("id", "author", "pipeline_tag", "dl30", "dl_all", "likes", "fam_members", "fam_dl30", "fam_all")
        return {"root": {k: root.get(k) for k in keep}, "relations": list(self.RELATIONS), "lineage": lineage,
                "total": int(root.get("fam_members") or 0), "nodes": {"id": ids, "parent": parent, "rel": rel, "dl30": dl}}

    def galaxies(self, limit: int = 16):
        """The biggest families whose base is an original model, not itself a derivative."""
        return self._rows("SELECT id, fam_members, fam_dl30, n_quantized, n_finetune, n_adapter, n_merge FROM models "
                          "WHERE fam_members >= 50 AND coalesce(len(base_ids), 0) = 0 "
                          "ORDER BY fam_members DESC LIMIT ?", [limit])

    # ---------- pages and sitemap ----------

    def find_author(self, name: str):
        r = self.con().execute("SELECT author FROM models WHERE author = ? LIMIT 1", [name]).fetchone() or \
            self.con().execute("SELECT author FROM models WHERE lower(author) = lower(?) LIMIT 1", [name]).fetchone()
        return r[0] if r else None

    def author_summary(self, author: str):
        r = self.con().execute("SELECT count(*), sum(dl30), sum(dl_all), sum(likes) FROM models WHERE author = ?", [author]).fetchone()
        return {"models": r[0], "dl30": r[1] or 0, "dl_all": r[2] or 0, "likes": r[3] or 0}

    def top_models(self, n: int):
        return self._rows("SELECT id, pipeline_tag, dl30 FROM models ORDER BY dl30 DESC NULLS LAST LIMIT ?", [n])

    def sitemap_authors(self, n: int):
        return [r[0] for r in self.con().execute(
            "SELECT author FROM models GROUP BY author HAVING sum(dl30) >= 1000 ORDER BY sum(dl30) DESC LIMIT ?", [n]).fetchall()]

    def sitemap_galaxies(self, n: int):
        return [r[0] for r in self.con().execute(
            "SELECT id FROM models WHERE fam_members >= 20 ORDER BY fam_dl30 DESC NULLS LAST LIMIT ?", [n]).fetchall()]

    def author_models(self, author: str, limit: int = 200):
        return self._rows("SELECT id, pipeline_tag, params, dl30, dl_all, dl_7d, growth_7d, likes FROM models "
                          "WHERE author = ? ORDER BY dl30 DESC NULLS LAST LIMIT ?", [author, limit])

    def top_ids(self, n: int):
        return [r[0] for r in self.con().execute("SELECT id FROM models ORDER BY dl30 DESC NULLS LAST LIMIT ?", [n]).fetchall()]

    def search(self, q: str, limit: int = 12):
        q = q.strip().lower()
        if not q:
            return []
        return self._rows(
            "SELECT id, pipeline_tag, dl30 FROM search_ix WHERE lid LIKE ? "
            "ORDER BY (lid = ?) DESC, starts_with(lid, ?) DESC, starts_with(split_part(lid,'/',2), ?) DESC, dl30 DESC NULLS LAST LIMIT ?",
            [f"%{q}%", q, q, q, limit])

    def hub(self, top: int = 7):
        tags = [r["pipeline_tag"] for r in self._rows(
            "SELECT pipeline_tag FROM hub WHERE day >= (SELECT max(day) - INTERVAL 90 DAY FROM hub) AND pipeline_tag <> 'other' "
            "GROUP BY 1 ORDER BY sum(dl) DESC LIMIT ?", [top])]
        data = self._columns(
            "SELECT day, CASE WHEN list_contains(?, pipeline_tag) THEN pipeline_tag ELSE 'other' END AS tag, sum(dl)::BIGINT AS dl "
            "FROM hub GROUP BY ALL ORDER BY day", [tags])
        return {"tags": tags + ["other"], **data}

    def _columns(self, sql, args):
        cur = self.con().execute(sql, args)
        cols = [d[0] for d in cur.description]
        data = {c: [] for c in cols}
        for r in cur.fetchall():
            for c, v in zip(cols, r):
                data[c].append(v.isoformat() if isinstance(v, date) else v)
        return data
