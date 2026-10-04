"""Per-day raw totals and frozen shares from per-repo dl_all (gap-aware). Usage: C_frozen.py models|datasets
Writes /work/stalls_C/C_<kind>_days.parquet. Runs in the modelpulse-api image with /data mounted read-only."""
import sys, glob, os, json, datetime as dt, time
import duckdb

kind = sys.argv[1]
SRC = "/data/series" if kind == "models" else "/data/datasets/series"
THR = [2000] if kind == "models" else [200, 1000, 2000]
START = dt.date(2025, 2, 27)
c = duckdb.connect()
c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'; SET preserve_insertion_order=false")
files = sorted(glob.glob(f"{SRC}/*.parquet"))
months = [os.path.basename(f)[:7] for f in files]
t0 = time.time()
c.execute("create table tot(day date, delta bigint, gap int, n_pairs bigint, n_ids bigint)")
c.execute("create table rows_c(id varchar, day date, delta bigint, gap int)")
lo = min(THR) * 0.5
prev_file = None
for f, m in zip(files, months):
    if m < "2025-02":
        prev_file = f; continue
    if prev_file:
        last = c.execute(f"select max(day) from '{prev_file}'").fetchone()[0]
        src = f"(select id, day, dl_all from '{f}' where dl_all is not null union all select id, day, dl_all from '{prev_file}' where day = DATE '{last}' and dl_all is not null)"
    else:
        src = f"(select id, day, dl_all from '{f}' where dl_all is not null)"
    c.execute(f"""create or replace temp table w as
      select id, day, dl_all, lag(dl_all) over (partition by id order by day) p, lag(day) over (partition by id order by day) pd from {src}""")
    # global previous snapshot day for each day in this month
    c.execute("create or replace temp table dd as select distinct day from w")
    c.execute("create or replace temp table dg as select day, lag(day) over (order by day) gd from dd")
    c.execute(f"""create or replace temp table v as
      select w.id, w.day, w.dl_all - w.p as delta, (w.day - dg.gd) as gap from w join dg using(day)
      where w.pd = dg.gd and w.p is not null and w.day >= DATE '{START}' and w.day >= DATE '{months[0]}-01'""")
    c.execute("insert into tot select day, sum(greatest(delta,0)), any_value(gap), count(*), count(*) from v group by day")
    c.execute(f"""insert into rows_c select id, day, delta, gap from v where id in
       (select id from v group by id having sum(greatest(delta,0))/count(*)/greatest(avg(gap),1) >= {lo})""")
    print(m, round(time.time() - t0), c.execute("select count(*) from rows_c").fetchone(), flush=True)
    prev_file = f
# per-id median daily rate over its whole history
c.execute("""create table idmed as select id, median(greatest(delta,0)/gap) med, count(*) n from rows_c group by id having count(*) >= 30""")
sel = ", ".join(
  f"""sum(case when r.gap=1 and m.med>={t} then 1 else 0 end) g1_n{t}, sum(case when r.gap=1 and m.med>={t} and r.delta=0 then 1 else 0 end) g1_f{t},
      sum(case when m.med>={t} then 1 else 0 end) ga_n{t}, sum(case when m.med>={t} and r.delta=0 then 1 else 0 end) ga_f{t}""" for t in THR)
c.execute(f"create table fz as select r.day, {sel} from rows_c r join idmed m using(id) group by r.day")
for t in THR:
    print("ids with median >=", t, c.execute(f"select count(*) from idmed where med>={t}").fetchone())
c.execute("create table out as select t.day, t.gap, t.delta as total_delta, t.n_pairs, fz.* exclude(day) from tot t left join fz using(day) order by t.day")
c.execute(f"copy out to '/work/stalls_C/C_{kind}_days.parquet' (format parquet)")
print(c.execute("select * from out order by day limit 3").fetchall(), time.time() - t0)
