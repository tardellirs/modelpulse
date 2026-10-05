"""Stale per-model rows: dl30 AND dl_all identical across >=35 days while dl30>0 (a 30-day window can't stay constant). Mass, who, and when they went stale."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute(f"""CREATE OR REPLACE TABLE stale AS
 SELECT a.id, a.dl30, a.dl_all, a.likes, m.author, m.pipeline_tag, m.dl_7d, m.rank_dl30, m.created_at, m.last_modified
 FROM read_parquet('{DATA}/series/2026-10.parquet') a
 JOIN (SELECT * FROM read_parquet('{DATA}/series/2026-08.parquet') UNION ALL BY NAME SELECT * FROM read_parquet('{DATA}/series/2026-09.parquet')) b
   ON a.id=b.id AND b.day=DATE '{LAST}'-35 AND b.dl30=a.dl30 AND b.dl_all IS NOT DISTINCT FROM a.dl_all
 JOIN models m ON m.id=a.id
 WHERE a.day=DATE '{LAST}' AND a.dl30>0""")
show(c,"select count(*) n, sum(dl30) dl30_sum, (select sum(dl30) from models) tot_dl30, round(sum(dl30)*1.0/(select sum(dl30) from models),5) shr from stale")
show(c,"select count(*) n_ge1000, sum(dl30) s from stale where dl30>=1000")
print('-- in current top-100 by rank_dl30 / dl30:')
show(c,"select id, dl30, dl_all, rank_dl30, last_modified from stale where rank_dl30<=20000 order by dl30 desc limit 25")
print('-- authors with most stale mass')
show(c,"select author, count(*) n, sum(dl30) s, (select sum(dl30) from models m where m.author=stale.author) auth_dl30 from stale group by 1 order by 3 desc limit 20")
