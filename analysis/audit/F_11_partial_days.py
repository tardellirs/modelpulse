"""Rows per snapshot day (models present), to find partial snapshots; and effect on author_series (members per day)."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute("CREATE OR REPLACE TABLE rowsperday AS SELECT day, count(*) n, count(dl_all) n_all FROM series GROUP BY day ORDER BY day")
c.execute("CREATE OR REPLACE TABLE rpd2 AS SELECT *, lag(n) OVER (ORDER BY day) pn, lead(n) OVER (ORDER BY day) nn, median(n) OVER (ORDER BY day ROWS BETWEEN 7 PRECEDING AND 7 FOLLOWING) med FROM rowsperday")
show(c, "select day, n, n_all, med, round(n*1.0/med,3) r, day in (select day from skip) is_skip, day in (select day from low) is_low from rpd2 where n < 0.97*med or n > 1.03*med order by day", 80)
