import duckdb, json
c = duckdb.connect(); c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
for k, p in [("datasets", "/data/datasets/series/2026-08.parquet"), ("models", "/data/series/2026-08.parquet")]:
    print(k, c.execute(f"describe select * from '{p}'").fetchall())
    print(c.execute(f"select day, count(*), count(dl_all), sum(dl_all) from '{p}' group by 1 order by 1 limit 4").fetchall())
m = json.load(open("/data/repos_meta.json")); print(m.keys()); print(m["skip_days"]); print(len(m["datasets_days"]), m["datasets_days"][:3], m["datasets_days"][-3:])
mm = json.load(open("/data/meta.json")); print(mm["days"][:3], mm["days"][-3:])
