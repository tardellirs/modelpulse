"""Stage 11: rollback episodes treated as one gap interval (skip the snapshots inside): net clipped delta between the bounding snapshots / days."""
import duckdb
c = duckdb.connect(); c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
def net(f1, d1, f2, d2, n):
    c.execute("drop table if exists a"); c.execute("drop table if exists b")
    c.execute(f"create table a as select id, dl_all from read_parquet('/data/series/{f1}.parquet') where day=DATE '{d1}' and dl_all is not null")
    c.execute(f"create table b as select id, dl_all from read_parquet('/data/series/{f2}.parquet') where day=DATE '{d2}' and dl_all is not null")
    r = c.execute("select sum(greatest(b.dl_all-a.dl_all,0))::double, sum(b.dl_all-a.dl_all)::double, count(*) from a join b using(id)").fetchone()
    print(f"{d1} -> {d2} ({n} days): clipped net {r[0]/1e6:.0f}M = {r[0]/n/1e6:.1f}M/day ; unclipped net {r[1]/1e6:.0f}M = {r[1]/n/1e6:.1f}M/day ; models {r[2]}", flush=True)
net("2025-05", "2025-05-18", "2025-05", "2025-05-21", 3)
net("2025-05", "2025-05-18", "2025-05", "2025-05-22", 4)
net("2025-05", "2025-05-18", "2025-05", "2025-05-23", 5)
net("2026-06", "2026-06-11", "2026-06", "2026-06-19", 8)
net("2026-06", "2026-06-12", "2026-06", "2026-06-19", 7)
net("2026-06", "2026-06-12", "2026-06", "2026-06-20", 8)
net("2026-06", "2026-06-12", "2026-06", "2026-06-16", 4)
