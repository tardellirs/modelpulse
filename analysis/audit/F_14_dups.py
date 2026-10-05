"""Duplicate (id, day) rows in series / family_series / author_series."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
show(c, "select count(*) dup_keys, sum(n-1) extra_rows from (select id, day, count(*) n from fam group by 1,2 having count(*)>1)")
show(c, "select count(*) dup_keys, sum(n-1) extra_rows from (select author, day, count(*) n from auth group by 1,2 having count(*)>1)")
show(c, "select id, day, count(*) n, min(dl30) mn, max(dl30) mx, min(members) m1, max(members) m2 from fam group by 1,2 having count(*)>1 order by n desc limit 10")
show(c, "select day, count(*) from (select id, day from fam group by 1,2 having count(*)>1) group by 1 order by 2 desc limit 10")
show(c, f"select count(*) dup_keys from (select id, day, count(*) n from read_parquet('{DATA}/series/2026-10.parquet') group by 1,2 having count(*)>1)")
show(c, f"select count(*) dup_keys from (select id, day, count(*) n from read_parquet('{DATA}/series/2026-09.parquet') group by 1,2 having count(*)>1)")
show(c, "select count(*) n_models_ids_dups from (select id from models group by 1 having count(*)>1)")
