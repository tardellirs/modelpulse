# weighted (by trailing median) frozen share vs unweighted, t2000 set
import polars as pl,pandas as pd,numpy as np
sub=pl.read_parquet('/tmp/sub.parquet').filter(pl.col('tmed')>=2000)
w=sub.group_by('day').agg(pl.len().alias('n'),(pl.col('delta')==0).mean().alias('share'),((pl.col('delta')==0).cast(pl.Float64)*pl.col('tmed')).sum().alias('fw'),pl.col('tmed').sum().alias('tw'),(pl.col('dd').sum()/pl.col('tmed').sum()).alias('set_ratio')).with_columns((pl.col('fw')/pl.col('tw')).alias('wshare')).sort('day').to_pandas().set_index('day')
w.index=pd.to_datetime(w.index); w=w[w.index>='2025-03-20']
w[['n','share','wshare','set_ratio']].round(3).to_csv('A_weighted.csv')
x=w.wshare; print('weighted share bins <1%',(x<.01).sum(),'1-5',((x>=.01)&(x<.05)).sum(),'5-25',((x>=.05)&(x<.25)).sum(),'25-90',((x>=.25)&(x<.9)).sum(),'>=90',(x>=.9).sum())
print(x[(x>=.05)].round(3).to_string())
print(np.round(np.sort(x[x>=.05].values),2))
