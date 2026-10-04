import json, duckdb
import monthly
D="/data"
con=duckdb.connect(); con.execute("SET memory_limit='5GB'; SET threads=3; SET temp_directory='/work/duck_tmp'")
q=lambda sql:[dict(zip([c[0] for c in r.description],row)) for r in [con.execute(sql)] for row in r.fetchall()]
out={}
con.execute(f"CREATE TABLE uses AS SELECT * FROM read_parquet('{D}/uses.parquet')")
con.execute(f"CREATE TABLE dmeta AS SELECT * FROM read_parquet('{D}/datasets/datasets.parquet')")
# training data counted by distinct model authors, so one account mass-producing models counts once
out["train_by_year_authors"]=q("""WITH u AS (SELECT year(created) AS y, dst, split_part(src,'/',1) AS a FROM uses WHERE src_kind='model' AND dst_kind='dataset' AND created>=DATE '2022-01-01'),
  c AS (SELECT y, dst, count(DISTINCT a) AS authors, row_number() OVER (PARTITION BY y ORDER BY count(DISTINCT a) DESC) AS rk FROM u GROUP BY 1,2),
  t AS (SELECT y, count(DISTINCT a) AS tot FROM u GROUP BY 1)
  SELECT y, dst, authors, authors/tot AS share, rk FROM c JOIN t USING (y) WHERE rk<=12 ORDER BY y, rk""")
# themes of declared training data over time (by distinct authors)
out["train_themes"]=q("""WITH u AS (SELECT year(created) AS y, lower(dst) AS d, split_part(src,'/',1) AS a FROM uses WHERE src_kind='model' AND dst_kind='dataset' AND created>=DATE '2022-01-01')
  SELECT y, count(DISTINCT a) AS authors,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(math|gsm8k|numina|metamath)')) AS math,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(ultrafeedback|dpo|orpo|preference|hh-rlhf|helpsteer)')) AS preference,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(deepseek-r1|openr1|open-r1|thought|reasoning|[-_/]cot|cot[-_]|distill)')) AS reasoning,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(code|starcoder|the-stack)')) AS code,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(common_voice|fleurs|librispeech|gtzan|speech)')) AS speech,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(fineweb|^c4$|/c4$|pile|wikipedia|dclm|redpajama|oscar|madlad)')) AS web,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(^|/)(glue|imdb|emotion|squad|squad_v2|tweet_eval|sst2|conll2003|xtreme|ag_news|yelp_review_full)$')) AS classic_nlp,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(alpaca|dolly|oasst|ultrachat|openhermes|orca|sharegpt|tulu|capybara)')) AS chat_sft,
   count(DISTINCT a) FILTER (WHERE regexp_matches(d, '(opus|claude|gpt-4|gpt4|gemini|gpt-5)')) AS closed_distill
  FROM u GROUP BY 1 ORDER BY 1""")
# datasets with no card metadata at all (no modality, size, task): a proxy for file storage rather than ML data
RM = json.load(open(f"{D}/repos_meta.json"))
con.execute("CREATE TABLE dcreated AS SELECT id, created_at::DATE AS created FROM dmeta")
monthly.build(con, "dd", f"{D}/datasets/series/*.parquet", RM["datasets_days"], RM["skip_days"], "dcreated")
out["ds_kinds_month"]=q("""SELECT m, sum(dl) AS dl,
   sum(dl) FILTER (WHERE modality IS NULL AND size IS NULL AND pipeline_tag IS NULL) AS bare,
   sum(dl) FILTER (WHERE pipeline_tag='robotics') AS robotics,
   sum(dl) FILTER (WHERE used_by_models>0) AS cited,
   sum(dl) FILTER (WHERE author IN ('huggingface','hf-internal-testing','hf-doc-build','HuggingFaceM4','HuggingFaceFW','HuggingFaceTB','HuggingFaceH4','open-r1','lerobot')) AS hf_orgs,
   sum(dl) FILTER (WHERE created_at >= m - INTERVAL 180 DAY) AS young
  FROM dd JOIN dmeta USING (id) GROUP BY m ORDER BY m""")
out["robotics_authors"]=q("""SELECT date_trunc('quarter', created_at)::DATE AS q, count(*) AS n, count(DISTINCT author) AS authors FROM dmeta WHERE pipeline_tag='robotics' AND created_at>=DATE '2024-07-01' GROUP BY 1 ORDER BY 1""")
out["robotics_top"]=q("""SELECT id, sum(dl) AS dl FROM dd JOIN dmeta USING (id) WHERE pipeline_tag='robotics' AND m>=DATE '2026-07-01' GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")
out["robotics_conc"]=q("""SELECT count(*) FILTER (WHERE dl30 < 10) AS under10, count(*) AS n, median(dl30) AS med FROM dmeta WHERE pipeline_tag='robotics'""")
out["sp_created_month"]=q(f"SELECT date_trunc('month', day)::DATE AS m, sum(n)::BIGINT AS n FROM read_parquet('{D}/spaces/new_by_sdk.parquet') WHERE day>=DATE '2025-06-01' GROUP BY 1 ORDER BY 1")
# Spaces likes: daily total of all likes on tracked Spaces, sampled monthly
out["sp_total_likes"]=q(f"""WITH ends AS (SELECT max(day) AS day FROM read_parquet('{D}/spaces/series/*.parquet') GROUP BY date_trunc('month', day))
  SELECT day, sum(likes) AS likes, count(*) AS spaces FROM read_parquet('{D}/spaces/series/*.parquet') WHERE day IN (SELECT day FROM ends) GROUP BY 1 ORDER BY 1""")
json.dump(out, open("/work/analysis_repos2.json","w"), default=str, indent=1); print("ok")
