# Q2: who is frozen on the Aug-Oct 2025 "0.21 plateau" days (orig set).
import polars as pl,numpy as np
sub=pl.read_parquet('/tmp/sub.parquet'); meta=pl.read_parquet('/tmp/submeta.parquet')
o=sub.filter(pl.col('in_orig'))
W=o.filter((pl.col('day')>=pl.date(2025,8,24))&(pl.col('day')<=pl.date(2025,10,18)))
sh=W.group_by('day').agg(pl.len().alias('n'),(pl.col('delta')==0).sum().alias('fz'),(pl.col('delta')==0).mean().alias('sh')).sort('day')
plateau=sh.filter(pl.col('sh')>0.12)['day'].to_list(); non=sh.filter(pl.col('sh')<0.05)['day'].to_list()
print('plateau days',len(plateau),'non-plateau',len(non))
print(sh.with_columns(pl.col('day').dt.strftime('%a').alias('dow')).select('day','dow','n','fz',pl.col('sh').round(3)).to_pandas().to_string())
F=W.filter(pl.col('delta')==0)
cnt=F.group_by('id').agg(pl.len().alias('k'),pl.col('tmed').median().alias('tmed')).sort('k',descending=True)
print('ids ever frozen in window',cnt.height); print(cnt['k'].describe())
# frozen on >= 80% of plateau days
fp=F.filter(pl.col('day').is_in(plateau)).group_by('id').agg(pl.len().alias('kp'))
core=fp.filter(pl.col('kp')>=0.8*len(plateau))
print('plateau-day frozen ids with kp>=80%:',core.height,'of ids frozen on any plateau day',fp.height)
# daily Jaccard between plateau days
sets={d:set(F.filter(pl.col('day')==d)['id'].to_list()) for d in plateau}
js=[len(sets[a]&sets[b])/len(sets[a]|sets[b]) for a,b in zip(plateau,plateau[1:])]
print('mean consecutive-plateau Jaccard',np.mean(js))
# are core ids frozen on non-plateau days?
coreids=core['id'].to_list()
c=W.filter(pl.col('id').is_in(coreids)).group_by('day').agg((pl.col('delta')==0).mean().alias('sh_core'),pl.len().alias('n')).sort('day')
print(c.with_columns(pl.col('day').dt.strftime('%a').alias('dow')).to_pandas().round(3).to_string())
# ratio on following days for core ids (alternation?)
cc=W.filter(pl.col('id').is_in(coreids)).with_columns((pl.col('dd')/pl.col('tmed')).alias('ratio'))
print(cc.group_by('day').agg(pl.col('ratio').median().alias('med_ratio')).sort('day').to_pandas().round(2).T.to_string())
# traits
m=meta.filter(pl.col('id').is_in(coreids))
allo=meta.filter(pl.col('id').is_in(o['id'].unique().to_list()))
for col in ['pipeline_tag','library_name','author','license','is_gguf','base_relation']:
    a=m[col].value_counts(sort=True).head(8).with_columns((pl.col('count')/m.height).round(3).alias('share_core'))
    b=allo[col].value_counts().with_columns((pl.col('count')/allo.height).round(3).alias('share_all')).select(col,'share_all')
    print(a.join(b,on=col,how='left').to_pandas().to_string())
print('first_seen core',m['first_seen'].describe()); print('first_seen all orig',allo['first_seen'].describe())
print('created_at core',m['created_at'].quantile(.1),m['created_at'].median(),m['created_at'].quantile(.9),' all:',allo['created_at'].quantile(.1),allo['created_at'].median(),allo['created_at'].quantile(.9))
print('params core median',m['params'].median(),'all',allo['params'].median())
# size: tmed of core ids during plateau vs others
print('tmed core median',cc['tmed'].median(), 'orig overall tmed median in window',W['tmed'].median())
core.join(meta,on='id').sort('kp',descending=True).select('id','kp','dl30','created_at','pipeline_tag','library_name').head(25).to_pandas().to_string() and print(core.join(meta,on='id').sort('dl30',descending=True).select('id','kp','dl30','created_at','pipeline_tag','library_name').head(25).to_pandas().to_string())
