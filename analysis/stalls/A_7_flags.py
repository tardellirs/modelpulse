# Q1: stability of flagged days across variants; threshold choice; bimodality; weekday; hub ratio.
import pandas as pd,numpy as np,json
pd.set_option('display.width',250);pd.set_option('display.max_rows',500);pd.set_option('display.max_columns',50)
S=pd.read_csv('A_shares.csv',parse_dates=['day']).set_index('day'); S=S[S.index>='2025-03-20']
meta=json.load(open('/tmp/meta.json')); skip=set(meta['skip_days'])
print('skip_days',sorted(skip))
core=['t500_z','t2000_z','t10000_z','r500_z','r2500_z','r10000_z','orig_z','t500_p5','t2000_p5','t10000_p5','r2500_p5','orig_p5']
for th in [0.15,0.2,0.25,0.3,0.35,0.4]:
    F={v:set(S.index[S[v]>=th]) for v in core}
    base=F['t2000_z']
    row={v:(len(F[v]), round(len(F[v]&base)/max(1,len(F[v]|base)),2)) for v in core}
    inter=set.intersection(*[F[v] for v in core if v not in('orig_z','orig_p5')]); uni=set.union(*[F[v] for v in core])
    print(f'th={th}: n/Jaccard-vs-t2000_z',row,'| in all non-orig:',len(inter),'in any:',len(uni))
# where do variants disagree at 0.30
th=.3
F={v:(S[v]>=th) for v in core}
dis=S.index[(pd.concat(F,axis=1).sum(axis=1)>0)&(pd.concat(F,axis=1).sum(axis=1)<len(core))]
print((S.loc[dis,core]*100).round(1).assign(dow=[d.strftime('%a') for d in dis]))
# gap in distribution: sorted t2000_z shares of days >=0.05
x=S['t2000_z'].dropna(); print(np.round(np.sort(x[x>=0.04].values),3))
x2=S['t2000_p5'].dropna(); print('p5',np.round(np.sort(x2[x2>=0.1].values),3))
S.to_csv('A_shares_trim.csv')
