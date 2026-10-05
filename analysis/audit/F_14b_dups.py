from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
show(c, "select id, count(*) n, min(dl30) a, max(dl30) b, min(dl_all) c, max(dl_all) d, any_value(author) from models group by 1 having count(*)>1 order by 2 desc")
show(c, f"select id, day, count(*) n, min(dl30), max(dl30), min(dl_all), max(dl_all) from read_parquet('{DATA}/series/2026-10.parquet') group by 1,2 having count(*)>1 order by 3 desc limit 8")
show(c, f"select strftime(day,'%Y-%m') m, count(*) from (select id, day from series group by 1,2 having count(*)>1) group by 1 order by 1")
