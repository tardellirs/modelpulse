"""Stage 1: rebuild RAW Hub-wide daily downloads from per-model dl_all deltas (same method as build.hub_series).
Pass A: per snapshot day -> hub totals per tag (sum of clip(delta,0)/gap), plus candidate ids (delta/gap >= 1000).
Pass B: per-model deltas (all rows) for candidate ids -> /work/stalls_B/big_deltas.parquet
Outputs in /work/stalls_B/: hub_raw_snap.parquet (snap day, prev day, gap, tag, delta_sum, n_models), cand.parquet, big_deltas.parquet
"""
import duckdb, glob, os, time, sys, datetime as dt
OUT = "/work/stalls_B"
c = duckdb.connect()
c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
files = sorted(glob.glob("/data/series/*.parquet"))
t0 = time.time()
# snapshot days (dl_all non-null) per file
days = []
for f in files:
    for (d,) in c.execute(f"select distinct day from read_parquet('{f}') where dl_all is not null order by 1").fetchall():
        days.append((d, f))
days.sort()
print("snapshot days", len(days), days[0][0], days[-1][0], round(time.time() - t0), flush=True)
c.execute("create table tags as select id, coalesce(pipeline_tag,'other') tag from read_parquet('/data/models.parquet')")

def load(d, f):
    c.execute("drop table if exists cur")
    c.execute(f"create table cur as select id, dl_all from read_parquet('{f}') where day=DATE '{d}' and dl_all is not null")

stage = sys.argv[1]
if stage == "A":
    c.execute("create table hub(day date, prev date, gap int, tag varchar, dsum double, n bigint)")
    c.execute("create table hi(id varchar)")
    load(*days[0]); c.execute("alter table cur rename to prv")
    pd_ = days[0][0]
    for d, f in days[1:]:
        load(d, f)
        gap = (d - pd_).days
        c.execute(f"""create or replace table dd as select cur.id, greatest(cur.dl_all - prv.dl_all,0) dl from cur join prv using(id)""")
        c.execute(f"""insert into hub select DATE '{d}', DATE '{pd_}', {gap}, coalesce(t.tag,'other'), sum(dl)::double, count(*)
                      from dd left join tags t using(id) group by 2,3,4""")
        c.execute(f"insert into hi select id from dd where dl/{gap} >= 1000")
        c.execute("drop table prv"); c.execute("alter table cur rename to prv")
        pd_ = d
        if (d.day == 1) or d == days[-1][0]:
            print(d, round(time.time() - t0), flush=True)
    c.execute(f"copy hub to '{OUT}/hub_raw_snap.parquet' (format parquet)")
    c.execute(f"copy (select id, count(*) nhi from hi group by id) to '{OUT}/cand.parquet' (format parquet)")
    print("cand", c.execute("select count(distinct id) from hi").fetchone())
else:
    c.execute(f"create table cand as select id from read_parquet('{OUT}/cand.parquet')")
    c.execute("create table bd(id varchar, day date, prev date, gap int, delta bigint, prev_all bigint)")
    load(*days[0]); c.execute("alter table cur rename to prv")
    pd_ = days[0][0]
    for d, f in days[1:]:
        load(d, f)
        gap = (d - pd_).days
        c.execute(f"""insert into bd select cur.id, DATE '{d}', DATE '{pd_}', {gap}, cur.dl_all-prv.dl_all, prv.dl_all
                      from cur join prv on cur.id=prv.id where cur.id in (select id from cand)""")
        c.execute("drop table prv"); c.execute("alter table cur rename to prv")
        pd_ = d
        if d.day == 1: print(d, round(time.time() - t0), flush=True)
    c.execute(f"copy bd to '{OUT}/big_deltas.parquet' (format parquet)")
    print("rows", c.execute("select count(*) from bd").fetchone())
print("done", round(time.time() - t0))
