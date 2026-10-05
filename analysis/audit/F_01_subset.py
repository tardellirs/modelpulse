"""Materialise a compact working subset: all series rows for models in the current top ~60k by dl30 or dl_all (covers what rankings show)."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute("""CREATE OR REPLACE TABLE top AS
  SELECT id FROM (SELECT id FROM models ORDER BY dl30 DESC NULLS LAST LIMIT 40000)
  UNION SELECT id FROM (SELECT id FROM models ORDER BY dl_all DESC NULLS LAST LIMIT 20000)
  UNION SELECT id FROM (SELECT id FROM models ORDER BY dl_7d DESC NULLS LAST LIMIT 5000)""")
c.execute("CREATE OR REPLACE TABLE s AS SELECT s.id, s.day, s.dl30, s.dl_all, s.likes FROM series s SEMI JOIN top USING(id) ORDER BY id, day")
print(c.sql("select count(*), count(distinct id) from s"))
