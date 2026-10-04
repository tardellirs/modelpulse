# Local: compare variants, stability of flagged days, distribution/bimodality.
import pandas as pd,numpy as np,json
d=pd.read_csv('daily.csv',parse_dates=['day']).set_index('day')
vars_=sorted({c[2:] for c in d.columns if c.startswith('f_')})
S=pd.DataFrame({v:d['f_'+v]/d['n_'+v].replace(0,np.nan) for v in vars_})
N=pd.DataFrame({v:d['n_'+v] for v in vars_})
S.to_csv('A_shares.csv')
# hub ratio
h=pd.read_parquet('/tmp/hub.parquet');t=h.groupby('day').dl.sum();t.index=pd.to_datetime(t.index)
print(S.describe().T[['count','mean','50%','max']])
if __name__=='__main__':
    print(N.describe().T[['min','50%','max']])
