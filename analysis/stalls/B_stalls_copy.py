"""Days when the Hub's download counters stood still.

Some snapshots carry counters that barely moved since the day before: every tag at 0, or a tiny fraction of a normal
day. These are not two snapshots taken close together (uploads stay about 24 hours apart); the Hub simply did not
update its counters, and it books those downloads over the next day or two, sometimes the day before.

Each episode becomes a window: the quiet days plus the catch-up days around them. Spreading the window's total evenly
over its days keeps every sum exact and removes both the hole and the spike. Per-model series get the same treatment by
ignoring the snapshots inside a window (all but its last day), so the gap between the remaining snapshots is spread
evenly by whoever reads them.
"""
import datetime as dt

import polars as pl

LOW = 0.3        # a day below this share of the local median is a stall
HIGH = 1.3       # a neighbouring day above it is catching up
MEDIAN_DAYS = 15


def windows(hub: pl.DataFrame, settled_before: dt.date | None = None) -> list[list[dt.date]]:
    """Stall episodes in a hub series (day, pipeline_tag, dl), as lists of consecutive days.

    Episodes that touch the last two days are left alone until the catch-up has had time to arrive.
    """
    t = hub.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
    t = t.with_columns(pl.col("tot").rolling_median(window_size=MEDIAN_DAYS, center=True, min_samples=5).alias("med"))
    days = t["day"].to_list()
    r = [(a / m if m else 1.0) for a, m in zip(t["tot"].to_list(), t["med"].to_list())]
    n, out, k = len(days), [], 0
    while k < n:
        if r[k] >= LOW:
            k += 1
            continue
        a = b = k
        while b + 1 < n and r[b + 1] < LOW:
            b += 1
        e = b + 1                               # always take the next day: the counters resume there
        for f in range(b + 3, e, -1):           # catch-up can land up to three days later
            if f < n and r[f] > HIGH:
                e = f
                break
        while e + 1 < n and e + 1 <= b + 4 and r[e] > HIGH and r[e + 1] > HIGH:
            e += 1                              # and keep going while it lasts
        while a - 1 >= 0 and a - 1 >= k - 2 and r[a - 1] > 1.5:
            a -= 1                              # downloads booked early, the day before the stall
        if e >= n - 1:                          # too recent to know how it ends
            break
        if out and (days[a] - out[-1][-1]).days <= 2:   # episodes a day or two apart are one episode
            first = out[-1][0]
            out[-1] = [d for d in days if first <= d <= days[e]]
        else:
            out.append(days[a:e + 1])
        k = e + 1
    if settled_before:
        out = [w for w in out if w[-1] < settled_before]
    return out


def smooth(hub: pl.DataFrame, wins: list[list[dt.date]]) -> pl.DataFrame:
    """Spread each window's downloads evenly over its days, tag by tag."""
    if not wins:
        return hub
    key = pl.DataFrame({"day": [d for w in wins for d in w], "win": [i for i, w in enumerate(wins) for _ in w]})
    h = hub.join(key, on="day", how="left")
    size = key.group_by("win").agg(pl.len().alias("n"))
    total = h.filter(pl.col("win").is_not_null()).group_by("win", "pipeline_tag").agg(pl.col("dl").sum().alias("sum"))
    # every tag gets a row on every day of its window, even days where it had none
    spread = (key.join(total, on="win").join(size, on="win")
              .with_columns((pl.col("sum") / pl.col("n")).round(0).cast(pl.Int64).alias("dl"))
              .select("day", "pipeline_tag", "dl"))
    return pl.concat([h.filter(pl.col("win").is_null()).select(hub.columns), spread.select(hub.columns)]).sort("day", "pipeline_tag")


def skip_days(wins: list[list[dt.date]]) -> list[str]:
    """Snapshots to ignore in per-model series: every day of a window but its last."""
    return sorted({d.isoformat() for w in wins for d in w[:-1]})
