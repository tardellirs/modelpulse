"""Recompute the model leaderboard inputs (dl_7d, dl_prev7d, dl_base7d, growth_7d) as build.derived() would have, for every historical day D,
on the top-model subset, to see: (a) how long the '7-day' window really is after skip windows, (b) growth bias, (c) spikes in the top boards.
Uses today's skip_days (best case: the daily job only knew earlier skip lists)."""
from F_common import *
import datetime as dt, csv
c = views(con(f"{WORK}/work.duckdb"))
c.execute("CREATE OR REPLACE TABLE sk AS SELECT id, day, dl_all, dl30 FROM s WHERE dl_all IS NOT NULL")
days = [dt.date.fromisoformat(d) for d in META["days"]]
skip = {dt.date.fromisoformat(d) for d in SKIP}
dayset = set(days)
def ref_day(r, D):
    for k in range(0, 11):
        d = r - dt.timedelta(days=k)
        if d in dayset and (d not in skip or d == D): return d
    return None
out = []
for D in days:
    if D < dt.date(2025, 4, 5): continue
    r1, r2, r4 = ref_day(D - dt.timedelta(7), D), ref_day(D - dt.timedelta(14), D), ref_day(D - dt.timedelta(28), D)
    if not (r1 and r2 and r4): continue
    c.execute(f"""CREATE OR REPLACE TEMP TABLE m AS
      SELECT n.id, n.dl30, n.dl_all - a.dl_all raw7, a.dl_all - b.dl_all prev7, (a.dl_all - d4.dl_all)/3.0 base7
      FROM sk n JOIN sk a ON a.id=n.id AND a.day=DATE '{r1}' JOIN sk b ON b.id=n.id AND b.day=DATE '{r2}' JOIN sk d4 ON d4.id=n.id AND d4.day=DATE '{r4}'
      WHERE n.day=DATE '{D}'""")
    row = c.execute("""SELECT count(*),
        median(CASE WHEN base7>=1000 AND dl30>=10000 THEN least(greatest(raw7,0),dl30)/base7-1 END),
        avg(CASE WHEN base7>=1000 AND dl30>=10000 THEN ((least(greatest(raw7,0),dl30)/base7-1)>0.3)::int END),
        avg(CASE WHEN base7>=1000 AND dl30>=10000 THEN ((least(greatest(raw7,0),dl30)/base7-1)<-0.3)::int END)
        FROM m""").fetchone()
    out.append((str(D), (D - r1).days, (D - r2).days - (D - r1).days, (D - r4).days, *row))
with open(f"{WORK}/F_hist_windows.csv", "w") as f:
    w = csv.writer(f); w.writerow(["D", "len7", "len_prev7", "len28", "n", "med_growth", "frac_gt30", "frac_lt-30"]); w.writerows(out)
import collections
print("days", len(out), "len7>7:", sum(1 for o in out if o[1] > 7), " len7>=9:", sum(1 for o in out if o[1] >= 9), " prev7!=7:", sum(1 for o in out if o[2] != 7), " len28 !=28:", sum(1 for o in out if o[3] != 28))
bad = [o for o in out if o[1] != 7 or o[2] != 7 or o[3] != 28]
print("distinct D with any non-standard window:", len(bad))
print("D len7 lenprev len28 med_growth frac>30 frac<-30")
for o in out:
    if o[1] != 7 or o[2] != 7 or o[3] != 28 or abs(o[5]) > 0.08: print(o)
