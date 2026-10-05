"""Effect of the partial snapshot 2025-11-24 (26% of the usual rows) on author_series/family_series and the hub."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
show(c, "select day, n from rowsperday where day between '2025-11-15' and '2025-11-30' order by day")
print("-- authors: models counted on 11-24 vs neighbours (authors with >=100 models on 11-25)")
show(c, """with a as (select author, day, models, dl_all, dl30 from auth where day in ('2025-11-19','2025-11-24','2025-11-25'))
 select count(*) n_authors, sum((b.models<0.8*c.models)::int) lt80pct_members, sum((b.dl30<0.9*c.dl30)::int) dl30_dip_gt10pct, sum((b.dl_all<0.9*c.dl_all)::int) dlall_dip_gt10pct
 from (select * from a where day='2025-11-24') b join (select * from a where day='2025-11-25') c using(author) where c.models>=1""")
print("-- biggest authors by dl30 hit")
show(c, """with a as (select author, day, models, dl_all, dl30 from auth where day in ('2025-11-19','2025-11-24','2025-11-25'))
 select b.author, c.models m25, b.models m24, round(b.dl_all*1.0/c.dl_all,2) all24_over_all25, round(b.dl30*1.0/c.dl30,2) d30_ratio, c.dl_all-b.dl_all fake_step
 from (select * from a where day='2025-11-24') b join (select * from a where day='2025-11-25') c using(author) order by c.dl_all-b.dl_all desc limit 15""")
print("-- which models are present on 11-24? compare distribution of dl30 of present vs absent models (11-25 population)")
show(c, """select (p.id is not null) present, count(*) n, round(median(a.dl30)) med_dl30, round(avg(a.dl30)) avg_dl30, sum(a.dl30) sum30 from series a left join series p on p.id=a.id and p.day='2025-11-24' where a.day='2025-11-25' group by 1""")
print("-- family_series: members on 11-24 vs 11-25 for top families")
show(c, """select b.id, c.members m25, b.members m24, c.dl_all-b.dl_all step from (select * from fam where day='2025-11-24') b join (select * from fam where day='2025-11-25') c using(id) order by step desc limit 8""")
print("-- hub_series around")
con2 = c
show(c, f"select day, sum(dl) from read_parquet('{DATA}/hub_series.parquet') where day between '2025-11-18' and '2025-11-30' group by 1 order by 1")
