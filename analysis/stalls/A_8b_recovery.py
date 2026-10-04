# Q4 extra: cumulative recovery of frozen cohort vs non-frozen control over D-1..D+k (k=3,7,14 snapshot days), median of dl_all gain / (trailing median * calendar days)
import polars as pl,pandas as pd,numpy as np,datetime as dt
pd.set_option('display.width',200)
suba=pl.read_parquet('/tmp/sub.parquet'); sub=suba.filter(pl.col('tmed')>=2000)
S=pd.read_csv('A_shapes.csv',parse_dates=['day'])
days=sorted(sub['day'].unique().to_list()); idx={d:i for i,d in enumerate(days)}
out=[]
for D in [d.date() for d in S.loc[S.fz_share>=0.25,'day']]:
    i=idx[D]; c=sub.filter(pl.col('day')==D)
    d0=D-dt.timedelta(days=int(c['g'].median()))
    c=c.with_columns((pl.col('dl_all')-pl.col('delta')).alias('dl0'))
    r={'day':D}
    for name,coh in [('fz',c.filter(pl.col('delta')==0)),('nf',c.filter(pl.col('delta')>0))]:
        for k in (3,7,14):
            if i+k>=len(days): r[f'{name}{k}']=np.nan; continue
            d=days[i+k]; e=suba.filter(pl.col('day')==d).select('id',pl.col('dl_all').alias('dlk'))
            j=coh.join(e,on='id'); q=((j['dlk']-j['dl0'])/(j['tmed']*(d-d0).days))
            r[f'{name}{k}']=(round(q.median(),2) if q.len() else np.nan)
    out.append(r)
R=pd.DataFrame(out); print(R.to_string()); R.to_csv('A_recovery.csv',index=False)
