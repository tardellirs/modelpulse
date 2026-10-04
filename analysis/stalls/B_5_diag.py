"""Stage 5 diagnostics: snapshot gaps / models joined per day, per-model ratio distribution on pair-only days vs frozen half-stalls, dl30 test for hub-wide spikes."""
import datetime as dt, glob, json, statistics as S
import duckdb, polars as pl
from B_common import *
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(220)
D = dt.date
snap = pl.read_parquet(f"{W}/hub_raw_snap.parquet").group_by("day", "prev", "gap").agg(pl.col("dsum").sum().alias("tot"), pl.col("n").sum().alias("n")).sort("day")
print("snapshot intervals with gap>1:"); print(snap.filter(pl.col("gap") > 1).select("prev", "day", "gap", "n"))
nm = snap["n"].median(); print("median models joined", nm)
print("days where n_models < 0.97*median or > 1.03 :"); print(snap.filter((pl.col("n") < 0.97 * nm) | (pl.col("n") > 1.03 * nm)).select("day", "gap", "n"))
# n_joined around candidate days
cands = "2025-05-03 2025-05-04 2025-05-21 2026-04-01 2026-06-12 2026-06-13 2026-06-18 2026-06-25 2026-08-01 2025-10-08".split()
nn = {r["day"]: r["n"] for r in snap.iter_rows(named=True)}
for c_ in cands:
    d = D.fromisoformat(c_); print(c_, [nn.get(d + dt.timedelta(days=k)) for k in (-2, -1, 0, 1, 2)])
# per-model ratio distribution
big = pl.read_parquet(f"{W}/big_ids.parquet").select("id")
bb = pl.read_parquet(f"{W}/big_deltas.parquet").join(big, on="id", how="semi").with_columns((pl.col("delta").clip(lower_bound=0) / pl.col("gap")).alias("v"))
raw = raw_hub(); t = totals(raw); days = t["day"].to_list(); r = t["r"].to_list(); ix = {d: i for i, d in enumerate(days)}
bad = {d for d in days if r[ix[d]] < 0.7 or r[ix[d]] > 1.3}
badr = {x["day"] for x in bb.select("day").unique().iter_rows(named=True) if x["day"] in bad}
def ratios(d):
    base = bb.filter((pl.col("day") >= d - dt.timedelta(days=28)) & (pl.col("day") <= d + dt.timedelta(days=28)) & ~pl.col("day").is_in(list(bad)) & (pl.col("gap") == 1)).group_by("id").agg(pl.col("v").median().alias("b"))
    x = bb.filter((pl.col("day") == d)).join(base, on="id").filter(pl.col("b") > 50000).with_columns((pl.col("v") / pl.col("b")).alias("q"))
    return x["q"].to_list()
def qs(v, ps=(.05, .1, .25, .5, .75, .9, .95)):
    v = sorted(v); return [round(v[min(len(v) - 1, int(p * len(v)))], 2) for p in ps]
print("\nper-model ratio act/base (big models with base>50k/day): n, share<0.05, share in [.05,.5), share>2, quantiles 5/10/25/50/75/90/95%")
for s in "2026-06-23 2026-06-24 2026-06-25 2026-06-26 2026-07-31 2026-08-01 2026-08-02 2025-07-16 2025-10-08 2026-02-11 2026-04-29 2026-07-29 2026-08-05 2026-06-13 2026-04-01 2025-05-04 2026-06-10".split():
    q = ratios(D.fromisoformat(s))
    if not q: print(s, "no data"); continue
    print(s, D.fromisoformat(s).strftime("%a"), "hub r", round(r[ix[D.fromisoformat(s)]], 2), len(q), round(sum(1 for x in q if x < .05) / len(q), 2), round(sum(1 for x in q if .05 <= x < .5) / len(q), 2), round(sum(1 for x in q if x > 2) / len(q), 2), qs(q))
# dl30 hub total
c = duckdb.connect(); c.execute("SET memory_limit='2000MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
for mon, lo, hi in [("2025-05", "2025-05-12", "2025-05-31"), ("2025-06", "2025-06-01", "2025-06-30"), ("2026-06", "2026-06-10", "2026-06-30"), ("2026-07", "2026-07-10", "2026-07-25")]:
    print(mon); print(c.sql(f"select day, sum(dl30)::double/1e9 dl30_total_B, sum(dl_all)::double/1e12 all_T, count(*) n from read_parquet('/data/series/{mon}.parquet') where day between DATE '{lo}' and DATE '{hi}' group by 1 order by 1"))
