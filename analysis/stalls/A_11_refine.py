# Refinement: count a model as frozen only if it was moving on the previous snapshot (delta_prev>0) -> kills cohort-ending artefacts
import polars as pl,pandas as pd
sub=pl.read_parquet('/tmp/sub.parquet').sort('id','day')
sub=sub.with_columns(pl.col('delta').shift(1).over('id').alias('pdelta'),pl.col('day').shift(1).over('id').alias('pd'))
days=sorted(sub['day'].unique().to_list()); prev={b:a for a,b in zip(days,days[1:])}
sub=sub.with_columns((pl.col('pd')==pl.col('day').replace_strict(prev,default=None,return_dtype=pl.Date)).alias('consec'))
s=sub.filter((pl.col('tmed')>=2000)&pl.col('consec')&(pl.col('pdelta')>0))
w=s.group_by('day').agg((pl.col('delta')==0).mean().alias('refined')).sort('day').to_pandas().set_index('day'); w.index=pd.to_datetime(w.index)
o=pd.read_csv('A_shares.csv',parse_dates=['day']).set_index('day')['t2000_z']
w['t2000_z']=o; w=w[w.index>='2025-03-20']
w.round(3).to_csv('A_refined.csv')
print(w.loc['2025-07-26':'2025-08-04'].round(3)); print(w.loc['2025-09-14':'2025-09-19'].round(3)); print(w.loc['2025-05-02':'2025-05-06'].round(3));print(w.loc['2025-12-09':'2025-12-12'].round(3))
x=w.refined; print('refined bins <1%',(x<.01).sum(),'1-5',((x>=.01)&(x<.05)).sum(),'5-25',((x>=.05)&(x<.25)).sum(),'25-90',((x>=.25)&(x<.9)).sum(),'>=90',(x>=.9).sum())
print(x[(x>=.05)&(x<.3)].round(3).to_dict())
