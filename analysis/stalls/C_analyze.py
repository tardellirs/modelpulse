"""Combine C_models_days.parquet / C_datasets_days.parquet (from C_frozen.py) with C_snapshots.csv (C_timing.py).
Prints the tables used in C_datasets_timing.md. Run locally with space/.venv python."""
import json, datetime as dt
import numpy as np, polars as pl
from scipy import stats

H = [dt.date.fromisoformat(s) for s in "2025-07-16 2025-08-13 2025-10-01 2025-10-08 2025-11-26 2026-02-11 2026-04-29 2026-06-25 2026-07-29 2026-08-01 2026-08-05 2026-08-12".split()]

def side(kind):
    d = pl.read_parquet(f"C_{kind}_days.parquet").sort("day")
    # spread each snapshot's delta evenly over the calendar days it covers (as build.hub_series does), then 15-day centred median
    rows = []
    for r in d.iter_rows(named=True):
        for k in range(r["gap"]):
            rows.append((r["day"] - dt.timedelta(days=k), r["total_delta"] / r["gap"]))
    cal = pl.DataFrame(rows, schema=["day", "tot"], orient="row").sort("day")
    cal = cal.with_columns(pl.col("tot").rolling_median(15, center=True, min_samples=5).alias("med")).with_columns((pl.col("tot") / pl.col("med")).alias("ratio"))
    return d.join(cal, on="day", how="left")

M, D = side("models"), side("datasets")
snap = pl.read_csv("C_snapshots.csv", try_parse_dates=True).select("day", "models_ts", "datasets_ts", "models_int_h", "datasets_int_h", "ds_minus_models_min", "models_ncommits", "datasets_ncommits")
def sh(df, t, k="g1"): return (pl.col(f"{k}_f{t}") / pl.col(f"{k}_n{t}")).alias(f"fz{t}")
m = M.select("day", "gap", pl.col("ratio").alias("m_ratio"), sh(M, 2000).alias("m_fz2000"), pl.col("g1_n2000").alias("m_n"))
d = D.select("day", pl.col("ratio").alias("d_ratio"), sh(D, 200).alias("d_fz200"), sh(D, 1000).alias("d_fz1000"), sh(D, 2000).alias("d_fz2000"), pl.col("g1_n200").alias("d_n200"), pl.col("g1_n1000").alias("d_n1000"))
T = m.join(d, on="day", how="full", coalesce=True).join(snap, on="day", how="left").sort("day")
T.write_csv("C_daily_table.csv")
print("rows", T.height, T["day"].min(), T["day"].max())

pd = T.to_pandas()
def corr(a, b, sub):
    s = pd[sub].dropna(subset=[a, b]); 
    return len(s), stats.pearsonr(s[a], s[b])[0], stats.spearmanr(s[a], s[b])[0]
ok = (pd.gap == 1)
print("\n== ratio vs frozen share (g==1 days), Pearson/Spearman")
for r, f in [("m_ratio", "m_fz2000"), ("d_ratio", "d_fz200"), ("d_ratio", "d_fz1000"), ("d_ratio", "d_fz2000")]:
    print(r, f, corr(r, f, ok))
print("\n== model vs dataset, same day")
for a, b in [("m_ratio", "d_ratio"), ("m_fz2000", "d_fz2000"), ("m_fz2000", "d_fz1000"), ("m_fz2000", "d_fz200")]:
    print(a, b, corr(a, b, ok))
print("\n== depth comparison: days below thresholds")
for thr in (0.3, 0.5, 0.7):
    mm, dd = ok & (pd.m_ratio < thr), ok & (pd.d_ratio < thr)
    print(f"ratio<{thr}: models {mm.sum()}, datasets {dd.sum()}, both {(mm & dd).sum()}, models only {(mm & ~dd).sum()}, datasets only {(dd & ~mm).sum()}")
for thr in (0.3, 0.5):
    mm, dd = ok & (pd.m_fz2000 > thr), ok & (pd.d_fz1000 > thr)
    print(f"frozen>{thr}: models(2000) {mm.sum()}, datasets(1000) {dd.sum()}, both {(mm & dd).sum()}")
print("median frozen share on normal days (ratio>0.9 both):",
      pd[ok & (pd.m_ratio > .9) & (pd.d_ratio > .9)][["m_fz2000", "d_fz200", "d_fz1000", "d_fz2000"]].median().round(4).to_dict())

# interval vs dip
print("\n== interval vs ratio (days with calendar gap 1 and commit interval available)")
for nm, r, iv in [("models", "m_ratio", "models_int_h"), ("datasets", "d_ratio", "datasets_int_h")]:
    s = pd[ok].dropna(subset=[r, iv])
    print(nm, "n", len(s), "pearson", round(stats.pearsonr(s[iv], s[r])[0], 3), "spearman", round(stats.spearmanr(s[iv], s[r])[0], 3))
    s2 = s[(s[iv] > 20) & (s[iv] < 28)]
    print(nm, "restricted to 20-28h:", len(s2), "pearson", round(stats.pearsonr(s2[iv], s2[r])[0], 3), "spearman", round(stats.spearmanr(s2[iv], s2[r])[0], 3))
    s["b"] = pd_cut = np.select([s[iv] < 22, s[iv] < 23.9, s[iv] <= 24.1, s[iv] <= 30, s[iv] > 30], ["<22h", "22-23.9h", "24.0h(+-0.1)", "24.1-30h", ">30h"], "?")
    print(s.groupby("b")[r].agg(["count", "mean", "median", "min", "max"]).round(3).to_string())
    print("share of days with ratio<0.7 by bucket:", s.groupby("b")[r].apply(lambda x: round((x < .7).mean(), 3)).to_dict())
    # rate normalised by interval
    s["rn"] = s[r] / (s[iv] / 24)
    print("  normalised-by-interval ratio: pearson with interval", round(stats.pearsonr(s[iv], s["rn"])[0], 3))
    low = s[s[r] < 0.7]
    print("  low days (<0.7) interval stats:", low[iv].describe().round(3).to_dict())

# all days with any dip
flag = ok & ((pd.m_ratio < 0.7) | (pd.d_ratio < 0.7) | (pd.m_fz2000 > .3) | (pd.d_fz1000 > .3))
cols = ["day", "m_ratio", "d_ratio", "m_fz2000", "d_fz200", "d_fz1000", "d_fz2000", "models_int_h", "datasets_int_h", "ds_minus_models_min"]
import pandas as p
p.set_option("display.width", 250); p.set_option("display.max_rows", 500)
print("\n== all g==1 days with ratio<0.7 or frozen>0.3 on either side:", flag.sum())
print(pd[flag][cols].round(3).to_string(index=False))
print("\n== the 12 half-stall days")
print(pd[pd.day.isin(H)][cols + ["gap"]].round(3).to_string(index=False))
print("\n== days with gap>1 (missing snapshots), ratios")
print(pd[~ok][["day", "gap", "m_ratio", "d_ratio", "models_int_h"]].round(3).to_string(index=False))
# dataset skip_days
