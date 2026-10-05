"""Duplicate ids in models.parquet and duplicate (id,day) in the newest series file only (small reads, 1 file each)."""
from F_common import *
c = con(mem="1GB"); c.execute("SET threads=1")
show(c, f"select id, count(*) n, min(dl30) a, max(dl30) b, min(dl_all) lo, max(dl_all) hi from read_parquet('{DATA}/models.parquet') group by 1 having count(*)>1 order by 2 desc")
show(c, f"select id, day, count(*) n, min(dl30) a, max(dl30) b, min(dl_all) lo, max(dl_all) hi from read_parquet('{DATA}/series/2026-10.parquet') group by 1,2 having count(*)>1 order by 3 desc limit 8")
