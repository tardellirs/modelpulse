"""D stage 9 (local, small): partial snapshots, spike concentration, weekday/dl30 ratio drift, from stats.parquet/topd.parquet."""
import polars as pl, datetime as dt, json
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(250)
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
st=pl.read_parquet(S+"/out/stats.parquet").sort("day").filter(pl.col("prev").is_not_null())
print("== snapshots whose model count differs >1% from previous")
print(st.filter(((pl.col("n_cur")/pl.col("n_prev")-1).abs()>0.01)).select("day","gap","n_prev","n_cur","n_new","n_gone","pos","gone_all","new_all"))
print("== n_gone > 0.3% of prev (heavy deletions / renames)")
print(st.filter(pl.col("n_gone")>0.003*pl.col("n_prev")).select("day","gap","n_prev","n_gone","gone_all","n_new","new_all"))
# spike concentration
st=st.with_columns((pl.col("pos")/pl.col("gap")).alias("pd"))
st=st.with_columns(pl.col("pd").rolling_median(15,center=True,min_samples=5).alias("med"),
                   (pl.col("top10")/pl.col("pos")).alias("s10"),(pl.col("top100")/pl.col("pos")).alias("s100"),(pl.col("top1000")/pl.col("pos")).alias("s1000"),(pl.col("top1")/pl.col("pos")).alias("s1"))
st=st.with_columns((pl.col("pd")/pl.col("med")).alias("r"))
print("median shares top1/10/100/1000:",st["s1"].median(),st["s10"].median(),st["s100"].median(),st["s1000"].median())
sp=st.filter(pl.col("gap")==1).filter(pl.col("r")>1.3).select("day","pos","r","s1","s10","s100","s1000","n_up","top1_id")
print("== spike days (gap-1, r>1.3) with concentration; compare to median above"); print(sp)
# spike excess decomposition: excess pos over local median; excess in top1000 vs rest
st=st.with_columns(pl.col("top1000").rolling_median(15,center=True,min_samples=5).alias("t1000_med"),pl.col("n_up").rolling_median(15,center=True,min_samples=5).alias("nup_med"))
ex=st.filter((pl.col("gap")==1)&(pl.col("r")>1.3)).with_columns((pl.col("pos")-pl.col("med")).alias("excess"),(pl.col("top1000")-pl.col("t1000_med")).alias("ex_top1000"),(pl.col("n_up")/pl.col("nup_med")).alias("nup_ratio")).with_columns((pl.col("ex_top1000")/pl.col("excess")).alias("share_of_excess_in_top1000")).select("day","r","excess","ex_top1000","share_of_excess_in_top1000","nup_ratio")
print(ex)
# top delta ids on spike days
td=pl.read_parquet(S+"/out/topd.parquet")
for d in ["2025-03-09","2025-07-10","2026-03-19","2026-07-08","2026-07-09","2026-08-02","2026-07-17","2026-08-12"]:
    x=td.filter(pl.col("day")==dt.date.fromisoformat(d)).sort("delta",descending=True).head(5)
    print(d,[(i,int(v)) for i,v in zip(x["id"],x["delta"])])
