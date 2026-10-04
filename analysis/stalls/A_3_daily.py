# Daily frozen-share under many model-set / frozen-definition variants -> daily.csv
import polars as pl,duckdb,glob
P=pl.scan_parquet('/work/stalls_A/panel_*.parquet')
# per-day dl30 cutoffs for fixed top-N sets
cut=(P.select('day','dl30').group_by('day').agg(pl.col('dl30').sort(descending=True).gather([499,2499,9999]).alias('c')).collect())
cut=cut.with_columns(pl.col('c').list.get(0).alias('c500'),pl.col('c').list.get(1).alias('c2500'),pl.col('c').list.get(2).alias('c10000')).drop('c')
top3000=duckdb.sql("select id from '/data/models.parquet' order by dl30 desc limit 3000").pl()['id'].to_list()
# survivor-biased original: whole-history median of dd >= 2000 among current top 3000
orig=(P.filter(pl.col('id').is_in(top3000)).group_by('id').agg(pl.col('dd').median().alias('m')).filter(pl.col('m')>=2000).collect())
print('orig set size',orig.height,flush=True)
oset=orig['id'].to_list()
o2=(P.filter(pl.col('id').is_in(top3000)).group_by('id').agg(pl.col('dl30').median().alias('m')).filter(pl.col('m')>=2000).collect())
print('orig2 (median dl30>=2000) size',o2.height,flush=True)
o2set=o2['id'].to_list()
sets={'t500':pl.col('tmed')>=500,'t2000':pl.col('tmed')>=2000,'t10000':pl.col('tmed')>=10000,
      'r500':pl.col('dl30')>=pl.col('c500'),'r2500':pl.col('dl30')>=pl.col('c2500'),'r10000':pl.col('dl30')>=pl.col('c10000'),
      'orig':pl.col('id').is_in(oset),'orig2':pl.col('id').is_in(o2set)}
fz={'z':pl.col('delta')==0,'p5':(pl.col('delta')==0)|(pl.col('tmed').is_not_null()&(pl.col('dd')<0.05*pl.col('tmed')))}
aggs=[]
for sn,se in sets.items():
    for fn,fe in fz.items():
        ok=pl.col('tmed').is_not_null() if fn=='p5' else pl.lit(True)
        m=se&ok
        aggs+= [m.sum().alias(f'n_{sn}_{fn}'),(m&fe).sum().alias(f'f_{sn}_{fn}')]
# totals of normalised delta in t2000 set (for own ratio)
aggs+=[pl.col('dd').filter(pl.col('tmed')>=2000).sum().alias('tot_t2000'),pl.col('g').max().alias('gmax'),pl.col('g').median().alias('gmed')]
out=P.join(cut.lazy(),on='day').group_by('day').agg(aggs).sort('day').collect(engine='streaming') if False else None
# process month by month to bound memory
res=[]
days=sorted(P.select('day').unique().collect()['day'].to_list())
months=sorted({(d.year,d.month) for d in days})
for y,mo in months:
    d=P.filter((pl.col('day').dt.year()==y)&(pl.col('day').dt.month()==mo)).join(cut.lazy(),on='day')
    res.append(d.group_by('day').agg(aggs).collect()); print(y,mo,flush=True)
pl.concat(res).sort('day').write_csv('/work/stalls_A/daily.csv')
