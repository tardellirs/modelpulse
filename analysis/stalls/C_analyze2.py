"""Extra tables: the 12 half-stall days, exact dataset totals on stall days, commit hour (UTC) by era, stall rate by hour/era."""
import json, datetime as dt, pandas as pd, polars as pl, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
H = "2025-07-16 2025-08-13 2025-10-01 2025-10-08 2025-11-26 2026-02-11 2026-04-29 2026-06-25 2026-07-29 2026-08-01 2026-08-05 2026-08-12".split()
T = pd.read_csv("C_daily_table.csv", parse_dates=["day", "models_ts", "datasets_ts"]); T["ds"] = T.day.dt.strftime("%Y-%m-%d")
T["m_hr"] = T.models_ts.dt.hour + T.models_ts.dt.minute / 60
cols = ["ds", "m_ratio", "d_ratio", "m_fz2000", "d_fz1000", "models_int_h", "datasets_int_h", "ds_minus_models_min", "m_hr"]
print("== half-stall days"); print(T[T.ds.isin(H)][cols].round(3).to_string(index=False))
sk = json.load(open("C_skip_days.json"))
print("\n== dataset skip_days: dataset ratio / frozen vs model ratio / frozen")
x = T[T.ds.isin(sk["datasets"])][cols].round(3); print(x.to_string(index=False))
# era by commit hour
T["era"] = np.where(T.m_hr >= 22, "23h UTC", np.where((T.m_hr >= 12) & (T.m_hr < 15), "13h UTC", "other"))
print("\n== commit hour era boundaries"); 
g = T.dropna(subset=["m_hr"]).copy(); g["chg"] = g.era != g.era.shift(); print(g[g.chg][["ds", "era", "m_hr"]].to_string(index=False))
ok = T[(T.gap == 1)]
print("\n== dip rates by era (g==1 days)")
for e, s in ok.groupby("era"):
    print(e, "n", len(s), "models ratio<0.7:", int((s.m_ratio < .7).sum()), "datasets ratio<0.3:", int((s.d_ratio < .3).sum()), "datasets ratio<0.7:", int((s.d_ratio < .7).sum()))
# stalls by ds-minus-models spacing
print("\n== datasets-minus-models upload gap (min) distribution on dataset-stall days (d_ratio<0.1) vs others")
s = ok.dropna(subset=["ds_minus_models_min", "d_ratio"]); a = s[s.d_ratio < .1].ds_minus_models_min; b = s[s.d_ratio >= .1].ds_minus_models_min
print("stall:", a.describe().round(2).to_dict()); print("other:", b.describe().round(2).to_dict())
print("\n== day after each dataset stall (catch-up): dataset ratio next snapshot")
T2 = T.reset_index(drop=True)
for i in T2.index[(T2.d_ratio < .1) & (T2.gap == 1)]:
    if i + 1 < len(T2): print(T2.ds[i], "d_ratio", round(T2.d_ratio[i], 3), "-> next", T2.ds[i + 1], round(T2.d_ratio[i + 1], 3), "| models", round(T2.m_ratio[i], 3), "->", round(T2.m_ratio[i + 1], 3))
