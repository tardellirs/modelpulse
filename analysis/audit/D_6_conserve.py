"""D stage 6 (local): conservation, dl30 consistency, spike concentration, from server day_stats.parquet etc."""
import json, polars as pl, datetime as dt
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(250)
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
O=S+"/out"
st=pl.read_parquet(f"{O}/stats.parquet").sort("day"); m=json.load(open(f"{S}/d/meta.json"))
h=pl.read_parquet(f"{S}/d/hub_series.parquet"); hub=h.group_by("day").agg(pl.col("dl").sum().alias("pub")).sort("day")
pub_total=hub["pub"].sum()
s=st.filter(pl.col("prev").is_not_null() & (pl.col("dlall_null")==0) )
print("intervals",s.height)
print("== conservation, all snapshot intervals (first dl_all snapshot -> last)")
tot=dict(pos=s["pos"].sum(),neg=s["neg"].sum(),new_all=s["new_all"].sum(),gone_all=s["gone_all"].sum())
first=st.filter(pl.col("dlall_null")==0).row(0,named=True); last=st.row(-1,named=True)
print({k:round(v/1e9,4) for k,v in tot.items()}, "first",first["day"],round(first["dlall_sum"]/1e9,3),"last",last["day"],round(last["dlall_sum"]/1e9,3))
print("net growth of sum(dl_all):",round((last["dlall_sum"]-first["dlall_sum"])/1e9,4),"identity pos+neg+new-gone:",round((tot["pos"]+tot["neg"]+tot["new_all"]-tot["gone_all"])/1e9,4))
print("published hub_series total",round(pub_total/1e9,4),"vs sum pos",round(tot["pos"]/1e9,4),"diff",round((pub_total-tot["pos"])/1e9,4))
# new ids: share of daily total
s=s.with_columns((pl.col("new_all")/pl.col("pos")).alias("new_share"),(pl.col("gone_all")/pl.col("pos")).alias("gone_share"),(pl.col("pos_deleted")/pl.col("pos")).alias("del_share"))
print("new-id first-appearance downloads: total",round(tot["new_all"]/1e9,3),"B =",round(100*tot["new_all"]/pub_total,2),"% of published; per day median share",round(s["new_share"].median()*100,2),"% max",round(s["new_share"].max()*100,1))
print("deleted-since models' positive deltas (reassigned to 'other' in hub_series):",round(s["pos_deleted"].sum()/1e9,3),"B =",round(100*s["pos_deleted"].sum()/s["pos"].sum(),2),"%")
print(s.select("day","gap","pos","neg","new_all","gone_all","pos_deleted","n_new","n_gone").sort("new_all",descending=True).head(12))
# by month
mo=s.with_columns(pl.col("day").dt.strftime("%Y-%m").alias("ym")).group_by("ym").agg((pl.col("pos").sum()/1e9).round(3).alias("pos_B"),(pl.col("pos_deleted").sum()/pl.col("pos").sum()*100).round(2).alias("del_pct"),(pl.col("new_all").sum()/pl.col("pos").sum()*100).round(2).alias("new_pct"),(pl.col("gone_all").sum()/pl.col("pos").sum()*100).round(2).alias("gone_pct"),(pl.col("neg").sum()/1e9).round(3).alias("neg_B")).sort("ym")
print(mo)
# negative deltas days
print("days with large negative sum (>1% of pos):")
print(s.filter(pl.col("neg").abs()>0.01*pl.col("pos")).select("day","pos","neg","n_down","n_cur"))
# dl30 consistency
tt=hub.with_columns(pl.col("pub").rolling_sum(30).alias("r30")).drop_nulls()
x=st.select("day","dl30_sum").join(tt,on="day").with_columns((pl.col("dl30_sum")/pl.col("r30")).alias("ratio"))
print("== dl30 sum vs rolling 30-day sum of published hub total: ratio quantiles",x["ratio"].quantile(0.05),x["ratio"].median(),x["ratio"].quantile(0.95),x["ratio"].min(),x["ratio"].max())
x=x.with_columns(pl.col("ratio").rolling_median(15,center=True).alias("rm")).with_columns((pl.col("ratio")/pl.col("rm")).alias("dev"))
print(x.filter((pl.col("dev")-1).abs()>0.03).select("day","dl30_sum","r30","ratio","rm","dev"))
x.write_csv(f"{S}/dl30_ratio.csv")
