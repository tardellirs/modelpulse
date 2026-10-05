"""Server (docker 4g): flow of all raw ids vs ids that are in the dataset series, for sampled day pairs.
The full build (build.hub_series) reads RAW files (all ids); the daily update (daily_repos.py) reads series snapshots (universe only)."""
import duckdb
con=duckdb.connect(); con.execute("SET memory_limit='3GB'; SET threads=2")
con.execute("CREATE TABLE u AS SELECT DISTINCT id FROM read_parquet('/d/datasets/series/2026-0[6-9].parquet')")
con.execute("INSERT INTO u SELECT DISTINCT id FROM read_parquet('/d/datasets/series/2025-0[3-6].parquet') WHERE id NOT IN (SELECT id FROM u)")
print(con.execute("select count(*) from u").fetchone())
pairs=[("2025-04-08","2025-04-09"),("2025-05-28","2025-05-29"),("2025-09-23","2025-09-24"),("2025-12-28","2025-12-29"),("2026-03-24","2026-03-25"),("2026-06-18","2026-06-19"),("2026-08-23","2026-08-24"),("2026-09-29","2026-09-30"),("2026-10-02","2026-10-03")]
for a,b in pairs:
    r=con.execute(f"""SELECT sum(greatest(y.downloadsAllTime-x.downloadsAllTime,0)) tot,
      sum(greatest(y.downloadsAllTime-x.downloadsAllTime,0)) filter (where y.id in (select id from u)) inu,
      count(*) n, count(*) filter (where y.id in (select id from u)) nu
      FROM read_parquet('/r/{b}.parquet') y JOIN read_parquet('/r/{a}.parquet') x USING (id) WHERE y.downloadsAllTime IS NOT NULL""").fetchone()
    print(b,"flow_all",r[0],"flow_in_series_ids",r[1],"share %.4f"%(r[1]/r[0]),"n",r[2],r[3],flush=True)
