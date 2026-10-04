"""Does the minute-level upload time (relative to its 15-day rolling median) or the models->datasets spacing relate to stalls?"""
import pandas as pd, numpy as np
from scipy import stats
T = pd.read_csv("C_daily_table.csv", parse_dates=["day", "models_ts", "datasets_ts"])
T = T[(T.gap == 1) & (T.day >= "2025-07-10")].dropna(subset=["models_ts"]).reset_index(drop=True)
T["m_min"] = T.models_ts.dt.hour * 60 + T.models_ts.dt.minute + T.models_ts.dt.second / 60
T["m_dev"] = T.m_min - T.m_min.rolling(15, center=True, min_periods=5).median()
T["ds_dev"] = T.datasets_ts.dt.hour * 60 + T.datasets_ts.dt.minute - T.m_min.rolling(15, center=True, min_periods=5).median()
T["d_stall"] = T.d_ratio < 0.1; T["m_half"] = (T.m_ratio < 0.7) & (T.m_fz2000 > 0.3)
for nm, f in [("dataset total stall (ratio<0.1)", "d_stall"), ("model half-stall (ratio<0.7 & frozen>0.3)", "m_half")]:
    a, b = T[T[f]], T[~T[f]]
    print(nm, "n", len(a), "| models upload minute-of-day deviation from local median: stall mean %.2f, others mean %.2f (min); MWU p=%.3f" % (a.m_dev.mean(), b.m_dev.mean(), stats.mannwhitneyu(a.m_dev.dropna(), b.m_dev.dropna()).pvalue))
    a2, b2 = a.ds_minus_models_min.dropna(), b.ds_minus_models_min.dropna()
    print("   datasets-after-models spacing (min): stall mean %.2f, others mean %.2f; MWU p=%.3f" % (a2.mean(), b2.mean(), stats.mannwhitneyu(a2, b2).pvalue))
    a3, b3 = a.models_int_h, b.models_int_h
    print("   interval h: stall mean %.3f sd %.3f, others mean %.3f sd %.3f" % (a3.mean(), a3.std(), b3.mean(), b3.std()))
print("corr(m_ratio, m_dev) pearson/spearman", stats.pearsonr(T.dropna(subset=["m_ratio","m_dev"]).m_ratio, T.dropna(subset=["m_ratio","m_dev"]).m_dev)[0].round(3), stats.spearmanr(T.dropna(subset=["m_ratio","m_dev"]).m_ratio, T.dropna(subset=["m_ratio","m_dev"]).m_dev)[0].round(3))
# monthly stall rate (13h era)
T["ym"] = T.day.dt.to_period("M")
print(T.groupby("ym").agg(n=("day", "size"), ds_stalls=("d_stall", "sum"), m_half=("m_half", "sum")).T.to_string())
