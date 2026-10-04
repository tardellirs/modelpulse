"""Datasets, Spaces and model-size statistics for the article. Writes /work/analysis_repos.json.

Run inside the API image:  docker run --rm --memory 6g -v /opt/modelpulse/data:/data -v /opt/modelpulse/work:/work \
    -v $PWD:/a modelpulse-api python /a/explore_repos.py   (needs monthly.py next to it)
"""
import json
import os

import duckdb

import monthly

D = "/data"
os.makedirs("/work/duck_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET memory_limit='5GB'; SET threads=3; SET temp_directory='/work/duck_tmp'; SET preserve_insertion_order=false")
q = lambda sql: [dict(zip([c[0] for c in r.description], row)) for r in [con.execute(sql)] for row in r.fetchall()]
out = {}
M0, M1 = "2025-03-01", "2026-09-01"


MM = json.load(open(f"{D}/meta.json")); RM = json.load(open(f"{D}/repos_meta.json"))


# ---------------- model size, finer ----------------
print("# model size", flush=True)
con.execute(f"CREATE TABLE meta AS SELECT id, author, pipeline_tag, params, base_relation, is_gguf, created_at::DATE AS created FROM read_parquet('{D}/models.parquet')")
monthly.build(con, "md", f"{D}/series/*.parquet", MM["days"], MM["skip_days"], "meta")
con.execute("CREATE TABLE tg AS SELECT m, id, dl, params FROM md JOIN meta USING (id) WHERE pipeline_tag = 'text-generation' AND params > 1e7 AND dl > 0")
out["size_buckets"] = q("""SELECT m, sum(dl) AS dl,
    sum(dl) FILTER (WHERE params < 1e9) / sum(dl) AS lt1, sum(dl) FILTER (WHERE params >= 1e9 AND params < 4e9) / sum(dl) AS b1_4,
    sum(dl) FILTER (WHERE params >= 4e9 AND params < 10e9) / sum(dl) AS b4_10, sum(dl) FILTER (WHERE params >= 10e9 AND params < 35e9) / sum(dl) AS b10_35,
    sum(dl) FILTER (WHERE params >= 35e9 AND params < 100e9) / sum(dl) AS b35_100, sum(dl) FILTER (WHERE params >= 100e9) / sum(dl) AS ge100,
    sum(dl) FILTER (WHERE params >= 10e9) AS dl_ge10, sum(dl) FILTER (WHERE params >= 100e9) AS dl_ge100
    FROM tg GROUP BY m ORDER BY m""")
# downloads-weighted percentiles: the size of the model behind the median, 75th and 90th percentile download
out["size_pct"] = q("""WITH s AS (SELECT m, params, sum(dl) AS dl FROM tg GROUP BY 1, 2),
    c AS (SELECT m, params, sum(dl) OVER (PARTITION BY m ORDER BY params ROWS UNBOUNDED PRECEDING) / sum(dl) OVER (PARTITION BY m) AS cf FROM s)
    SELECT m, min(params) FILTER (WHERE cf >= 0.25) AS p25, min(params) FILTER (WHERE cf >= 0.5) AS p50,
      min(params) FILTER (WHERE cf >= 0.75) AS p75, min(params) FILTER (WHERE cf >= 0.9) AS p90 FROM c GROUP BY m ORDER BY m""")
out["size_top_big"] = q(f"""SELECT id, params, sum(dl) AS dl FROM tg WHERE params >= 100e9 AND m >= DATE '2026-07-01' GROUP BY 1, 2 ORDER BY dl DESC LIMIT 15""")
out["size_top_mid"] = q(f"""SELECT id, params, sum(dl) AS dl FROM tg WHERE params >= 10e9 AND params < 100e9 AND m >= DATE '2026-07-01' GROUP BY 1, 2 ORDER BY dl DESC LIMIT 15""")
out["models_month_total"] = q("SELECT m, sum(dl) AS dl FROM md GROUP BY m ORDER BY m")
con.execute("DROP TABLE tg")

# ---------------- datasets ----------------
print("# datasets", flush=True)
con.execute(f"""CREATE TABLE dmeta AS SELECT id, author, pipeline_tag, size, license, modality, created_at::DATE AS created, dl30, dl_all, likes,
    used_by_models, used_by_spaces FROM read_parquet('{D}/datasets/datasets.parquet')""")
monthly.build(con, "dd", f"{D}/datasets/series/*.parquet", RM["datasets_days"], RM["skip_days"], "dmeta")
out["ds_month_total"] = q("SELECT m, sum(dl) AS dl, count(*) FILTER (WHERE dl > 0) AS active FROM dd GROUP BY m ORDER BY m")
out["ds_concentration"] = q("""WITH r AS (SELECT m, dl, row_number() OVER (PARTITION BY m ORDER BY dl DESC) AS rk, sum(dl) OVER (PARTITION BY m) AS tot FROM dd WHERE dl > 0)
    SELECT m, sum(dl) FILTER (WHERE rk <= 10) / any_value(tot) AS top10, sum(dl) FILTER (WHERE rk <= 100) / any_value(tot) AS top100,
      sum(dl) FILTER (WHERE rk <= 1000) / any_value(tot) AS top1000 FROM r GROUP BY m ORDER BY m""")
out["ds_modality"] = q("""SELECT m, coalesce(modality, 'unknown') AS modality, sum(dl) AS dl FROM dd JOIN dmeta USING (id) GROUP BY ALL ORDER BY 1, 3 DESC""")
out["ds_task"] = q("""SELECT m, coalesce(pipeline_tag, 'none') AS task, sum(dl) AS dl, count(*) FILTER (WHERE dl > 0) AS n FROM dd JOIN dmeta USING (id) GROUP BY ALL ORDER BY 1, 3 DESC""")
out["ds_size"] = q("""SELECT m, coalesce(size, 'unknown') AS size, sum(dl) AS dl FROM dd JOIN dmeta USING (id) GROUP BY ALL ORDER BY 1, 3 DESC""")
out["ds_license"] = q("""SELECT coalesce(license, 'none') AS license, count(*) AS n, sum(dl30) AS dl30 FROM dmeta GROUP BY 1 ORDER BY 3 DESC LIMIT 15""")
out["ds_authors"] = q(f"""WITH a AS (SELECT author, m, sum(dl) AS dl FROM dd JOIN dmeta USING (id) WHERE m IN (DATE '{M0}', DATE '2025-09-01', DATE '2026-03-01', DATE '{M1}') GROUP BY 1, 2)
    SELECT author, sum(dl) FILTER (WHERE m = DATE '{M0}') AS mar25, sum(dl) FILTER (WHERE m = DATE '2025-09-01') AS sep25,
      sum(dl) FILTER (WHERE m = DATE '2026-03-01') AS mar26, sum(dl) FILTER (WHERE m = DATE '{M1}') AS sep26 FROM a GROUP BY 1 ORDER BY sep26 DESC NULLS LAST LIMIT 30""")
out["ds_top_sep26"] = q(f"""SELECT id, dl, modality, pipeline_tag, size, used_by_models, used_by_spaces, likes, created FROM dd JOIN dmeta USING (id) WHERE m = DATE '{M1}' ORDER BY dl DESC LIMIT 40""")
out["ds_risers"] = q(f"""WITH a AS (SELECT id, sum(dl) FILTER (WHERE m BETWEEN DATE '2026-07-01' AND DATE '{M1}') AS now, sum(dl) FILTER (WHERE m BETWEEN DATE '2025-07-01' AND DATE '2025-09-01') AS ago FROM dd GROUP BY id)
    SELECT id, now, ago, modality, pipeline_tag, created FROM a JOIN dmeta USING (id) WHERE now > 0 ORDER BY now - coalesce(ago, 0) DESC LIMIT 30""")
# robotics: LeRobot-format datasets, created per month and their downloads
out["ds_robotics"] = q("""SELECT date_trunc('month', created)::DATE AS m, count(*) AS created_n, count(*) FILTER (WHERE author = 'lerobot') AS lerobot_org FROM dmeta
    WHERE pipeline_tag = 'robotics' GROUP BY 1 ORDER BY 1""")
out["ds_created"] = q("""SELECT date_trunc('month', created)::DATE AS m, count(*) AS n, count(*) FILTER (WHERE pipeline_tag = 'robotics') AS robotics,
    count(*) FILTER (WHERE modality = 'tabular') AS tabular FROM dmeta WHERE created >= DATE '2022-01-01' GROUP BY 1 ORDER BY 1""")
out["ds_weekday"] = q("""SELECT dayofweek(day) AS wd, median(dl) AS dl FROM (SELECT day, sum(dl) AS dl FROM read_parquet('/data/datasets/hub_series.parquet')
    WHERE day BETWEEN DATE '2025-03-01' AND DATE '2026-09-30' GROUP BY 1) GROUP BY 1 ORDER BY 1""")
out["md_weekday"] = q("""SELECT dayofweek(day) AS wd, median(dl) AS dl FROM (SELECT day, sum(dl) AS dl FROM read_parquet('/data/hub_series.parquet')
    WHERE day BETWEEN DATE '2025-03-01' AND DATE '2026-09-30' GROUP BY 1) GROUP BY 1 ORDER BY 1""")
out["ds_tail"] = q("""SELECT count(*) AS n, count(*) FILTER (WHERE dl30 < 10) AS under10, count(*) FILTER (WHERE dl30 >= 1000000) AS over1m,
    count(*) FILTER (WHERE used_by_models > 0) AS used_by_any_model, count(*) FILTER (WHERE used_by_spaces > 0) AS used_by_any_space FROM dmeta""")

# training data: what models say they were trained on, by the half-year the model was created, weighted by count and by model downloads
print("# training", flush=True)
con.execute(f"CREATE TABLE uses AS SELECT * FROM read_parquet('{D}/uses.parquet')")
out["train_by_half"] = q("""WITH u AS (SELECT dst, year(created) || CASE WHEN month(created) <= 6 THEN 'H1' ELSE 'H2' END AS h FROM uses
      WHERE src_kind = 'model' AND dst_kind = 'dataset' AND created >= DATE '2022-01-01'),
    c AS (SELECT h, dst, count(*) AS n, row_number() OVER (PARTITION BY h ORDER BY count(*) DESC) AS rk, sum(count(*)) OVER (PARTITION BY h) AS tot FROM u GROUP BY 1, 2)
    SELECT h, dst, n, n / tot AS share, rk FROM c WHERE rk <= 8 ORDER BY h, rk""")
out["train_models_per_half"] = q("""SELECT year(created) || CASE WHEN month(created) <= 6 THEN 'H1' ELSE 'H2' END AS h, count(DISTINCT src) AS models, count(*) AS edges
    FROM uses WHERE src_kind = 'model' AND dst_kind = 'dataset' AND created >= DATE '2022-01-01' GROUP BY 1 ORDER BY 1""")
out["train_share_of_models"] = q(f"""SELECT date_trunc('quarter', m.created_at)::DATE AS qtr, count(*) AS models,
    count(*) FILTER (WHERE m.id IN (SELECT src FROM uses WHERE src_kind = 'model' AND dst_kind = 'dataset')) AS declare_data
    FROM read_parquet('{D}/models.parquet') m WHERE m.created_at >= DATE '2022-01-01' GROUP BY 1 ORDER BY 1""")
# downloaded a lot but rarely cited as training data, and the other way round
out["ds_dl_vs_cited"] = q("""SELECT id, dl30, used_by_models, used_by_spaces, modality, pipeline_tag, size FROM dmeta WHERE dl30 >= 300000 ORDER BY dl30 DESC LIMIT 60""")
out["ds_most_cited"] = q("""SELECT id, used_by_models, used_by_spaces, dl30, created FROM dmeta ORDER BY used_by_models DESC NULLS LAST LIMIT 30""")

# ---------------- spaces ----------------
print("# spaces", flush=True)
con.execute(f"""CREATE TABLE smeta AS SELECT id, author, sdk, created_at::DATE AS created, likes, likes_30d, title, emoji, uses FROM read_parquet('{D}/spaces/spaces.parquet')""")
out["sp_new_by_sdk_month"] = q(f"""SELECT date_trunc('month', day)::DATE AS m, sdk, sum(n)::BIGINT AS n FROM read_parquet('{D}/spaces/new_by_sdk.parquet')
    WHERE day >= DATE '2021-06-01' GROUP BY ALL ORDER BY 1""")
con.execute(f"""CREATE TABLE sl AS
    WITH ends AS (SELECT max(day) AS day FROM read_parquet('{D}/spaces/series/*.parquet') GROUP BY date_trunc('month', day)),
    e AS (SELECT id, date_trunc('month', day)::DATE AS m, likes FROM read_parquet('{D}/spaces/series/*.parquet') WHERE day IN (SELECT day FROM ends)),
    x AS (SELECT id, m, likes, lag(likes) OVER (PARTITION BY id ORDER BY m) AS p, lag(m) OVER (PARTITION BY id ORDER BY m) AS pm FROM e)
    SELECT id, m, likes - coalesce(p, 0) AS gained, p IS NULL AS first FROM x""")
out["sp_likes_month"] = q("""SELECT m, sdk, sum(gained) FILTER (WHERE NOT first) AS gained, count(*) FILTER (WHERE first) AS newly_liked
    FROM sl JOIN smeta USING (id) WHERE m >= DATE '2024-09-01' GROUP BY ALL ORDER BY 1""")
out["sp_likes_by_age"] = q("""SELECT m, sum(gained) FILTER (WHERE created >= m - INTERVAL 90 DAY) / sum(gained) AS under90d,
    sum(gained) FILTER (WHERE created < m - INTERVAL 365 DAY) / sum(gained) AS over1y FROM sl JOIN smeta USING (id)
    WHERE m >= DATE '2024-09-01' AND NOT first AND gained > 0 GROUP BY m ORDER BY m""")
out["sp_concentration"] = q("""WITH r AS (SELECT likes, row_number() OVER (ORDER BY likes DESC) AS rk, count(*) OVER () AS n, sum(likes) OVER () AS tot FROM smeta)
    SELECT any_value(n) AS n, any_value(tot) AS likes, sum(likes) FILTER (WHERE rk <= 100) / any_value(tot) AS top100,
      sum(likes) FILTER (WHERE rk <= n * 0.01) / any_value(tot) AS top1pct, count(*) FILTER (WHERE likes = 1) AS one_like,
      count(*) FILTER (WHERE likes >= 1000) AS over1k FROM r""")
out["sp_sdk_stats"] = q("""SELECT sdk, count(*) AS n, median(likes) AS med, avg(likes) AS mean, quantile_cont(likes, 0.99) AS p99,
    sum(likes_30d) AS likes_30d FROM smeta GROUP BY 1 ORDER BY n DESC""")
out["sp_top_30d"] = q("""SELECT id, title, sdk, likes_30d, likes, created FROM smeta ORDER BY likes_30d DESC NULLS LAST LIMIT 25""")
out["sp_models_by_year"] = q("""WITH u AS (SELECT year(created) AS y, dst FROM uses WHERE src_kind = 'space' AND dst_kind = 'model' AND created IS NOT NULL),
    c AS (SELECT y, dst, count(*) AS n, row_number() OVER (PARTITION BY y ORDER BY count(*) DESC) AS rk, sum(count(*)) OVER (PARTITION BY y) AS tot FROM u GROUP BY 1, 2)
    SELECT y, dst, n, n / tot AS share, rk FROM c WHERE rk <= 8 ORDER BY y, rk""")
out["sp_models_by_year_author"] = q("""WITH u AS (SELECT year(created) AS y, split_part(dst, '/', 1) AS org FROM uses WHERE src_kind = 'space' AND dst_kind = 'model' AND created IS NOT NULL),
    c AS (SELECT y, org, count(*) AS n, row_number() OVER (PARTITION BY y ORDER BY count(*) DESC) AS rk, sum(count(*)) OVER (PARTITION BY y) AS tot FROM u GROUP BY 1, 2)
    SELECT y, org, n, n / tot AS share, rk FROM c WHERE rk <= 8 ORDER BY y, rk""")
out["sp_declare_share"] = q("""SELECT year(created) AS y, count(*) AS spaces, count(*) FILTER (WHERE uses > 0) AS declaring FROM smeta GROUP BY 1 ORDER BY 1""")
# do Spaces track downloads? models with the most Spaces vs their downloads
out["sp_models_vs_dl"] = q(f"""WITH s AS (SELECT dst AS id, count(*) AS spaces FROM uses WHERE src_kind = 'space' AND dst_kind = 'model' GROUP BY 1)
    SELECT s.id, s.spaces, m.dl30, m.pipeline_tag FROM s LEFT JOIN read_parquet('{D}/models.parquet') m USING (id) ORDER BY spaces DESC LIMIT 30""")
out["sp_task_of_used_models"] = q(f"""SELECT year(u.created) AS y, coalesce(m.pipeline_tag, 'unknown') AS task, count(*) AS n FROM uses u
    LEFT JOIN read_parquet('{D}/models.parquet') m ON m.id = u.dst WHERE u.src_kind = 'space' AND u.dst_kind = 'model' AND u.created IS NOT NULL GROUP BY ALL ORDER BY 1, 3 DESC""")

json.dump(out, open("/work/analysis_repos.json", "w"), default=str, indent=1)
print("ok", {k: len(v) for k, v in out.items()})
