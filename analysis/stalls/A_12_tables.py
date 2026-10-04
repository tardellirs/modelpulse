# Emit markdown tables for the report
import pandas as pd,numpy as np
S=pd.read_csv('A_shapes.csv',parse_dates=['day']); R=pd.read_csv('A_recovery.csv',parse_dates=['day'])
M=S.merge(R,on='day',how='left')
def verdict(r):
    if r.skip_win=='Y' and r.fz_share>=.9: return 'full stall (in skip window)'
    if r.fz_share<.05: return 'no freeze (rate dip)'
    return ''
rows=[]
for _,r in M.iterrows():
    f=lambda x,n=2: '' if pd.isna(x) else f'{x:.{n}f}'
    p=lambda x: '' if pd.isna(x) else f'{100*x:.0f}'
    rows.append(f"| {r.day.date()} | {r.dow} | {p(r['fz-1'])} | **{p(r.fz_share)}** | {p(r['fz+1'])}/{p(r['fz+2'])}/{p(r['fz+3'])} | {f(r['rat+1'],1)}/{f(r['rat+2'],1)}/{f(r['rat+3'],1)} | {r['first_catch_dist(+1/+2/+3)']} | {f(r.fz3)}/{f(r.fz7)}/{f(r.fz14)} | {f(r.nf3)}/{f(r.nf7)}/{f(r.nf14)} | {f(r.tot_ratio)} | {'Y' if r.skip_win=='Y' else ''} |")
print("| day | dow | frozen % D-1 | frozen % D | frozen % D+1/+2/+3 | frozen-cohort ratio D+1/+2/+3 | first >=1.3x at +1/+2/+3 (n models) | recovery frozen 3/7/14d | recovery non-frozen (control) 3/7/14d | set total / 15d median | in skip_days |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
print("\n".join(rows))
