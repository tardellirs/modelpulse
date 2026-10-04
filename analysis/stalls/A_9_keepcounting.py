# Q3: who keeps counting on half-stall days (t2000 set, frozen share 0.25-0.9)
import polars as pl,pandas as pd,numpy as np,itertools
pd.set_option('display.width',250);pd.set_option('display.max_rows',200)
sub=pl.read_parquet('/tmp/sub.parquet').filter(pl.col('tmed')>=2000); meta=pl.read_parquet('/tmp/submeta.parquet')
S=pd.read_csv('A_shares.csv',parse_dates=['day']).set_index('day'); S=S[S.index>='2025-03-20']
half=[d.date() for d in S.index[(S['t2000_z']>=0.25)&(S['t2000_z']<0.9)]]
# exclude days that are inside the skip windows (their frozen share is not a 'half' event) and the one with OpenMed cohort artefact
print('half days',len(half),half)
H=sub.filter(pl.col('day').is_in(half)).join(meta,on='id',how='left').with_columns((pl.col('delta')>0).alias('nf'),(pl.col('dd')/pl.col('tmed')).alias('q'))
per=H.group_by('id').agg(pl.len().alias('k'),pl.col('nf').sum().alias('nnf'),pl.col('q').filter(pl.col('nf')).median().alias('q_nf'),pl.col('tmed').median().alias('tmed')).with_columns((pl.col('nnf')/pl.col('k')).alias('rate'))
print('models x half-days',H.height,'distinct models',per.height)
print('overall non-frozen rate on half days',round(H['nf'].mean(),3))
pr=per.filter(pl.col('k')>=5)
print(pr['rate'].to_pandas().describe()); print('rate histogram (k>=5):',np.histogram(pr['rate'].to_numpy(),bins=[0,.05,.2,.4,.6,.8,.95,1.01])[0])
always=pr.filter(pl.col('rate')>=0.8).join(meta,on='id').sort('tmed',descending=True)
never=pr.filter(pl.col('rate')<=0.1)
print('k>=5 models',pr.height,'always counting (>=80%)',always.height,'never counting (<=10%)',never.height)
print(always.select('id','k','rate','q_nf','tmed','library_name','pipeline_tag').head(40).to_pandas().to_string())
# traits: nonfrozen rate by category
for col in ['library_name','pipeline_tag','is_gguf','base_relation','license']:
    g=H.group_by(col).agg(pl.len().alias('n'),pl.col('nf').mean().alias('nf_rate'),pl.col('id').n_unique().alias('models')).filter(pl.col('n')>=100).sort('n',descending=True).head(10)
    print(g.to_pandas().round(3).to_string())
H=H.with_columns(pl.col('author').fill_null('').alias('au'))
g=H.group_by('au').agg(pl.len().alias('n'),pl.col('nf').mean().alias('nf_rate'),pl.col('id').n_unique().alias('models')).filter(pl.col('n')>=150).sort('nf_rate',descending=True)
print(g.head(15).to_pandas().round(3).to_string())
# size effect: tmed deciles
H=H.with_columns(pl.col('tmed').qcut(6,labels=list('abcdef')).alias('tq'))
print(H.group_by('tq').agg(pl.col('tmed').min().alias('lo'),pl.col('tmed').max().alias('hi'),pl.col('nf').mean().round(3).alias('nf_rate')).sort('lo').to_pandas().to_string())
# stability: Jaccard of non-frozen sets between pairs of half days
sets={d:set(H.filter((pl.col('day')==d)&pl.col('nf'))['id'].to_list()) for d in half}
pres={d:set(H.filter(pl.col('day')==d)['id'].to_list()) for d in half}
js=[]
for a,b in itertools.combinations(half,2):
    c=pres[a]&pres[b]; A=sets[a]&c; B=sets[b]&c
    if A|B: js.append(len(A&B)/len(A|B))
print('pairwise Jaccard of non-frozen sets (common models): mean %.2f median %.2f'%(np.mean(js),np.median(js)))
# expected Jaccard under independence given rates
# ratio on counting models
print('median ratio dd/tmed of non-frozen on half days',round(H.filter(pl.col('nf'))['q'].median(),2))
# named examples
for m in ['sentence-transformers/all-MiniLM-L6-v2','BAAI/bge-small-en-v1.5','BAAI/bge-m3','amazon/chronos-2','Comfy-Org/MiniMax-H3','google-bert/bert-base-uncased','openai/clip-vit-base-patch32']:
    r=per.filter(pl.col('id')==m); print(m, r.select('k','nnf','q_nf').rows())
# top always-counting by traits
print(always['library_name'].value_counts(sort=True).head(8).to_pandas().to_string()); print(always['pipeline_tag'].value_counts(sort=True).head(8).to_pandas().to_string())
print(always['author'].value_counts(sort=True).head(10).to_pandas().to_string())
# age and size traits
nev=never.join(meta,on='id')
for name,x in [('always(>=80% counting)',always),('never(<=10%)',nev)]:
    p=x.to_pandas(); ca=pd.to_datetime(p['created_at'])
    print(name,len(p),'created_at q25/med/q75',ca.quantile(.25).date(),ca.median().date(),ca.quantile(.75).date(),'| median params',p['params'].median(),'| share created before 2024-01-01 %.2f'%(ca<'2024-01-01').mean(),'| share gguf %.2f'%p['is_gguf'].fillna(False).astype(bool).mean(),'| share with base_relation %.2f'%p['base_relation'].notna().mean())
print(nev['library_name'].value_counts(sort=True).head(6).to_pandas().to_string()); print(nev['pipeline_tag'].value_counts(sort=True).head(6).to_pandas().to_string())
print(nev['author'].value_counts(sort=True).head(8).to_pandas().to_string())
# non-frozen rate by creation period
p=H.select('id','nf','created_at','tmed').to_pandas(); p['cq']=pd.to_datetime(p['created_at']).dt.to_period('Q').astype(str)
p.loc[pd.to_datetime(p['created_at'])<'2022-03-03','cq']='<=2022-03-02'
g=p.groupby('cq').agg(n=('nf','size'),models=('id','nunique'),nf_rate=('nf','mean')).round(3)
print(g.to_string())
