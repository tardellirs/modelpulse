"""D stage 12 (local, small): per-model decomposition of spike days. For spike day D, per model: delta(D)/gap vs the model's mean
per-day delta over snapshots D-2,D-1,D+1,D+2 (days missing in file => delta < 500 => 0). Excess = delta(D) - baseline."""
import polars as pl, datetime as dt
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_width_chars(220)
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
sp=pl.read_parquet(S+"/out/spike_models.parquet").with_columns((pl.col("delta")/pl.col("gap")).alias("pd"))
for D in ["2025-03-09","2025-07-10","2026-03-19","2026-07-08","2026-08-02","2026-08-12"]:
    D=dt.date.fromisoformat(D)
    cur=sp.filter(pl.col("day")==D).select("id",pl.col("pd").alias("x"))
    nb=sp.filter((pl.col("day")!=D)&(pl.col("day").is_between(D-dt.timedelta(days=2),D+dt.timedelta(days=2)))).group_by("id").agg((pl.col("pd").sum()/4).alias("base"))
    j=cur.join(nb,on="id",how="left").with_columns(pl.col("base").fill_null(0),(pl.col("x")).alias("x"))
    j=j.with_columns((pl.col("x")-pl.col("base")).alias("ex")).with_columns((pl.col("x")/pl.col("base").clip(1)).alias("ratio"))
    tot=j["ex"].sum(); pos=j.filter(pl.col("ex")>0)
    srt=pos.sort("ex",descending=True)
    big=j.filter(pl.col("base")>=5000)
    print(f"{D}: models with |delta|>=500: {j.height}; excess total {tot/1e6:.0f}M; top10 contributors {srt.head(10)['ex'].sum()/1e6:.0f}M, top100 {srt.head(100)['ex'].sum()/1e6:.0f}M, top1000 {srt.head(1000)['ex'].sum()/1e6:.0f}M;"
          f" n models with ratio>1.5 (base>=5k/day): {big.filter(pl.col('ratio')>1.5).height} of {big.height}; median ratio of those {big['ratio'].median():.2f}; share of big models with ratio>1.25: {big.filter(pl.col('ratio')>1.25).height/big.height:.2f}")
    print("   top5:",[(i,round(e/1e6,1),round(r,1)) for i,e,r in zip(srt["id"][:5],srt["ex"][:5],srt["ratio"][:5])])
