"""Today's dl30 vs dl_all(last)-dl_all(last-30) across ALL tracked models; which kinds disagree."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute(f"""CREATE OR REPLACE TABLE lc AS
 SELECT a.id, a.dl30, a.dl_all, b.dl_all AS dl_all_30, a.dl_all-b.dl_all AS d30,
        m.pipeline_tag, m.author, m.created_at, m.dl_7d, m.library_name, m.is_gguf
 FROM read_parquet('{DATA}/series/2026-10.parquet') a
 JOIN read_parquet('{DATA}/series/2026-09.parquet') b ON a.id=b.id AND b.day=DATE '{LAST}'-30
 JOIN models m ON m.id=a.id WHERE a.day=DATE '{LAST}'""")
show(c,"select count(*) n, sum((dl30>=1000)::int) n1k, sum((dl30>=1000 and d30<0.5*dl30)::int) low_half, sum((dl30>=1000 and d30>1.5*dl30)::int) high_150, sum((dl30>=1000 and d30<0)::int) neg from lc")
print("-- by band of dl30")
show(c,"""select case when dl30>=1e7 then '>=10M' when dl30>=1e6 then '1-10M' when dl30>=1e5 then '100k-1M' when dl30>=1e4 then '10k-100k' else '1k-10k' end band, count(*) n,
  round(median(d30*1.0/dl30),3) med, round(avg((abs(d30*1.0/dl30-1)>0.25)::int),4) off25, round(avg((d30*1.0/dl30<0.75)::int),4) under75, round(avg((d30*1.0/dl30>1.25)::int),4) over125
  from lc where dl30>=1000 and dl_all_30 is not null group by 1 order by 1""")
print("-- by is_gguf / library")
show(c,"""select is_gguf, count(*) n, round(median(d30*1.0/dl30),3) med, round(avg((abs(d30*1.0/dl30-1)>0.25)::int),4) off25 from lc where dl30>=1000 group by 1""")
print("-- by created in last 45d")
show(c,f"""select (created_at > TIMESTAMP '{LAST}' - INTERVAL 45 DAY) is_new, count(*) n, round(median(d30*1.0/dl30),3) med, round(avg((abs(d30*1.0/dl30-1)>0.25)::int),4) off25 from lc where dl30>=1000 group by 1""")
print("-- worst over (d30 >> dl30) top by abs diff")
show(c,"select id, dl30, d30, round(d30*1.0/dl30,2) r, created_at from lc where dl30>=1000 order by d30-dl30 desc limit 15")
print("-- worst under (d30 << dl30)")
show(c,"select id, dl30, d30, round(d30*1.0/dl30,2) r, dl_all, dl_all_30, created_at from lc where dl30>=1000 order by dl30-d30 desc limit 25")
