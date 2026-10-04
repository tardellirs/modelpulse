"""Stage 7: pair-threshold sensitivity, negative-delta (counter rollback) diagnostics for 2025-05-21, episode totals for catch-up beyond the window."""
import datetime as dt, duckdb, polars as pl
from B_common import *
pl.Config.set_tbl_rows(60); pl.Config.set_tbl_width_chars(200)
D = dt.date
raw = raw_hub(); t = totals(raw); days = t["day"].to_list(); r = t["r"].to_list(); tot = t["tot"].to_list(); med = t["med"].to_list(); ix = {d: i for i, d in enumerate(days)}
fz = pl.read_parquet(f"{W}/frozen.parquet"); share = {}
for row in fz.iter_rows(named=True):
    for k in range(row["gap"]): share[row["day"] - dt.timedelta(days=k)] = row["share"]
fzset = {d for d in days if share.get(d, 0) > .35}
cur = {d for d in days if r[ix[d]] < .3}
print("== pair sensitivity: (lo, hi, sum band) -> n pairs, of which not frozen>0.35 / not r<0.3, list of the non-frozen ones")
for lo in (0.6, 0.7, 0.8, 0.85):
    for hi in (1.2, 1.3, 1.4):
        for band in ((1.6, 2.4), (1.8, 2.2)):
            p = pair_pairs(days, r, lo=lo, hi=hi, s_lo=band[0], s_hi=band[1])
            nf = [(str(a), a.strftime("%a"), round(r[ix[a]], 2)) for a, b in p if a not in fzset and a not in cur]
            print(lo, hi, band, len(p), len(nf), nf)
# weekday-adjusted: how many Wednesdays naturally have r<0.85 and neighbor >1.15?
print("\n== negative delta share among big models, top days")
fz2 = fz.with_columns((pl.col("n_neg") / pl.col("n_big")).alias("neg_share")).sort("neg_share", descending=True)
print(fz2.select("day", "gap", "n_big", "n_zero", "n_neg", "neg_share").head(12))
print(fz2.filter((pl.col("day") >= D(2025, 5, 14)) & (pl.col("day") <= D(2025, 5, 26))).sort("day").select("day", "n_big", "n_zero", "n_neg", "neg_share", "tot_big"))
# all-model positive/negative mass day by day around 2025-05-21
c = duckdb.connect(); c.execute("SET memory_limit='2000MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
def mass(f, d0, d1):
    c.execute(f"create or replace table a as select id, day, dl_all from read_parquet('{f}') where day between DATE '{d0}' and DATE '{d1}' and dl_all is not null")
    print(c.sql("""select day, sum(greatest(d,0))::double/1e6 pos_M, sum(least(d,0))::double/1e6 neg_M, sum((d<0)::int) n_neg, count(*) n,
      sum((d<0)::int)::double/count(*) share_neg from (select id, day, dl_all - lag(dl_all) over (partition by id order by day) d from a) where d is not null group by 1 order by 1"""))
print("\n== all models, 2025-05 (pos delta mass, neg delta mass, count of decreasing counters)"); mass("/data/series/2025-05.parquet", "2025-05-15", "2025-05-26")
print("\n== all models, 2026-06"); mass("/data/series/2026-06.parquet", "2026-06-11", "2026-06-22")
# episode totals incl. later catch-up
def ep(a, b):
    ii = [ix[d] for d in days if a <= d <= b]
    return round(sum(tot[i] for i in ii) / sum(med[i] for i in ii), 3), len(ii)
print("\nepisode total / sum of medians:", {k: ep(D.fromisoformat(a), D.fromisoformat(b)) for k, (a, b) in {"2026-06-12..06-19": ("2026-06-12", "2026-06-19"), "2026-06-12..06-14": ("2026-06-12", "2026-06-14"), "2026-06-15..06-19": ("2026-06-15", "2026-06-19"), "2025-05-19..05-23": ("2025-05-19", "2025-05-23"), "2025-05-03..05-08": ("2025-05-03", "2025-05-08"), "2026-06-24..25": ("2026-06-24", "2026-06-25"), "2026-07-31..08-02": ("2026-07-31", "2026-08-02"), "2026-08-12..08-17": ("2026-08-12", "2026-08-17")}.items()})
print("raw r series 2026-06-08..06-26:", [(str(d)[5:], round(r[ix[d]], 2)) for d in days if D(2026, 6, 8) <= d <= D(2026, 6, 26)])
print("raw r series 2025-05-15..05-27:", [(str(d)[5:], round(r[ix[d]], 2)) for d in days if D(2025, 5, 15) <= d <= D(2025, 5, 27)])
print("raw r series 2026-07-26..08-17:", [(str(d)[5:], d.strftime('%a')[:2], round(r[ix[d]], 2), round(share.get(d, 0), 2)) for d in days if D(2026, 7, 26) <= d <= D(2026, 8, 17)])
