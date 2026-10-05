"""D stage 10: hub_series monthly sum vs per-model net month-boundary diff (months with exact 1st-of-month snapshots)."""
import polars as pl, datetime as dt
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
b=pl.read_csv(S+"/out/boundaries.csv",try_parse_dates=True)
t=pl.read_csv(S+"/d/hub_tot.csv",try_parse_dates=True)
rows=[]
for r in b.iter_rows(named=True):
    a,e=r["snap_a"],r["snap_b"]
    hubsum=t.filter((pl.col("day")>a)&(pl.col("day")<=e))["tot"].sum()
    rows.append((str(r["month"]),str(a),str(e),r["span_days"],round(hubsum/1e9,3),round(r["pos"]/1e9,3),round((hubsum/r["pos"]-1)*100,2),round(r["neg"]/1e9,3),round(r["new"]/1e9,3)))
print("month snapA snapB span hub_sum_B boundary_pos_B hub/boundary-1 % neg_B new_B")
for x in rows: print(*x)
