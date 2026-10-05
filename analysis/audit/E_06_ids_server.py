"""Server version (docker, 4g): per-id span of the dataset series via duckdb, plus rename candidates. Writes /out/*.csv"""
import duckdb
con=duckdb.connect(); con.execute("SET memory_limit='3GB'; SET threads=2")
con.execute("""CREATE TABLE span AS SELECT id, min(day) d_first, max(day) d_last, count(*) n, arg_min(dl_all,day) all_first, arg_max(dl_all,day) all_last, arg_max(dl30,day) dl30_last, max(dl_all) all_max
 FROM read_parquet('/d/datasets/series/*.parquet') WHERE dl_all IS NOT NULL GROUP BY id""")
print(con.execute("select count(*) from span").fetchone())
con.execute("COPY (SELECT * FROM span WHERE d_last < DATE '2026-10-04' AND all_max>=100000 ORDER BY all_max DESC LIMIT 3000) TO '/out/gone_big.csv' (HEADER)")
con.execute("""COPY (SELECT date_trunc('month',d_last) m, count(*) n, sum(all_max>=10000) n10k, sum(all_max>=1000000) n1m, sum(dl30_last) dl30_sum FROM span WHERE d_last<DATE '2026-10-04' GROUP BY 1 ORDER BY 1) TO '/out/gone_by_month.csv' (HEADER)""")
# rename candidates: id A last day d, id B first day d+1..d+2, same dl_all within 1%
con.execute("""COPY (SELECT a.id old_id,b.id new_id,a.d_last AS last_old,b.d_first AS first_new,a.all_last old_all,b.all_first new_all FROM span a JOIN span b ON b.d_first BETWEEN a.d_last AND a.d_last+2 AND a.id<>b.id AND lower(a.id)<>lower(b.id) AND split_part(a.id,'/',2)=split_part(b.id,'/',2) AND a.all_last>=1000 AND abs(b.all_first-a.all_last)<=0.02*a.all_last ORDER BY a.all_last DESC LIMIT 500) TO '/out/rename_cand.csv' (HEADER)""")
# case-insensitive duplicates alive in same day
con.execute("""COPY (SELECT lower(id) lid,count(*) k,list(id) ids,sum(n) n FROM span WHERE d_last=DATE '2026-10-04' GROUP BY 1 HAVING count(*)>1 ORDER BY k DESC LIMIT 200) TO '/out/case_dups.csv' (HEADER)""")
# flapping ids: n < last-first+1 - tolerance
con.execute("""COPY (SELECT count(*) filter (where n < (d_last-d_first)+1 - 40) n_with_holes, count(*) total FROM span) TO '/out/holes.csv' (HEADER)""")
