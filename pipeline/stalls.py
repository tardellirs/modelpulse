"""Days when the Hub's download counters stood still, or went backwards.

Stalls. Some snapshots carry counters that barely moved since the day before. These are not two snapshots taken close
together (uploads stay 24 hours apart); the Hub didn't update its counters and books those downloads over the next day
or two, sometimes the day before. Dataset counters freeze all at once; model counters often freeze only in part (old
repos keep counting, newer ones stop), so the Hub-wide total may only dip to half. A day is a stall when any of:
  - the total is below LOW of its local median;
  - at least FROZEN of the big models (BIG+ downloads in the previous 30 days) didn't move at all (FROZEN_DATASETS
    for datasets, whose counters freeze all at once);
  - it is below PAIR_LOW and a neighbouring day above HIGH makes up for it (the two sum to about twice the median).
Each episode becomes a window: the quiet days plus the catch-up days around them. Spreading the window's total evenly
over its days keeps every sum exact and removes both the hole and the spike. Per-model series get the same treatment by
ignoring the snapshots inside a window (all but its last day), so the gap between the remaining snapshots is spread
evenly by whoever reads them.

Rollbacks. Twice the Hub's all-time counters went down for a large share of repos and came back days later. Counting
only positive changes would then count the recovery as new downloads. When more than BACK of the repos go down, those
snapshots are set aside until the counters are back (the shortfall against the last good snapshot falls under
RECOVERED of what it was), and the downloads in between are measured from the last good snapshot to the first good one.
The Hub books part of them a day later, so the set-aside days then count as a stall and the window takes in the catch-up.

Partial snapshots. A few snapshots hold only part of the repos (2025-11-24: 289k of 1.13M models). Under PARTIAL of the
previous snapshot's rows, a snapshot is treated as missing: nothing is measured from or to it, and it goes into the
skip days so per-repo series ignore it too.

Gaps. Days without a snapshot share the per-day average of the next one. A window that reaches into such a stretch takes
all of it, up to the snapshot that closes it, so a catch-up booked across a gap is spread with the stall it belongs to.

Low days. After all this, a few days are still well under their local median and nothing around them makes up for it.
They keep their measured values and are only listed (see low_days).
"""
import bisect
import datetime as dt

import polars as pl

LOW = 0.3            # a day below this share of the local median is a stall
HIGH = 1.3           # a neighbouring day above it is catching up
FROZEN = 0.25        # share of big models whose counter didn't move that makes a day a stall
FROZEN_DATASETS = 0.9  # dataset counters freeze all at once; a few big ones that rarely update would trip 0.25
BIG = 60_000         # a big model: at least this many downloads in the 30 days before (2,000 a day)
MIN_BIG = 100        # too few big repos to tell (early or small series)
PAIR_LOW = 0.7       # a half-depth dip...
PAIR_SUM = (1.6, 2.4)  # ...whose neighbour brings the pair back to about two normal days
MEDIAN_DAYS = 15
BACK = 0.05          # share of repos whose all-time counter went down: a rollback
RECOVERED = 0.1      # a rollback ends when the shortfall falls under this share of where it started
MAX_ROLLBACK = 8     # snapshots; a drop still there after this many is a lasting correction
PARTIAL = 0.5        # a snapshot with fewer rows than this share of the previous one is incomplete
LOW_DAY = 0.7        # low day: under this share of its local median, adjusted for the day of the week...
MADE_UP = 0.5        # ...in a run whose shortfall the days around it don't make up by at least this share
MADE_UP_DAYS = 3     # days on each side that can make it up


# ---------- signals between two snapshots (id, dl_all, dl30) ----------

def signals(prev: pl.DataFrame, cur: pl.DataFrame) -> tuple[float | None, float]:
    """(frozen share of big repos, share of repos whose counter went down) between consecutive snapshots."""
    j = (cur.select("id", "dl_all").join(prev.select("id", pl.col("dl_all").alias("p"), pl.col("dl30").alias("p30")), on="id")
         .drop_nulls(["dl_all", "p"]))
    if not j.height:
        return None, 0.0
    back = float((j["dl_all"] < j["p"]).mean())
    big = j.filter(pl.col("p30") >= BIG)
    frozen = float((big["dl_all"] == big["p"]).mean()) if big.height >= MIN_BIG else None
    return frozen, back


def shortfall(base: pl.DataFrame, cur: pl.DataFrame) -> float:
    """How far below the base snapshot the counters still are, summed over repos."""
    j = cur.select("id", "dl_all").join(base.select("id", pl.col("dl_all").alias("b")), on="id").drop_nulls(["dl_all", "b"])
    return float((j["b"] - j["dl_all"]).clip(0).sum())


class Rollbacks:
    """Decides, snapshot by snapshot, which ones to measure from (state is a small dict kept in meta.json).

    check() returns "use" (measure from the base snapshot to this one), "hold" (set it aside for now) or "release":
    the counters never came back, so the drop was a lasting correction, not a rollback, and every held snapshot is
    measured normally after all, one after the other (`released` lists them).
    """

    def __init__(self, state: dict | None = None):
        self.state = state or None      # {"base": last good day, "start": shortfall, "held": [days set aside]}
        self.released: list[str] = []   # held snapshots that turned out usable after all
        self.recovered: list[str] = []  # held snapshots of a rollback that just ended

    def check(self, base_day: dt.date, base: pl.DataFrame, day: dt.date, cur: pl.DataFrame, back: float) -> str:
        self.released, self.recovered = [], []
        if self.state is None:
            if back <= BACK:
                return "use"
            self.state = {"base": base_day.isoformat(), "start": shortfall(base, cur), "held": [day.isoformat()]}
            return "hold"
        if shortfall(base, cur) <= RECOVERED * self.state["start"]:
            self.recovered, self.state = self.state["held"], None
            return "use"
        if len(self.state["held"]) >= MAX_ROLLBACK:
            self.released, self.state = self.state["held"], None
            return "release"
        self.state["held"].append(day.isoformat())
        return "hold"


def is_partial(prev: pl.DataFrame, cur: pl.DataFrame) -> bool:
    """An incomplete snapshot: far fewer repos with a counter than the one before."""
    return cur.height < PARTIAL * prev.height


def increment(frm: tuple, to: tuple, tags: pl.DataFrame) -> pl.DataFrame:
    """Downloads per pipeline_tag between two (day, snapshot) pairs, one row per calendar day they span, each the
    per-day average; repos whose counter went down add nothing."""
    gap = (to[0] - frm[0]).days
    inc = (to[1].select("id", "dl_all").join(frm[1].select("id", pl.col("dl_all").alias("b")), on="id").drop_nulls()
           .with_columns(((pl.col("dl_all") - pl.col("b")).clip(0) / gap).alias("dl"))
           .join(tags, on="id", how="left").with_columns(pl.col("pipeline_tag").fill_null("other"))
           .group_by("pipeline_tag").agg(pl.col("dl").sum()))
    return pl.concat([inc.with_columns(pl.lit(to[0] - dt.timedelta(days=k)).alias("day")) for k in range(gap)]).select(
        "day", "pipeline_tag", pl.col("dl").round(0).cast(pl.Int64))


def measure(snapshots, tags: pl.DataFrame):
    """Daily series per pipeline_tag from snapshots in order, as (day, frame of id/dl_all/dl30) pairs.

    Returns (raw series, frozen share by day, snapshots set aside as rollbacks, open rollback state or None, partial
    snapshots left out). Downloads between two usable snapshots g days apart are written as their per-day average on
    each of those days.
    """
    rows, frozen, aside, partial = [], {}, [], []
    rb = Rollbacks()
    prev = base = None
    held = {}

    def add(frm, to):
        rows.append(increment(frm, to, tags))

    for day, cur in snapshots:
        cur = cur.drop_nulls("dl_all")
        if not cur.height:
            continue
        if prev is not None and is_partial(prev[1], cur):
            partial.append(day)
            continue
        if prev is None:
            prev = base = (day, cur)
            continue
        f, back = signals(prev[1], cur)
        if (day - prev[0]).days == 1 and rb.state is None:
            frozen[day] = f
        verdict = rb.check(base[0], base[1], day, cur, back)
        if verdict == "hold":
            held[day] = cur
        else:
            if verdict == "release":
                chain = [base] + [(d, held[d]) for d in sorted(held)] + [(day, cur)]
                for a, b in zip(chain, chain[1:]):
                    add(a, b)
            else:
                aside += sorted(held)
                add(base, (day, cur))
            held, base = {}, (day, cur)
        prev = (day, cur)
    if not rows:
        return pl.DataFrame(schema={"day": pl.Date, "pipeline_tag": pl.String, "dl": pl.Int64}), frozen, aside, rb.state, partial
    raw = pl.concat(rows).sort("day", "pipeline_tag")
    return raw, frozen, aside, rb.state, partial


# ---------- windows over a daily series ----------

def _totals(hub: pl.DataFrame):
    t = hub.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
    t = t.with_columns(pl.col("tot").rolling_median(window_size=MEDIAN_DAYS, center=True, min_samples=5).alias("med"))
    return t["day"].to_list(), [(a / m if m else 1.0) for a, m in zip(t["tot"].to_list(), t["med"].to_list())]


def windows(hub: pl.DataFrame, frozen: dict | None = None, settled_before: dt.date | None = None,
            min_frozen: float = FROZEN, snaps=None) -> list[list[dt.date]]:
    """Stall episodes in a daily series (day, pipeline_tag, dl), as lists of consecutive days.

    `frozen` maps snapshot days to the frozen share of big repos (see signals). Episodes that touch the last two days
    are left alone until the catch-up has had time to arrive. `snaps` are the days with a usable snapshot: a window
    that reaches into the days without one around it takes all of them (see whole_gaps).
    """
    days, r = _totals(hub)
    frozen = frozen or {}
    n = len(days)
    stall = [r[i] < LOW or (frozen.get(days[i]) or 0) >= min_frozen for i in range(n)]
    out, k = [], 0
    while k < n:
        if not stall[k]:
            k += 1
            continue
        a = b = k
        while b + 1 < n and stall[b + 1]:
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
        out.append((days[a], days[e]))
        k = e + 1
    # half-depth dips made up by a neighbour, with no frozen counters to show for it
    for i in range(1, n - 2):
        if LOW <= r[i] < PAIR_LOW:
            for j in (i - 1, i + 1):
                if r[j] > HIGH and PAIR_SUM[0] <= r[i] + r[j] <= PAIR_SUM[1]:
                    out.append((min(days[i], days[j]), max(days[i], days[j])))
                    break
    out = whole_gaps(out, days, snaps)
    # episodes a day or two apart are one episode
    merged = []
    for a, b in sorted(out):
        if merged and (a - merged[-1][1]).days <= 2:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    wins = [[d for d in days if a <= d <= b] for a, b in merged]
    if settled_before:
        wins = [w for w in wins if w[-1] < settled_before]
    return wins


def whole_gaps(spans, days, snaps):
    """Widen (first, last) spans so that none cuts through days without a snapshot: those days and the snapshot after
    them share one measured average, so a span takes the whole stretch or none of it. A span that then reaches the
    last day waits, like any other, until the days after it are known."""
    if not snaps:
        return spans
    snaps = sorted(set(snaps))
    out = []
    for a, b in spans:
        i = bisect.bisect_left(snaps, b)        # the snapshot that closes b's stretch
        if i < len(snaps):
            b = max(b, snaps[i])
        j = bisect.bisect_left(snaps, a)        # a's stretch starts the day after the snapshot before it
        if j > 0:
            a = min(a, snaps[j - 1] + dt.timedelta(days=1))
        if b < days[-1]:
            out.append((a, b))
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


def settle_history(raw: pl.DataFrame, frozen: dict, min_frozen: float = FROZEN, snaps=None) -> tuple[pl.DataFrame, list[list[dt.date]]]:
    """Find and spread windows until none is left. Spreading a big episode moves the local median of its neighbours,
    which can reveal a smaller one next to it; settling to a fixed point keeps the daily job from reopening history."""
    hub, wins = raw, []
    for _ in range(10):
        settled = {d for w in wins for d in w[:-1]}
        new = [w for w in windows(hub, {d: v for d, v in frozen.items() if d not in settled}, min_frozen=min_frozen, snaps=snaps)
               if not all(d in settled for d in w[:-1])]
        if not new:
            break
        hub = smooth(hub, new)
        wins = sorted(wins + new)
    return hub, wins


def low_days(hub: pl.DataFrame) -> list[str]:
    """Days still under LOW_DAY of their local median after stalls, rollbacks and gaps are handled, in runs that the
    MADE_UP_DAYS on each side don't make up by at least MADE_UP of their shortfall.

    The median is adjusted for the day of the week (weekends run a little lower), so ordinary weekend dips don't
    count. These days keep their measured values and are only listed, for charts to mark. The last two days wait,
    like windows do, until their neighbours are known.
    """
    t = hub.group_by("day").agg(pl.col("dl").sum().alias("tot")).sort("day")
    t = t.with_columns(pl.col("tot").rolling_median(window_size=MEDIAN_DAYS, center=True, min_samples=5).alias("med"))
    t = t.with_columns(pl.col("day").dt.weekday().alias("wd"), (pl.col("tot") / pl.col("med")).alias("r"))
    week = t.group_by("wd").agg(pl.col("r").median().alias("f"))
    t = t.join(week, on="wd", how="left").sort("day").with_columns((pl.col("med") * pl.col("f")).alias("exp"))
    days, tot, exp = t["day"].to_list(), t["tot"].to_list(), t["exp"].to_list()
    n = len(days) - 2
    low = [exp[i] is not None and exp[i] > 0 and tot[i] < LOW_DAY * exp[i] for i in range(n)]
    out, i = [], 0
    while i < n:
        if not low[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and low[j + 1] and (days[j + 1] - days[j]).days == 1:
            j += 1
        short = sum(exp[k] - tot[k] for k in range(i, j + 1))
        around = [k for k in range(max(0, i - MADE_UP_DAYS), min(len(days), j + 1 + MADE_UP_DAYS)) if not i <= k <= j]
        back = sum(max(0.0, tot[k] - exp[k]) for k in around if exp[k] is not None)
        if back < MADE_UP * short:
            out += [days[k].isoformat() for k in range(i, j + 1)]
        i = j + 1
    return out


def skip_days(wins: list[list[dt.date]]) -> list[str]:
    """Snapshots to ignore in per-model series: every day of a window but its last."""
    return sorted({d.isoformat() for w in wins for d in w[:-1]})


def settle(hub: pl.DataFrame, meta: dict, today: dt.date, min_frozen: float = FROZEN, snaps=None) -> tuple[pl.DataFrame, list[list[dt.date]]]:
    """Daily step: find new windows among the days not yet settled, spread them, and record their skip days in meta.

    Days already inside a window are smoothed and stay as they are; only `meta["frozen"]` days not yet skipped can open
    a new one, so re-running never re-spreads settled history.
    """
    skip = set(meta.get("skip_days", []))
    pending = set(meta.get("pending", []))       # days of a rollback that ended, not yet in a window
    frozen = {dt.date.fromisoformat(d): v for d, v in meta.get("frozen", {}).items() if d not in skip and v is not None}
    frozen |= {dt.date.fromisoformat(d): 1.0 for d in pending}
    wins = [w for w in windows(hub, frozen, min_frozen=min_frozen, snaps=snaps) if not all(d.isoformat() in skip - pending for d in w[:-1])]
    if wins:
        hub = smooth(hub, wins)
        meta["skip_days"] = sorted(skip | set(skip_days(wins)))
    done = {d.isoformat() for w in wins for d in w}
    if pending - done:
        meta["pending"] = sorted(pending - done)
    else:
        meta.pop("pending", None)
    # keep the last few weeks of signals: a window settles within a few days
    keep = (today - dt.timedelta(days=30)).isoformat()
    meta["frozen"] = {d: v for d, v in meta.get("frozen", {}).items() if d >= keep}
    meta["low_days"] = low_days(hub)
    return hub, wins
