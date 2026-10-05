import polars as pl, glob, sys
H,O=sys.argv[1],sys.argv[2]
files=sorted(glob.glob(f"{H}/spaces/series/*.parquet"))
rows=[];ev=[]
prev=None;pday=None
for f in files:
    m=pl.read_parquet(f)
    for (day,),d in sorted(m.partition_by("day",as_dict=True).items()):
        d=d.select("id","likes")
        if prev is not None:
            j=d.join(prev,on="id",suffix="_p")
            dl=j["likes"]-j["likes_p"]
            j=j.with_columns(dl.alias("delta"))
            dn=j.filter(pl.col("delta")<0)
            up=j.filter(pl.col("delta")>0)
            rows.append(dict(day=day,prev=pday,gap=(day-pday).days,n=d.height,n_new=d.height-j.height,n_gone=prev.height-j.height,
              likes_sum=int(d["likes"].sum()),up_sum=int(up["delta"].sum()),down_sum=int(-dn["delta"].sum()),n_down=dn.height,n_up=up.height,
              big_down=int(dn.filter(pl.col("delta")<=-5).height)))
            if dn.height: ev.append(dn.with_columns(pl.lit(day).alias("day")).select("id","day","delta","likes_p","likes"))
        prev=d;pday=day
pl.DataFrame(rows).write_parquet(f"{O}/sp_pairs.parquet")
pl.concat(ev).write_parquet(f"{O}/sp_down_events.parquet")
