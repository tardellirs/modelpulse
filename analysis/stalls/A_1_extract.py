import duckdb,glob,os
con=duckdb.connect();con.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
files=sorted(glob.glob('/data/series/*.parquet'))
files=[f for f in files if f[-15:-8]>='2025-02']
con.execute("create table mx(id varchar, m bigint)")
for f in files:
    con.execute(f"insert into mx select id, max(dl30) from '{f}' where dl_all is not null group by id")
con.execute("create table ids as select id, max(m) m from mx group by id")
for t in [1000,3000,5000,10000,30000]:
    print(t, con.sql(f"select count(*) from ids where m>={t}").fetchone())
# dl30 cutoff for top-10000 on a few days
for f in files[::4]:
    print(f, con.sql(f"select min(dl30) from (select dl30, row_number() over (partition by day order by dl30 desc) r, day from '{f}' where day=(select max(day) from '{f}')) where r<=10000").fetchone())
T=1000
con.execute(f"create table cid as select id from ids where m>={T}")
out='/work/stalls_A/cand.parquet'
if os.path.exists(out): os.remove(out)
sel=" union all ".join(f"select s.id,s.day,s.dl30,s.dl_all from '{f}' s join cid using(id) where s.dl_all is not null" for f in files)
con.execute(f"copy ({sel}) to '{out}' (format parquet, compression zstd)")
print(con.sql(f"select count(*),count(distinct id),count(distinct day),min(day),max(day) from '{out}'"))
