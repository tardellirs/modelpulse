"""Exploratory statistics for the Model Pulse launch article. Writes /work/analysis.json.

Run inside the API image:  docker run --rm --memory 6g -v /opt/modelpulse/data:/data -v /opt/modelpulse/work:/work \
    -v $PWD:/a modelpulse-api python /a/explore.py
"""
import json
import os

import duckdb
import polars as pl

import monthly

D = "/data"
os.makedirs("/work/duck_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET memory_limit='5GB'; SET threads=3; SET temp_directory='/work/duck_tmp'; SET preserve_insertion_order=false")
q = lambda sql: con.execute(sql).pl()
out = {}

con.execute(f"""CREATE TABLE meta AS SELECT id, author, pipeline_tag, library_name, created_at::DATE AS created, params,
    base_relation, is_gguf, likes, dl30, dl_all, fam_members FROM read_parquet('{D}/models.parquet')""")

# ---- monthly downloads per model, between month boundaries (see monthly.py): exact from Mar 2025, estimated before ----
M = json.load(open(f"{D}/meta.json"))
monthly.build(con, "md", f"{D}/series/*.parquet", M["days"], M["skip_days"], "meta")
out["months"] = q("SELECT m, sum(dl) AS dl, sum(dl_est) AS dl_est, bool_and(exact) AS exact, count(*) FILTER (WHERE dl > 0) AS active FROM md GROUP BY m ORDER BY m").to_dicts()

print("# 1. concentration", flush=True)
# 1. concentration
conc = q("""WITH r AS (SELECT m, dl, row_number() OVER (PARTITION BY m ORDER BY dl DESC) AS rk,
                count(*) OVER (PARTITION BY m) AS n, sum(dl) OVER (PARTITION BY m) AS tot FROM md WHERE dl > 0)
    SELECT m, any_value(n) AS n_active,
      sum(dl) FILTER (WHERE rk <= 10) / any_value(tot) AS top10,
      sum(dl) FILTER (WHERE rk <= 100) / any_value(tot) AS top100,
      sum(dl) FILTER (WHERE rk <= 1000) / any_value(tot) AS top1000,
      sum(dl) FILTER (WHERE rk <= n * 0.01) / any_value(tot) AS top1pct
    FROM r GROUP BY m ORDER BY m""")
out["concentration"] = conc.to_dicts()
out["tail_sep26"] = q("""SELECT count(*) AS models,
    count(*) FILTER (WHERE dl < 10) AS under10, count(*) FILTER (WHERE dl < 100) AS under100,
    count(*) FILTER (WHERE dl >= 1000000) AS over1m FROM md WHERE m = DATE '2026-09-01'""").to_dicts()
out["total_models_hub"] = q(f"SELECT count(*) AS n FROM read_parquet('{D}/models.parquet')").to_dicts()

print("# 2. derivatives", flush=True)
# 2. derivatives, gguf, quantizers
out["derivative_share"] = q("""SELECT m, sum(dl) FILTER (WHERE base_relation IS NOT NULL) / sum(dl) AS derived,
    sum(dl) FILTER (WHERE base_relation = 'quantized') / sum(dl) AS quantized,
    sum(dl) FILTER (WHERE base_relation = 'finetune') / sum(dl) AS finetune,
    sum(dl) FILTER (WHERE is_gguf) / sum(dl) AS gguf,
    sum(dl) FILTER (WHERE pipeline_tag = 'text-generation' AND base_relation IS NOT NULL)
      / sum(dl) FILTER (WHERE pipeline_tag = 'text-generation') AS textgen_derived
    FROM md JOIN meta USING (id) GROUP BY m ORDER BY m""").to_dicts()
quantizers = ["bartowski", "unsloth", "mradermacher", "lmstudio-community", "TheBloke", "QuantFactory", "MaziyarPanahi", "ggml-org", "mlx-community"]
out["quantizers"] = q(f"""SELECT author, m, sum(dl) AS dl, count(*) FILTER (WHERE dl > 0) AS models FROM md JOIN meta USING (id)
    WHERE author IN ({",".join(repr(a) for a in quantizers)}) GROUP BY 1, 2 ORDER BY 1, 2""").to_dicts()
out["top_authors_total"] = q("""SELECT author, sum(dl) AS dl FROM md JOIN meta USING (id) WHERE m >= DATE '2026-04-01'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 25""").to_dicts()

print("# 3. text-generation", flush=True)
# 3. text-generation by org
out["textgen_orgs"] = q("""WITH t AS (SELECT m, author, sum(dl) AS dl FROM md JOIN meta USING (id)
        WHERE pipeline_tag IN ('text-generation', 'image-text-to-text') GROUP BY 1, 2)
    SELECT * FROM (SELECT m, author, dl, dl / sum(dl) OVER (PARTITION BY m) AS share FROM t)
    WHERE author IN ('Qwen', 'meta-llama', 'google', 'deepseek-ai', 'mistralai', 'microsoft', 'openai', 'unsloth', 'bartowski',
                     'HuggingFaceTB', 'nvidia', 'ibm-granite', 'moonshotai', 'zai-org', 'THUDM', 'tencent', 'baidu', 'mradermacher', 'lmstudio-community')
    ORDER BY m, dl DESC""").to_dicts()
# family-level: downloads of anything descending from each org's base models (Qwen ecosystem incl. derivatives)
out["textgen_top_models_sep26"] = q("""SELECT id, dl FROM md JOIN meta USING (id) WHERE m = DATE '2026-09-01'
    AND pipeline_tag IN ('text-generation', 'image-text-to-text') ORDER BY dl DESC LIMIT 20""").to_dicts()

print("# 4. age", flush=True)
# 4. age of what people download
out["age_mix"] = q("""SELECT m, CASE WHEN created < DATE '2022-01-01' THEN 'before 2022'
        WHEN created < DATE '2023-01-01' THEN '2022' WHEN created < DATE '2024-01-01' THEN '2023'
        WHEN created < DATE '2025-01-01' THEN '2024' WHEN created < DATE '2026-01-01' THEN '2025' ELSE '2026' END AS cohort,
      sum(dl) AS dl FROM md JOIN meta USING (id) GROUP BY 1, 2 ORDER BY 1, 2""").to_dicts()
out["oldest_in_top50_sep26"] = q("""SELECT id, created, dl FROM md JOIN meta USING (id) WHERE m = DATE '2026-09-01'
    ORDER BY dl DESC LIMIT 50""").to_dicts()

print("# 5. libraries", flush=True)
# 5. libraries
out["libraries"] = q("""WITH t AS (SELECT m, coalesce(library_name, 'none') AS lib, sum(dl) AS dl FROM md JOIN meta USING (id) GROUP BY 1, 2)
    SELECT * FROM (SELECT m, lib, dl, dl / sum(dl) OVER (PARTITION BY m) AS share FROM t)
    WHERE lib IN ('transformers', 'sentence-transformers', 'gguf', 'diffusers', 'mlx', 'timm', 'open_clip', 'onnx', 'transformers.js',
                  'peft', 'nemo', 'pyannote-audio', 'none', 'vllm', 'llama.cpp')
    ORDER BY m, dl DESC""").to_dicts()

print("# 6. model size", flush=True)
# 6. model size, downloads-weighted, text generation with known params
out["params"] = q("""SELECT m, quantile_cont(params, 0.5) AS unweighted_median,
      sum(dl * ln(params)) / sum(dl) AS w_logmean,
      sum(dl) FILTER (WHERE params < 2e9) / sum(dl) AS under2b, sum(dl) FILTER (WHERE params >= 2e9 AND params < 10e9) / sum(dl) AS b2_10,
      sum(dl) FILTER (WHERE params >= 10e9 AND params < 40e9) / sum(dl) AS b10_40, sum(dl) FILTER (WHERE params >= 40e9) / sum(dl) AS over40b
    FROM md JOIN meta USING (id) WHERE pipeline_tag = 'text-generation' AND params > 1e7 AND dl > 0 GROUP BY m ORDER BY m""").to_dicts()

print("# 7. likes", flush=True)
# 7. likes vs downloads
lv = q("""SELECT id, likes, dl30, author, pipeline_tag FROM meta WHERE dl30 >= 1000 AND likes IS NOT NULL""")
out["likes_downloads_spearman"] = float(lv.select(pl.corr(pl.col("likes").rank(), pl.col("dl30").rank())).item())
out["unloved_workhorses"] = lv.sort("dl30", descending=True).filter(pl.col("likes") < 50).head(10).to_dicts()
out["loved_unused"] = lv.filter(pl.col("dl30") < 5000).sort("likes", descending=True).head(10).to_dicts()
out["likes_per_100k"] = q("""SELECT pipeline_tag, sum(likes) * 1e5 / sum(dl30) AS likes_per_100k, sum(dl30) AS dl30
    FROM meta WHERE dl30 > 0 AND pipeline_tag IS NOT NULL GROUP BY 1 HAVING sum(dl30) > 5e6 ORDER BY 2 DESC""").to_dicts()

print("# 8. race", flush=True)
# 8. race to 1M (models created after all-time totals exist)
race = q(f"""SELECT s.id, min(s.day) AS day1m, any_value(meta.created) AS created, any_value(meta.author) AS author
    FROM read_parquet('{D}/series/*.parquet') s JOIN meta USING (id)
    WHERE s.dl_all >= 1000000 AND meta.created >= DATE '2025-03-01' GROUP BY s.id""")
race = race.with_columns((pl.col("day1m") - pl.col("created")).dt.total_days().alias("days")).sort("days")
out["race_1m_count"] = race.height
out["race_1m_fastest"] = race.head(25).to_dicts()
out["race_1m_median_days"] = float(race["days"].median())

# 9. lifecycle of releases: weekly downloads after creation, for models created Mar 2025 - Mar 2026 that reached 100k in 6 months
con.execute("""CREATE TABLE coh AS SELECT id, created FROM meta
    WHERE created BETWEEN DATE '2025-03-01' AND DATE '2026-03-31' AND dl_all >= 100000""")
con.execute(f"""CREATE TABLE life AS SELECT s.id, ((s.day - c.created) // 7)::INT AS wk, max(s.dl_all) AS cum, max(s.day - c.created) AS age
    FROM read_parquet('{D}/series/*.parquet') s JOIN coh c USING (id)
    WHERE s.dl_all IS NOT NULL AND (s.day - c.created) BETWEEN 0 AND 181 GROUP BY 1, 2""")
life = q("SELECT * FROM life")
print("life rows", life.height, flush=True)
keep = life.group_by("id").agg(pl.col("cum").max().alias("t182"), pl.col("age").max().alias("maxage")) \
    .filter((pl.col("t182") >= 100_000) & (pl.col("maxage") >= 175))
wk = (life.join(keep.select("id", "t182"), on="id").pivot(on="wk", index=["id", "t182"], values="cum").sort("id"))
cols = [str(w) for w in range(26) if str(w) in wk.columns]
# missing weeks (snapshot gaps) are interpolated; leading gaps count as 0
wk = wk.with_columns(pl.concat_list([pl.col(c) for c in cols]).alias("v")).select("id", "t182", "v")
rows = []
for r in wk.iter_rows(named=True):
    v = list(r["v"])
    known = [i for i, x in enumerate(v) if x is not None]
    for i in range(len(v)):
        if v[i] is None:
            lo = max((k for k in known if k < i), default=None); hi = min((k for k in known if k > i), default=None)
            v[i] = 0 if lo is None else v[lo] if hi is None else v[lo] + (v[hi] - v[lo]) * (i - lo) / (hi - lo)
    inc = [max(0, v[i] - (v[i - 1] if i else 0)) for i in range(len(v))]
    tot = sum(inc) or 1
    rows.append({"share": [x / tot for x in inc], "peak": max(range(len(inc)), key=inc.__getitem__),
                 "first30": (sum(inc[:4]) + inc[4] * 2 / 7 if len(inc) > 4 else sum(inc)) / tot})
import statistics as st
n = len(rows)
out["lifecycle"] = {
    "models": n,
    "median_share_first_30d": st.median(r["first30"] for r in rows),
    "median_weekly_share": [st.median(r["share"][i] for r in rows) for i in range(len(cols))],
    "mean_weekly_share": [sum(r["share"][i] for r in rows) / n for i in range(len(cols))],
    "median_peak_week": st.median(r["peak"] for r in rows),
    "peak_in_first_week": sum(r["peak"] == 0 for r in rows) / n,
    "peak_after_month3": sum(r["peak"] >= 13 for r in rows) / n,
}
print("lifecycle done", flush=True)

print("# 10. weekday", flush=True)
# 10. weekday vs weekend by task (automation index)
hub = q(f"SELECT day, pipeline_tag, dl FROM read_parquet('{D}/hub_series.parquet') WHERE day BETWEEN DATE '2025-03-01' AND DATE '2026-09-30'")
hub = hub.with_columns(pl.col("day").dt.weekday().alias("wd"))
tags = hub.group_by("pipeline_tag").agg(pl.col("dl").sum()).sort("dl", descending=True).head(12)["pipeline_tag"].to_list()
wkd = []
for t in tags + ["__all__"]:
    h = hub if t == "__all__" else hub.filter(pl.col("pipeline_tag") == t)
    h = h.group_by("day", "wd").agg(pl.col("dl").sum())
    by = h.group_by("wd").agg(pl.col("dl").median()).sort("wd")
    mid = by.filter(pl.col("wd").is_in([2, 3, 4]))["dl"].mean()
    wkend = by.filter(pl.col("wd").is_in([6, 7]))["dl"].mean()
    wkd.append({"tag": t, "weekday_over_weekend": mid / wkend if wkend else None, "by_weekday": by.to_dicts()})
out["weekday"] = wkd

json.dump(out, open("/work/analysis.json", "w"), default=str, indent=1)
print("ok", {k: (len(v) if isinstance(v, list) else "·") for k, v in out.items()})
