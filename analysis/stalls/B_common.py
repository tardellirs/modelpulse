"""Shared helpers: raw hub series, rule implementations (current / pair / frozen-share)."""
import datetime as dt
import polars as pl
import B_stalls_copy as st

W = "/work/stalls_B"
LOW, HIGH = st.LOW, st.HIGH

def raw_hub(rounded=True) -> pl.DataFrame:
    """Calendar-day raw hub series (day, pipeline_tag, dl), a snapshot gap's per-day average written on each day it covers."""
    s = pl.read_parquet(f"{W}/hub_raw_snap.parquet")
    rows = []
    for r in s.iter_rows(named=True):
        for k in range(r["gap"]):
            rows.append((r["day"] - dt.timedelta(days=k), r["tag"], r["dsum"] / r["gap"]))
    h = pl.DataFrame(rows, schema=["day", "pipeline_tag", "dl"], orient="row")
    if rounded:
        h = h.with_columns(pl.col("dl").round(0).cast(pl.Int64))
    return h.sort("day", "pipeline_tag")

def totals(hub):
    t = hub.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
    t = t.with_columns(pl.col("tot").rolling_median(window_size=st.MEDIAN_DAYS, center=True, min_samples=5).alias("med"))
    return t.with_columns((pl.col("tot") / pl.col("med")).alias("r"))

def windows_flags(days, r, flag, settled=True):
    """stalls.windows logic with `r<LOW` replaced by an arbitrary per-day flag list. r = ratio to median (for catch-up)."""
    n, out, k = len(days), [], 0
    while k < n:
        if not flag[k]:
            k += 1; continue
        a = b = k
        while b + 1 < n and flag[b + 1]:
            b += 1
        e = b + 1
        for f in range(b + 3, e, -1):
            if f < n and r[f] > HIGH:
                e = f; break
        while e + 1 < n and e + 1 <= b + 4 and r[e] > HIGH and r[e + 1] > HIGH:
            e += 1
        while a - 1 >= 0 and a - 1 >= k - 2 and r[a - 1] > 1.5:
            a -= 1
        if e >= n - 1:
            break
        if out and (days[a] - out[-1][-1]).days <= 2:
            first = out[-1][0]
            out[-1] = [d for d in days if first <= d <= days[e]]
        else:
            out.append(days[a:e + 1])
        k = e + 1
    return out

def merge(days, wins):
    """Union of window lists, merging episodes <=2 days apart (as stalls.py does)."""
    ws = sorted([(w[0], w[-1]) for w in wins])
    out = []
    for a, b in ws:
        if out and (a - out[-1][1]).days <= 2:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return [[d for d in days if a <= d <= b] for a, b in out]

def pair_pairs(days, r, lo=0.7, hi=HIGH, s_lo=1.6, s_hi=2.4):
    """Day under `lo` of the median next to a day over `hi`, the two summing to ~2x the median. Returns [(low_day, partner_day)]."""
    out = []
    for i in range(len(days)):
        if r[i] >= lo or r[i] < 0.3:
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(days) and r[j] > hi and s_lo <= r[i] + r[j] <= s_hi:
                out.append((days[i], days[j]))
    return out
