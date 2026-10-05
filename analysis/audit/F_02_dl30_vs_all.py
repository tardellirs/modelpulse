"""dl30(t) vs dl_all(t)-dl_all(t-30), per model, on the top-model subset. Skips hub skip_days at either end."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
c.execute("""CREATE OR REPLACE TABLE cons AS
 SELECT a.id, a.day, a.dl30, a.dl_all - b.dl_all AS d30
 FROM s a JOIN s b ON a.id=b.id AND b.day=a.day-30
 WHERE a.dl_all IS NOT NULL AND b.dl_all IS NOT NULL AND a.dl30>=1000
   AND a.day NOT IN (SELECT day FROM skip) AND b.day NOT IN (SELECT day FROM skip)""")
print("rows", c.sql("select count(*) from cons").fetchone())
# overall ratio distribution by month
show(c, """select strftime(day,'%Y-%m') m, count(*) n,
  round(quantile_cont(d30*1.0/dl30,0.05),3) p05, round(quantile_cont(d30*1.0/dl30,0.25),3) p25, round(median(d30*1.0/dl30),3) med, round(quantile_cont(d30*1.0/dl30,0.75),3) p75, round(quantile_cont(d30*1.0/dl30,0.95),3) p95,
  round(avg((abs(d30*1.0/dl30-1)>0.25)::int),3) frac_off25
  from cons group by 1 order by 1""")
