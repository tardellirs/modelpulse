"""Biggest families board: nested/overlapping families, and consistency family_series vs models.fam_*"""
from F_common import *
import json
c = views(con(f"{WORK}/work.duckdb"))
lb = json.load(open(f"{DATA}/leaderboards.json"))
fam = [r["id"] for r in lb["families"]]
c.execute("CREATE OR REPLACE TEMP TABLE fb(id VARCHAR, rk INT)")
c.executemany("INSERT INTO fb VALUES (?,?)", [(i, k + 1) for k, i in enumerate(fam)])
# ancestors of each board entry by walking base_ids up to 6 levels
c.execute("""CREATE OR REPLACE TEMP TABLE anc AS WITH RECURSIVE up(member, a, lvl) AS (
   SELECT id, unnest(base_ids), 1 FROM models WHERE id IN (SELECT id FROM fb) AND base_ids IS NOT NULL
   UNION ALL SELECT up.member, unnest(m.base_ids), lvl+1 FROM up JOIN models m ON m.id=up.a WHERE lvl<6 AND m.base_ids IS NOT NULL)
   SELECT DISTINCT member, a FROM up""")
show(c, """select f.rk, f.id, (select list(a.a) from anc a where a.member=f.id and a.a in (select id from fb)) ancestors_also_on_board, m.fam_dl30, m.dl30, m.fam_members
   from fb f join models m using(id) order by rk limit 30""", 30)
print("entries in top100 that descend from another top100 entry:", c.execute("select count(distinct member) from anc where a in (select id from fb)").fetchone())
print("-- family_series (last day) vs models.fam_*")
show(c, f"""select count(*) n, sum((abs(f.dl30 - m.fam_dl30) > 0.001*m.fam_dl30)::int) dl30_mismatch, sum((abs(f.dl_all - m.fam_all) > 0.001*m.fam_all)::int) all_mismatch
   from fam f join models m using(id) where f.day=DATE '{LAST}' and m.fam_members>=3""")
show(c, f"""select f.id, f.dl30, m.fam_dl30, f.dl_all, m.fam_all, f.members, m.fam_members+1 from fam f join models m using(id) where f.day=DATE '{LAST}' and (abs(f.dl30-m.fam_dl30)>0.001*m.fam_dl30 or abs(f.dl_all-m.fam_all)>0.001*m.fam_all) order by f.dl30 desc limit 15""")
print("-- author_series last day vs models")
show(c, f"""with am as (select author, sum(dl30) d30, sum(dl_all) a, count(*) n from models group by 1)
 select count(*) n, sum((abs(s.dl30-am.d30)>0.001*am.d30)::int) d30_mismatch, sum((abs(s.dl_all-am.a)>0.001*am.a)::int) all_mismatch, sum((s.models<>am.n)::int) members_mismatch
 from auth s join am using(author) where s.day=DATE '{LAST}'""")
show(c, f"""with am as (select author, sum(dl30) d30, sum(dl_all) a, count(*) n from models group by 1)
 select s.author, s.dl30, am.d30, s.dl_all, am.a, s.models, am.n from auth s join am using(author) where s.day=DATE '{LAST}' and (abs(s.dl30-am.d30)>0.001*am.d30 or s.models<>am.n) order by am.d30 desc limit 10""")
