import duckdb, json
con = duckdb.connect(); con.execute("SET memory_limit='5GB'; SET threads=3")
r = con.execute("""
WITH meta AS (SELECT id, created_at::DATE AS created, pipeline_tag, base_relation, author FROM read_parquet('/data/models.parquet')
              WHERE created_at >= TIMESTAMP '2025-03-01'),
s AS (SELECT s.id, s.day, s.dl_all FROM read_parquet('/data/series/*.parquet') s JOIN meta USING (id) WHERE s.dl_all IS NOT NULL),
f AS (SELECT id, min(day) AS first_day, arg_min(dl_all, day) AS first_all, min(day) FILTER (WHERE dl_all >= 1000000) AS day1m FROM s GROUP BY id)
SELECT f.id, meta.author, meta.pipeline_tag, meta.base_relation, meta.created, f.day1m, (f.day1m - meta.created) AS days
FROM f JOIN meta USING (id)
WHERE f.day1m IS NOT NULL AND f.first_all < 100000 AND f.first_day >= meta.created AND f.first_day - meta.created <= 3
ORDER BY days""").pl()
out = {"n": r.height, "median_days": float(r["days"].median()), "fastest": r.head(30).to_dicts(),
       "by_relation": r.group_by("base_relation").agg(n=duckdb and __import__("polars").len(), med=__import__("polars").col("days").median()).to_dicts(),
       "originals_fastest": r.filter(r["base_relation"].is_null()).head(15).to_dicts()}
json.dump(out, open("/work/race.json", "w"), default=str, indent=1); print("ok", r.height)
