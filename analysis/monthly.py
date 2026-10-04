"""Monthly downloads per repo, measured between month boundaries (the 1st of each month).

The source has missing days (most of June 2025, parts of Apr-Jun 2026) and days when the Hub's counters stood still
(`skip_days`), so a month's last snapshot can be weeks early. Each repo's counter is therefore read at the exact
boundary, interpolated linearly between the nearest usable snapshots on either side.

- `dl`: exact, the difference of the all-time counter between boundaries (from March 2025, when it appears).
- `dl_est`: the rolling 30-day count read at the end of the month, scaled to the month's length. It is the only
  measure before March 2025 and stands in for `dl` there (`exact` = false).
"""
import calendar
from datetime import date, timedelta


def month_starts(first: date, last: date):
    out, d = [], first.replace(day=1)
    while d <= last:
        out.append(d)
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def build(con, name: str, glob: str, days, skip, created: str, first="2024-07-01", last="2026-09-01", exact_from="2025-03-01"):
    """Create table `name` (id, m, dl, dl_est, exact). `created` is a table with (id, created DATE)."""
    usable = sorted(date.fromisoformat(d) for d in days if d not in set(skip))
    bounds = month_starts(date.fromisoformat(first), date.fromisoformat(last) + timedelta(days=32))
    rows = []
    for b in bounds:
        lo = max((d for d in usable if d <= b), default=None)
        hi = min((d for d in usable if d >= b), default=None)
        if hi is None:
            continue
        lo = lo or hi
        w = 0.0 if hi == lo else (b - lo).days / (hi - lo).days
        rows.append((b, lo, hi, w))
    con.execute("CREATE OR REPLACE TEMP TABLE bnd (b DATE, lo DATE, hi DATE, w DOUBLE)")
    con.executemany("INSERT INTO bnd VALUES (?, ?, ?, ?)", rows)
    snap_days = sorted({r[1] for r in rows} | {r[2] for r in rows})
    con.execute(f"""CREATE OR REPLACE TEMP TABLE snap AS SELECT id, day, dl30, dl_all FROM read_parquet('{glob}')
        WHERE day IN ({",".join(f"DATE '{d}'" for d in snap_days)})""")
    # the counters at each boundary: interpolated when the repo is in both snapshots; a repo created in between
    # starts from zero; one that disappeared keeps its last value
    con.execute(f"""CREATE OR REPLACE TEMP TABLE bval AS
        WITH l AS (SELECT b.b, s.* FROM bnd b JOIN snap s ON s.day = b.lo), h AS (SELECT b.b, s.* FROM bnd b JOIN snap s ON s.day = b.hi),
        j AS (SELECT coalesce(l.b, h.b) AS b, coalesce(l.id, h.id) AS id, l.dl_all AS a_lo, h.dl_all AS a_hi, l.dl30 AS t_lo, h.dl30 AS t_hi
              FROM l FULL JOIN h ON l.b = h.b AND l.id = h.id)
        SELECT j.b, j.id,
          CASE WHEN a_lo IS NOT NULL AND a_hi IS NOT NULL THEN a_lo + bnd.w * (a_hi - a_lo)
               WHEN a_lo IS NULL AND a_hi IS NOT NULL AND c.created >= bnd.lo THEN bnd.w * a_hi
               WHEN a_hi IS NULL THEN a_lo END AS a,
          coalesce(t_lo, 0) * (1 - bnd.w) + coalesce(t_hi, 0) * bnd.w AS t
        FROM j JOIN bnd USING (b) LEFT JOIN {created} c USING (id)""")
    # month m runs from boundary m to boundary m + 1; a repo missing at the start (created during the month, or newly
    # tracked) starts from zero if it was created that month and is left out otherwise
    days_in = "CASE month(m) WHEN 2 THEN CASE WHEN year(m) % 4 = 0 THEN 29 ELSE 28 END WHEN 4 THEN 30 WHEN 6 THEN 30 WHEN 9 THEN 30 WHEN 11 THEN 30 ELSE 31 END"
    con.execute(f"""CREATE OR REPLACE TABLE {name} AS
        WITH u AS (SELECT n.id, (n.b - INTERVAL 1 MONTH)::DATE AS m, p.a, n.a AS a_next, n.t AS t_next, c.created
                   FROM bval n LEFT JOIN bval p ON p.id = n.id AND p.b = n.b - INTERVAL 1 MONTH LEFT JOIN {created} c ON c.id = n.id
                   WHERE n.b > (SELECT min(b) FROM bnd)),
        v AS (SELECT id, m, CASE WHEN m >= DATE '{exact_from}' THEN greatest(0, a_next - coalesce(a, CASE WHEN created >= m THEN 0 END)) END AS dl_x,
                t_next * ({days_in}) / 30.0 AS dl_est FROM u WHERE m BETWEEN DATE '{first}' AND DATE '{last}')
        SELECT id, m, CASE WHEN m >= DATE '{exact_from}' THEN dl_x ELSE dl_est END AS dl, dl_est, m >= DATE '{exact_from}' AS exact
        FROM v WHERE m < DATE '{exact_from}' OR dl_x IS NOT NULL""")
    return rows
