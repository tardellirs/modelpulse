"""D stage 1 (run on the server, read-only on /d): per snapshot day hub-level statistics from per-model series.
  docker run --rm --memory 4g -v /opt/modelpulse/data:/d:ro -v /root/audit:/a --entrypoint python modelpulse-api /a/D_1_daystats.py
Writes /a/out/day_stats.csv, /a/out/top_deltas.parquet (top 300 positive deltas per day), /a/out/new_top.parquet.
"""
import duckdb, glob, os, time
OUT = "/a/out"; os.makedirs(OUT, exist_ok=True)
c = duckdb.connect()
c.execute("SET memory_limit='3000MB'; SET threads=3; SET temp_directory='/a/tmp'")
files = sorted(glob.glob("/d/series/*.parquet"))
t0 = time.time()
days = []
for f in files:
    for (d,) in c.execute(f"select distinct day from read_parquet('{f}') order by 1").fetchall():
        days.append((d, f))
days.sort()
print("days", len(days), days[0][0], days[-1][0], flush=True)
c.execute("create table cur_models as select id, pipeline_tag is null as notag from read_parquet('/d/models.parquet')")
c.execute("create table stats(day date, prev date, gap int, n_cur bigint, n_prev bigint, n_new bigint, n_gone bigint, "
          "dl30_sum double, dlall_sum double, dlall_null bigint, pos double, neg double, n_up bigint, n_down bigint, n_zero bigint, "
          "pos_deleted double, neg_deleted double, new_all double, gone_all double, top1 double, top10 double, top100 double, top1000 double, top1_id varchar, "
          "n_ge1k bigint, sum_ge1k double, n_big_zero bigint, n_big bigint)")
c.execute("create table topd(day date, id varchar, delta bigint, dl_all bigint)")
c.execute("create table newtop(day date, id varchar, dl_all bigint, dl30 bigint)")
c.execute("create table gonetop(day date, id varchar, dl_all bigint)")
prv = None; pd_ = None
def load(d, f):
    c.execute("drop table if exists cur")
    c.execute(f"create table cur as select id, dl_all, dl30 from read_parquet('{f}') where day=DATE '{d}'")
for d, f in days:
    load(d, f)
    if prv is None:
        c.execute(f"insert into stats(day,n_cur,dl30_sum,dlall_sum,dlall_null) select DATE '{d}',count(*),sum(dl30),sum(dl_all),count(*) filter (where dl_all is null) from cur")
        c.execute("alter table cur rename to prv"); pd_ = d; prv = 1; continue
    gap = (d - pd_).days
    c.execute("create or replace table j as select cur.id, cur.dl_all - prv.dl_all as dd, cur.dl_all, cur.dl30, prv.dl30 p30, prv.dl_all pall, (m.id is null) as deleted from cur join prv using(id) left join cur_models m on m.id=cur.id where cur.dl_all is not null and prv.dl_all is not null")
    c.execute(f"""insert into stats
      select DATE '{d}', DATE '{pd_}', {gap},
        (select count(*) from cur), (select count(*) from prv),
        (select count(*) from cur where id not in (select id from prv)),
        (select count(*) from prv where id not in (select id from cur)),
        (select sum(dl30) from cur), (select sum(dl_all) from cur), (select count(*) from cur where dl_all is null),
        sum(greatest(dd,0)), sum(least(dd,0)), count(*) filter (where dd>0), count(*) filter (where dd<0), count(*) filter (where dd=0),
        sum(greatest(dd,0)) filter (where deleted), sum(least(dd,0)) filter (where deleted),
        (select sum(dl_all) from cur where id not in (select id from prv)),
        (select sum(dl_all) from prv where id not in (select id from cur)),
        (select sum(x) from (select greatest(dd,0) x from j order by x desc limit 1)),
        (select sum(x) from (select greatest(dd,0) x from j order by x desc limit 10)),
        (select sum(x) from (select greatest(dd,0) x from j order by x desc limit 100)),
        (select sum(x) from (select greatest(dd,0) x from j order by x desc limit 1000)),
        (select id from j order by dd desc limit 1),
        count(*) filter (where dd>=1000), sum(greatest(dd,0)) filter (where dd>=1000),
        count(*) filter (where p30>=60000 and dd=0), count(*) filter (where p30>=60000)
      from j""")
    c.execute(f"insert into topd select DATE '{d}', id, dd, dl_all from j order by dd desc limit 300")
    c.execute(f"insert into newtop select DATE '{d}', id, dl_all, dl30 from cur where id not in (select id from prv) order by dl_all desc nulls last limit 15")
    c.execute(f"insert into gonetop select DATE '{d}', id, dl_all from prv where id not in (select id from cur) order by dl_all desc nulls last limit 15")
    c.execute("drop table prv"); c.execute("alter table cur rename to prv"); pd_ = d
    if d.day == 1: print(d, round(time.time()-t0), flush=True)
for t in ("stats", "topd", "newtop", "gonetop"):
    c.execute(f"copy {t} to '{OUT}/{t}.parquet' (format parquet)")
print("done", round(time.time()-t0))
