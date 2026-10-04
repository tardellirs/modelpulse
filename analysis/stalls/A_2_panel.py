# Build per-model/day delta panel with trailing medians (polars, hash-bucketed to stay under the memory cap).
import polars as pl,os,glob
for f in glob.glob('/work/stalls_A/panel*.parquet'): os.remove(f)
NB=8
lf=pl.scan_parquet('/work/stalls_A/cand.parquet')
for k in range(NB):
    d=(lf.filter(pl.col('id').hash()%NB==k).sort('id','day').collect())
    d=d.with_columns(pl.col('dl_all').shift(1).over('id').alias('pdl'),pl.col('day').shift(1).over('id').alias('pday')).filter(pl.col('pday').is_not_null())
    d=d.with_columns((pl.col('day')-pl.col('pday')).dt.total_days().alias('g'),(pl.col('dl_all')-pl.col('pdl')).alias('delta'))
    d=d.with_columns((pl.col('delta')/pl.col('g')).alias('dd'))
    d=d.with_columns(pl.col('dd').shift(1).rolling_median(14,min_samples=7).over('id').alias('tmed'))
    d.select('id','day','dl30','dl_all','g','delta','dd','tmed').write_parquet(f'/work/stalls_A/panel_{k:02d}.parquet',compression='zstd')
    print(k,d.height,flush=True)
x=pl.scan_parquet('/work/stalls_A/panel_*.parquet')
print(x.select(pl.len(),(pl.col('delta')<0).sum().alias('neg'),(pl.col('delta')==0).sum().alias('zero'),pl.col('g').median(),pl.col('g').max()).collect())
