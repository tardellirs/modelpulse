"""Per consecutive-snapshot pair stats on the RAW dataset series (positive deltas of dl_all), concentration, share of ids down.
usage: E_02_raw_pairs.py HFDIR OUTDIR"""
import polars as pl, glob, sys, datetime as dt
H,O=sys.argv[1],sys.argv[2]
files=sorted(glob.glob(f"{H}/datasets/series/*.parquet"))
rows=[];tops=[]
prev=None;pday=None
for f in files:
    m=pl.read_parquet(f).filter(pl.col("dl_all").is_not_null())
    for (day,),d in sorted(m.partition_by("day",as_dict=True).items()):
        d=d.select("id","dl_all","dl30","likes")
        if prev is not None:
            j=d.join(prev,on="id",suffix="_p")
            dl=(j["dl_all"]-j["dl_all_p"])
            pos=dl.clip(0)
            j=j.with_columns(pos.alias("pos"),dl.alias("delta"))
            tot=int(pos.sum())
            s=j.sort("pos",descending=True)
            top=s.head(200)
            tops.append(top.select("id","pos","delta","dl30").with_columns(pl.lit(day).alias("day"),pl.lit(pday).alias("prev")))
            ps=s["pos"]
            rows.append(dict(day=day,prev=pday,gap=(day-pday).days,n=j.height,n_new=d.height-j.height,n_gone=prev.height-j.height,total_pos=tot,
              total_neg=int((-dl).clip(0).sum()),share_down=float((dl<0).mean()),share_up=float((dl>0).mean()),
              top1=int(ps[0]),top10=int(ps.head(10).sum()),top100=int(ps.head(100).sum()),top1_id=s["id"][0],
              sum_all=int(d["dl_all"].sum()),sum_dl30=int(d["dl30"].sum()),n_ids=d.height,
              likes_sum=int(d["likes"].sum())))
        prev=d;pday=day
    print(f,flush=True)
pl.DataFrame(rows).write_parquet(f"{O}/pairs.parquet")
pl.concat(tops).write_parquet(f"{O}/pairs_top200.parquet")
