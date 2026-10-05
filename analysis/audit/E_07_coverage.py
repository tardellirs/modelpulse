"""Share of Hub dataset downloads covered by the tracked universe (ids in datasets.parquet), on sampled day pairs of the RAW snapshots.
usage: E_07_coverage.py HFDIR RAWDIR"""
import polars as pl, sys, glob, os, datetime as dt
H,R=sys.argv[1],sys.argv[2]
uni=pl.read_parquet(f"{H}/datasets/datasets.parquet",columns=["id"]).with_columns(pl.lit(True).alias("u"))
files=sorted(glob.glob(f"{R}/2*.parquet")); days=[dt.date.fromisoformat(os.path.basename(f)[:10]) for f in files]
print(len(files),"files")
rows=[]
prev=None
for d,f in zip(days,files):
    cur=pl.read_parquet(f).filter(pl.col("downloadsAllTime").is_not_null()).join(uni,on="id",how="left").with_columns(pl.col("u").fill_null(False))
    if prev is not None and (d-prev[0]).days==1:
        j=cur.join(prev[1].select("id",pl.col("downloadsAllTime").alias("p")),on="id").with_columns((pl.col("downloadsAllTime")-pl.col("p")).clip(0).alias("dl"))
        tot=j["dl"].sum(); cov=j.filter(pl.col("u"))["dl"].sum()
        rows.append(dict(day=d,n_raw=cur.height,n_uni=int(cur["u"].sum()),all_raw=int(cur["downloadsAllTime"].sum()),all_uni=int(cur.filter(pl.col("u"))["downloadsAllTime"].sum()),pos_all=int(tot),pos_uni=int(cov),pos_nonuni=int(tot-cov)))
    prev=(d,cur)
r=pl.DataFrame(rows).with_columns((pl.col("pos_uni")/pl.col("pos_all")).alias("cov_flow"),(pl.col("all_uni")/pl.col("all_raw")).alias("cov_stock"),(pl.col("n_uni")/pl.col("n_raw")).alias("cov_n"))
r.write_csv("E_coverage_sample.csv")
for x in r.iter_rows(named=True): print(x["day"],x["n_raw"],"uni %.3f"%x["cov_n"],"flow %.4f"%x["cov_flow"],"stock %.5f"%x["cov_stock"],"nonuni_pos",x["pos_nonuni"])
