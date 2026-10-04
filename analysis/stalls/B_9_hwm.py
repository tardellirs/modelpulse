"""Stage 9: hub daily totals with a per-model high-water mark (delta_t = max(0, a_t - running_max_{t-1})), which cancels counter rollbacks
(2025-05-19/20, 2026-06-13): the rebound after a dip no longer counts as new downloads. Also reports the standing deficit (sum of max - current)."""
import duckdb, glob, time
OUT = "/work/stalls_B"
c = duckdb.connect(); c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
files = sorted(glob.glob("/data/series/*.parquet")); t0 = time.time()
days = []
for f in files:
    for (d,) in c.execute(f"select distinct day from read_parquet('{f}') where dl_all is not null order by 1").fetchall(): days.append((d, f))
days.sort()
def load(d, f):
    c.execute("drop table if exists cur"); c.execute(f"create table cur as select id, dl_all from read_parquet('{f}') where day=DATE '{d}' and dl_all is not null")
c.execute("create table res(day date, prev date, gap int, tot_clip double, tot_hwm double, deficit double, n_below bigint, n bigint)")
load(*days[0]); c.execute("create table mx as select id, dl_all m from cur"); c.execute("alter table cur rename to prv"); pd_ = days[0][0]
for d, f in days[1:]:
    load(d, f); gap = (d - pd_).days
    c.execute(f"""insert into res select DATE '{d}', DATE '{pd_}', {gap}, sum(greatest(cur.dl_all - prv.dl_all, 0))::double, sum(greatest(cur.dl_all - mx.m, 0))::double,
                  sum(greatest(mx.m - cur.dl_all, 0))::double, sum((cur.dl_all < mx.m)::int), count(*)
                  from cur join prv using(id) join mx using(id)""")
    c.execute("update mx set m = cur.dl_all from cur where mx.id = cur.id and cur.dl_all > mx.m")
    c.execute("insert into mx select id, dl_all from cur where id not in (select id from mx)")
    c.execute("drop table prv"); c.execute("alter table cur rename to prv"); pd_ = d
    if d.day == 1: print(d, round(time.time() - t0), flush=True)
c.execute(f"copy res to '{OUT}/hub_hwm.parquet' (format parquet)"); print("done", round(time.time() - t0))
