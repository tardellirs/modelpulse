"""AuthorPage stat tiles sum only the 200 models the API returns (author_models limit 200). How many authors and how much is hidden. Single-file small read."""
from F_common import *
c = con(mem="1GB"); c.execute("SET threads=1")
c.execute(f"""CREATE TEMP TABLE r AS SELECT author, id, coalesce(dl30,0) dl30, coalesce(dl_all,0) dl_all, coalesce(dl_7d,0) dl_7d,
   row_number() OVER (PARTITION BY author ORDER BY dl30 DESC NULLS LAST) rk FROM read_parquet('{DATA}/models.parquet') WHERE author IS NOT NULL""")
show(c, """select count(distinct author) authors_gt200, (select count(distinct author) from r) authors from r where rk=201""")
show(c, """with a as (select author, count(*) n, sum(dl30) t30, sum(dl30) filter (rk<=200) s30, sum(dl_all) tall, sum(dl_all) filter (rk<=200) sall, sum(dl_7d) t7, sum(dl_7d) filter (rk<=200) s7 from r group by 1 having count(*)>200)
 select author, n, t30, round(s30*1.0/t30,3) shown_30d, tall, round(sall*1.0/tall,3) shown_all, round(s7*1.0/nullif(t7,0),3) shown_7d from a order by t30 desc limit 15""")
show(c, """with a as (select author, count(*) n, sum(dl30) t30, sum(dl30) filter (rk<=200) s30 from r group by 1 having count(*)>200)
 select count(*) n_authors, sum((s30<0.9*t30)::int) shown_lt90pct, sum((s30<0.5*t30)::int) shown_lt50pct, sum((t30>=1e6)::int) big_authors, sum((t30>=1e6 and s30<0.9*t30)::int) big_lt90 from a""")
