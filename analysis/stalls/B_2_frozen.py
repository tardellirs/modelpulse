"""Stage 2: big-model set and frozen share per snapshot interval / calendar day."""
import duckdb, polars as pl
W = "/work/stalls_B"
c = duckdb.connect(); c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
c.execute(f"create table bd as select * from read_parquet('{W}/big_deltas.parquet')")
print(c.sql("select count(*), count(distinct id) from bd"))
# big = median daily delta (delta/gap, clipped >=0) over all snapshot intervals >= 2000
c.execute("create table big as select id, median(greatest(delta,0)/gap) med, count(*) n from bd group by id having median(greatest(delta,0)/gap) >= 2000")
print(c.sql("select count(*) from big"))
c.execute("""create table fz as select b.day, b.prev, b.gap, count(*) n_big, sum((delta=0)::int) n_zero, sum((delta<0)::int) n_neg,
  avg((delta=0)::int) as "share", sum(greatest(delta,0))::double tot_big from bd b join big using(id) group by 1,2,3 order by 1""")
c.execute(f"copy fz to '{W}/frozen.parquet' (format parquet)")
c.execute(f"copy big to '{W}/big_ids.parquet' (format parquet)")
print(c.sql("select quantile_cont(\"share\",[0.05,0.25,0.5,0.75,0.95,0.99]), min(n_big), max(n_big) from fz"))
print(c.sql("select count(*) from fz where \"share\">0.35"))
