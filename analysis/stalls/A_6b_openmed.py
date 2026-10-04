# Q2 follow-up: the OpenMed cohort -- when does it exist, when frozen, what do its deltas look like.
import polars as pl,numpy as np
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(20)
sub=pl.read_parquet('/tmp/sub.parquet'); meta=pl.read_parquet('/tmp/submeta.parquet')
om=meta.filter(pl.col('id').str.starts_with('OpenMed/OpenMed-NER'))['id'].to_list()
print('OpenMed-NER ids in subset',len(om))
o=sub.filter(pl.col('id').is_in(om))
w=o.with_columns(pl.col('day').dt.truncate('1w').alias('wk')).group_by('wk').agg(pl.col('id').n_unique().alias('n'),(pl.col('delta')==0).mean().alias('fz'),pl.col('dd').median().alias('med_dd'),pl.col('dd').sum().alias('sum_dd')).sort('wk')
print(w)
d=o.filter((pl.col('day')>=pl.date(2025,7,10))&(pl.col('day')<=pl.date(2025,11,10))).group_by('day').agg(pl.len().alias('n'),(pl.col('delta')==0).mean().alias('fz'),pl.col('dd').median().alias('med_dd'),pl.col('dd').max().alias('max_dd'),pl.col('dd').sum().alias('sum_dd')).sort('day')
print(d)
