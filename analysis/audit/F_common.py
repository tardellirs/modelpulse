"""Shared helpers for the F_* audit scripts. DATA points at a local copy of /opt/modelpulse/data (rsync, excluding datasets/spaces)."""
import os, json, duckdb, datetime as dt
DATA = os.environ.get("MP_DATA", "/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad/d")
WORK = os.environ.get("MP_WORK", os.path.dirname(DATA))
META = json.load(open(f"{DATA}/meta.json"))
SKIP = META["skip_days"]; LOW = META["low_days"]; LAST = META["days"][-1]
def con(db=None, mem="5GB"):
    c = duckdb.connect(db) if db else duckdb.connect()
    c.execute(f"SET memory_limit='{mem}'"); c.execute(f"SET temp_directory='{WORK}/duck_tmp'"); c.execute("SET threads=4")
    return c
def views(c):
    for n, g in [("series", "series/*.parquet"), ("fam", "family_series/*.parquet"), ("auth", "author_series/*.parquet")]:
        c.execute(f"CREATE OR REPLACE VIEW {n} AS SELECT * FROM read_parquet('{DATA}/{g}')")
    c.execute(f"CREATE OR REPLACE VIEW models AS SELECT * FROM read_parquet('{DATA}/models.parquet')")
    c.execute(f"CREATE OR REPLACE VIEW children AS SELECT * FROM read_parquet('{DATA}/children.parquet')")
    c.execute("CREATE OR REPLACE TABLE skip(day DATE)")
    for d in SKIP: c.execute("INSERT INTO skip VALUES (?)", [d])
    c.execute("CREATE OR REPLACE TABLE low(day DATE)")
    for d in LOW: c.execute("INSERT INTO low VALUES (?)", [d])
    return c
def show(c, sql, n=60):
    cur = c.execute(sql); cols = [d[0] for d in cur.description]; rows = cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:n]: print(" | ".join("" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v)) for v in r))
    if len(rows) > n: print(f"... {len(rows)} rows")
    return rows
