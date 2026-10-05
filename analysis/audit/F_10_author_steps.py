"""Author series (author_series): one-day jumps in dl_all that are member models entering the sum (renames in / moves), not downloads.
The author page 'Weekly' / 'Daily' charts and Wrapped-like views difference dl_all, so such a step becomes a fake spike."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute("""CREATE OR REPLACE TABLE astep AS
 SELECT author, day, dl_all, models, dl_all - lag(dl_all) OVER w step, models::BIGINT - lag(models::BIGINT) OVER w dm, day - lag(day) OVER w gap
 FROM auth WHERE dl_all IS NOT NULL AND day NOT IN (SELECT day FROM skip) WINDOW w AS (PARTITION BY author ORDER BY day)""")
c.execute("""CREATE OR REPLACE TABLE amed AS SELECT author, median(step/gap) med, sum(step) tot, max(day) lastday, count(*) n FROM astep WHERE step IS NOT NULL GROUP BY author""")
print("authors", c.execute("select count(*) from amed").fetchone())
show(c, """select count(*) n_step_gt_25x, count(distinct author) authors
 from astep s join amed m using(author) where s.step > 25*greatest(m.med,1) and s.step > 1000000 and s.gap<=2""")
print("-- biggest steps relative to the author's median daily increment")
show(c, """select s.author, s.day, s.step, round(s.step/greatest(m.med,1)) x_median, s.dm models_added, s.models, round(s.step*1.0/m.tot,3) share_of_author_total
 from astep s join amed m using(author) where s.step > 25*greatest(m.med,1) and s.step > 1000000 and s.gap<=2 order by s.step desc limit 40""", 40)
print("-- how many authors' (top 200 by dl30) biggest single step is >20% of their all-time total")
show(c, """with t as (select author, sum(dl30) d from models group by 1 order by 2 desc limit 300),
 b as (select s.author, max(s.step) mx, any_value(m.tot) tot from astep s join amed m using(author) where s.gap<=2 group by 1)
 select count(*) n, sum((mx > 0.2*tot)::int) n_gt20, sum((mx>0.1*tot)::int) n_gt10 from b join t using(author)""")
