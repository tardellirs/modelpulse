# Q3/Q4: shape of each candidate stall day, catch-up of the frozen cohort, who keeps counting.
import polars as pl,pandas as pd,numpy as np,datetime as dt,json
pd.set_option('display.width',280);pd.set_option('display.max_rows',500);pd.set_option('display.max_columns',60)
sub=pl.read_parquet('/tmp/sub.parquet'); meta=pl.read_parquet('/tmp/submeta.parquet')
S=pd.read_csv('A_shares.csv',parse_dates=['day']).set_index('day')
days=sorted(sub['day'].unique().to_list()); idx={d:i for i,d in enumerate(days)}
rev=['2025-07-16','2025-08-13','2025-10-01','2025-10-08','2025-11-26','2026-02-11','2026-04-29','2026-06-25','2026-07-29','2026-08-01','2026-08-05','2026-08-12']
usr=['2025-07-23','2025-09-17','2025-11-05','2025-12-17','2026-01-28','2026-05-12','2026-07-08','2026-09-02','2026-06-25','2026-08-01']
cand=sorted({d.date() for d in S.index[(S['t2000_z']>=0.2)]}|{dt.date.fromisoformat(x) for x in rev+usr})
cand=[d for d in cand if d>=dt.date(2025,3,20)]
# hub ratio
h=pd.read_parquet('/tmp/hub.parquet');t=h.groupby('day').dl.sum();t.index=pd.to_datetime(t.index).date
tm=pd.Series(t.values,index=pd.to_datetime(t.index)).rolling(15,center=True,min_periods=5).median()
hub_ratio={d.date():v for d,v in (pd.Series(t.values,index=pd.to_datetime(t.index))/tm).items()}
base=sub.filter(pl.col('tmed')>=2000)
dly=pd.read_csv('daily.csv',parse_dates=['day']).set_index('day'); dly['tr']=dly.tot_t2000/dly.tot_t2000.rolling(15,center=True,min_periods=5).median()
skipd={dt.date.fromisoformat(x) for x in json.load(open('/tmp/meta.json'))['skip_days']}
rows=[];nonfz_rows=[]
half=[]
for D in cand:
    if D not in idx or idx[D]==0: continue
    i=idx[D]; get=lambda k: days[i+k] if 0<=i+k<len(days) else None
    cohort=base.filter(pl.col('day')==D)
    if cohort.height==0: continue
    fr=cohort.filter(pl.col('delta')==0); nf=cohort.filter(pl.col('delta')>0)
    allq={k:(lambda d:(base.filter(pl.col('day')==d).select((pl.col('dd')/pl.col('tmed')).median()).item() if d else np.nan))(days[i+k] if 0<=i+k<len(days) else None) for k in (-1,0,1,2,3)}
    r={'day':D,'skip_win':'Y' if D in skipd else '','tot_ratio':round(dly['tr'].get(pd.Timestamp(D),np.nan),2),**{f'all{k:+d}':round(v,2) for k,v in allq.items()},'dow':D.strftime('%a'),'n':cohort.height,'fz_share':round(fr.height/cohort.height,3),'gap':cohort['g'].median()}
    ids=fr['id'].to_list(); tm_=dict(zip(fr['id'],fr['tmed']))
    for k in (-1,1,2,3):
        d=get(k)
        if d is None: r[f'fz{k:+d}']=np.nan; continue
        c=base.filter((pl.col('day')==d)) if False else sub.filter((pl.col('day')==d)&(pl.col('tmed')>=2000))
        r[f'fz{k:+d}']=round((c['delta']==0).mean(),3) if c.height else np.nan
    # ratio of frozen cohort on following days relative to own trailing median at D
    X=sub.filter(pl.col('id').is_in(ids)).with_columns(pl.col('day').map_elements(lambda x: idx.get(x,-1),return_dtype=pl.Int64).alias('ix'))
    for k in (-1,0,1,2,3):
        d=get(k); 
        if d is None or fr.height<20: r[f'rat{k:+d}']=np.nan; continue
        y=X.filter(pl.col('day')==d).with_columns((pl.col('dd')/pl.col('id').replace_strict(tm_,default=None,return_dtype=pl.Float64)).alias('q'))
        r[f'rat{k:+d}']=round(y['q'].median(),2) if y.height else np.nan
    # cumulative recovery D-1 .. D+k: (dl_all(D+k)-dl_all(D-1)) / (tmed_D * calendar days)
    prev_dl=dict(zip(fr['id'],(fr['dl_all']-fr['delta'])))  # dl_all at D-1
    d0=days[i]-dt.timedelta(days=int(cohort['g'].median()))
    for k in (3,7):
        d=get(k)
        if d is None or fr.height<20: r[f'cum{k}']=np.nan; r[f'any_catch{k}']=np.nan; continue
        y=X.filter(pl.col('day')==d)
        ca=y.with_columns(((pl.col('dl_all')-pl.col('id').replace_strict(prev_dl,default=None,return_dtype=pl.Int64))/(pl.col('id').replace_strict(tm_,default=None,return_dtype=pl.Float64)*((d-d0).days))).alias('c'))
        r[f'cum{k}']=round(ca['c'].median(),2)
        r[f'p10_cum{k}']=round(ca['c'].quantile(.1),2)
    # share of frozen models showing >=1.3x own median on any of D+1..D+3
    anyc=X.filter((pl.col('ix')>=i+1)&(pl.col('ix')<=i+3)).with_columns((pl.col('dd')/pl.col('id').replace_strict(tm_,default=None,return_dtype=pl.Float64)).alias('q')).group_by('id').agg(pl.col('q').max().alias('mq'))
    r['share_catch>=1.3x']=round((anyc['mq']>=1.3).mean(),2) if anyc.height else np.nan
    # first day with >=1.3x
    fd=X.filter((pl.col('ix')>=i+1)&(pl.col('ix')<=i+3)).with_columns((pl.col('dd')/pl.col('id').replace_strict(tm_,default=None,return_dtype=pl.Float64)).alias('q')).filter(pl.col('q')>=1.3).group_by('id').agg(pl.col('ix').min().alias('f'))
    vc=fd['f'].value_counts().sort('f'); r['first_catch_dist(+1/+2/+3)']='/'.join(str(int(vc.filter(pl.col('f')==i+k)['count'].sum())) for k in (1,2,3))
    r['ratio_nonfrozen_D']=round((nf['dd']/nf['tmed']).median(),2) if nf.height else np.nan
    rows.append(r)
R=pd.DataFrame(rows); R.to_csv('A_shapes.csv',index=False); print(R.to_string())
