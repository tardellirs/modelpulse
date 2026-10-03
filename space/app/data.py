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
