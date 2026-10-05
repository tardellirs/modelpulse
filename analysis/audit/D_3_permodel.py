"""D stage 3 (server): per model and quarter, sum of positive dl_all deltas between consecutive snapshots (same
interval logic as hub_series, raw/unsmoothed, all snapshot pairs), plus first/last snapshot day and whether in latest snapshot.
Also per-day per-model delta for chosen spike days -> spike_models.parquet (id, day, delta, p_med: the model's median
positive daily rate over the previous 14 snapshots is NOT computed; instead we store delta of D-1, D, D+1 neighbours).
"""
import duckdb, glob, os, time, datetime as dt, sys
OUT="/a/out"
c=duckdb.connect(); c.execute("SET memory_limit='3000MB'; SET threads=3; SET temp_directory='/a/tmp'")
files=sorted(glob.glob("/d/series/*.parquet")); t0=time.time()
days=[]
for f in files:
    for (d,) in c.execute(f"select distinct day from read_parquet('{f}') where dl_all is not null order by 1").fetchall(): days.append((d,f))
days.sort()
SPIKE=[dt.date.fromisoformat(x) for x in sys.argv[1:]]
need=set()
for s in SPIKE:
    for k in (-2,-1,0,1,2): need.add(s+dt.timedelta(days=k))
c.execute("create table q(id varchar, q varchar, pos bigint, neg bigint)")
c.execute("create table life(id varchar, first date, last date)")
c.execute("create table sp(id varchar, day date, delta bigint, gap int)")
def load(d,f):
    c.execute("drop table if exists cur"); c.execute(f"create table cur as select id, dl_all from read_parquet('{f}') where day=DATE '{d}' and dl_all is not null")
load(*days[0]); c.execute("alter table cur rename to prv"); pd_=days[0][0]
for d,f in days[1:]:
    load(d,f); gap=(d-pd_).days; qq=f"{d.year}Q{(d.month-1)//3+1}"
    c.execute(f"insert into q select cur.id,'{qq}',sum(greatest(cur.dl_all-prv.dl_all,0)),sum(least(cur.dl_all-prv.dl_all,0)) from cur join prv using(id) group by 1")
    if d in need:
        c.execute(f"insert into sp select cur.id, DATE '{d}', cur.dl_all-prv.dl_all, {gap} from cur join prv using(id) where abs(cur.dl_all-prv.dl_all)>=500 or cur.id in (select id from prv order by dl_all desc limit 0)")
    c.execute("drop table prv"); c.execute("alter table cur rename to prv"); pd_=d
    if d.day==1:
        c.execute("create or replace table q2 as select id,q,sum(pos) pos,sum(neg) neg from q group by 1,2"); c.execute("drop table q"); c.execute("alter table q2 rename to q")
        print(d,round(time.time()-t0),flush=True)
c.execute(f"copy (select id,q,sum(pos) pos,sum(neg) neg from q group by 1,2) to '{OUT}/model_quarter.parquet' (format parquet)")
c.execute(f"copy sp to '{OUT}/spike_models.parquet' (format parquet)")
# lifetime
c.execute(f"""copy (select id, min(day) first, max(day) last from read_parquet('/d/series/*.parquet') where dl_all is not null group by id) to '{OUT}/life.parquet' (format parquet)""")
print("done",round(time.time()-t0))
