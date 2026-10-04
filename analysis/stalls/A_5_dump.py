# Dump small subsets of the panel + metadata for local analysis (Q2-Q4).
import polars as pl,duckdb
P=pl.scan_parquet('/work/stalls_A/panel_*.parquet')
top3000=duckdb.sql("select id from '/data/models.parquet' order by dl30 desc limit 3000").pl()['id'].to_list()
orig=(P.filter(pl.col('id').is_in(top3000)).group_by('id').agg(pl.col('dd').median().alias('m')).filter(pl.col('m')>=2000).collect())['id'].to_list()
sub=P.filter((pl.col('tmed')>=500)|pl.col('id').is_in(orig)).with_columns(pl.col('id').is_in(orig).alias('in_orig')).collect()
sub.write_parquet('/work/stalls_A/sub.parquet',compression='zstd'); print(sub.height, sub['id'].n_unique())
ids=sub['id'].unique().to_list()
meta=duckdb.sql("select id,author,pipeline_tag,library_name,created_at,first_seen,license,is_gguf,base_relation,likes,dl30,dl_all,params from '/data/models.parquet'").pl().filter(pl.col('id').is_in(ids))
print(meta.columns); meta.write_parquet('/work/stalls_A/submeta.parquet')
