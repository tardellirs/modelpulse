"""Retro 'Fastest growing' board (growth_7d) every 7th day since 2025-06 on the top-model subset (survivorship: models that are big today only, so
this UNDER-counts artifacts). Flags entries where one snapshot step holds >=50% of the 7-day downloads."""
from F_common import *
import datetime as dt
c = views(con(f"{WORK}/work.duckdb"))
c.execute("CREATE OR REPLACE TABLE inc AS SELECT id, day, dl_all, dl30, dl_all - lag(dl_all) OVER w d FROM s WHERE dl_all IS NOT NULL AND day NOT IN (SELECT day FROM skip) WINDOW w AS (PARTITION BY id ORDER BY day)")
days = [dt.date.fromisoformat(d) for d in META["days"]]; dayset = set(days); skip = {dt.date.fromisoformat(d) for d in SKIP}
def ref(r, D):
    for k in range(11):
        d = r - dt.timedelta(days=k)
        if d in dayset and (d not in skip or d == D): return d
res = []
for D in days[::7]:
    if D < dt.date(2025, 6, 1): continue
    r1, r2, r4 = ref(D-dt.timedelta(7), D), ref(D-dt.timedelta(14), D), ref(D-dt.timedelta(28), D)
    if not (r1 and r2 and r4): continue
    rows = c.execute(f"""
      WITH m AS (SELECT n.id, n.dl30, least(greatest(n.dl_all-a.dl_all,0), n.dl30) dl7, (a.dl_all-d4.dl_all)/3.0 base
        FROM s n JOIN s a ON a.id=n.id AND a.day=DATE '{r1}' JOIN s d4 ON d4.id=n.id AND d4.day=DATE '{r4}' WHERE n.day=DATE '{D}' AND n.dl_all IS NOT NULL),
      top AS (SELECT *, dl7/base-1 g FROM m WHERE base>=1000 AND dl30>=10000 ORDER BY g DESC LIMIT 100),
      mx AS (SELECT id, max(d) mxd FROM inc WHERE day>DATE '{r1}' AND day<=DATE '{D}' AND id IN (SELECT id FROM top) GROUP BY id)
      SELECT row_number() OVER (ORDER BY g DESC) rk, top.id, dl7, round(g,1) g, mxd*1.0/nullif(dl7,0) shr FROM top JOIN mx USING(id) ORDER BY g DESC""").fetchall()
    if not rows: continue
    f25 = sum(1 for r in rows[:25] if r[4] and r[4] >= .5); f100 = sum(1 for r in rows if r[4] and r[4] >= .5)
    res.append((str(D), (D-r1).days, f25, f100, rows[0][1], rows[0][2], rows[0][3], round(rows[0][4] or 0, 2)))
print("D len7 spike_in_top25 spike_in_top100 #1 dl7 growth share_one_step")
for r in res: print(*r)
import statistics
print("mean spike_in_top25:", statistics.mean(r[2] for r in res), "mean in top100:", statistics.mean(r[3] for r in res), "weeks", len(res))
print("weeks where #1 is >=80% one step:", sum(1 for r in res if r[7] >= .8))
