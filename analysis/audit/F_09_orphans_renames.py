"""Series ids that no longer exist in models.parquet (deleted / renamed / made private) and rename pairs (old id's last counters == new id's first counters)."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb", mem="6GB"))
import os
if not os.path.exists(f"{WORK}/idagg.done"):
    c.execute("""CREATE OR REPLACE TABLE idagg AS
      SELECT id, min(day) first_day, max(day) last_day, count(*) n, max(dl_all) max_all, max(dl30) max_30,
             arg_max(dl_all, day) last_all, arg_max(dl30, day) last_30, arg_min(dl_all, day) FILTER (WHERE dl_all IS NOT NULL) first_all
      FROM series GROUP BY id""")
    open(f"{WORK}/idagg.done", "w").write("1")
c.execute("CREATE OR REPLACE TEMP VIEW orph AS SELECT a.* FROM idagg a ANTI JOIN models m ON m.id=a.id")
show(c, f"select count(*) n_orph, sum((max_30>=1000)::int) n_30_ge1k, sum((max_all>=100000)::int) all_ge100k, sum(max_30) peak30_sum from orph")
print("-- last_day distribution of orphans with max_30>=1000 (month)")
show(c, "select strftime(last_day,'%Y-%m') m, count(*) n from orph where max_30>=1000 group by 1 order by 1", 40)
print("-- biggest orphans")
show(c, "select id, first_day, last_day, max_30, max_all, last_all from orph order by max_30 desc limit 25")
print("-- rename candidates: orphan (last_day L, last_all A>=20000) vs current model with first_day in [L-1,L+3] and first_all within 3% of A")
show(c, f"""select count(*) n_pairs from (select o.id oid, m.id nid from orph o join idagg m on m.first_day between o.last_day-1 and o.last_day+3
   and m.first_all between o.last_all*0.97 and o.last_all*1.03 and m.id<>o.id join models mm on mm.id=m.id where o.last_all>=20000 and o.last_day < DATE '{LAST}')""")
show(c, f"""select o.id old_id, o.last_day, o.last_all, m.id new_id, m.first_day, m.first_all from orph o join idagg m on m.first_day between o.last_day-1 and o.last_day+3
   and m.first_all between o.last_all*0.97 and o.last_all*1.03 and m.id<>o.id join models mm on mm.id=m.id where o.last_all>=20000 and o.last_day < DATE '{LAST}' order by o.last_all desc limit 25""")
