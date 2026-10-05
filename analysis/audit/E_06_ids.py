"""Per-id span of the dataset series (first/last day present, all-time counter at both ends), month by month to keep memory low.
usage: E_06_ids.py HFDIR OUTDIR"""
import polars as pl, sys, glob
H,O=sys.argv[1],sys.argv[2]
parts=[]
for f in sorted(glob.glob(f"{H}/datasets/series/*.parquet")):
    m=pl.read_parquet(f,columns=["id","day","dl30","dl_all"]).filter(pl.col("dl_all").is_not_null()).sort("id","day")
    parts.append(m.group_by("id").agg(pl.col("day").first().alias("first"),pl.col("day").last().alias("last"),pl.len().alias("n"),
       pl.col("dl_all").first().alias("all_first"),pl.col("dl_all").last().alias("all_last"),pl.col("dl30").last().alias("dl30_last")))
    print(f,flush=True)
a=pl.concat(parts).sort("id","first")
g=a.group_by("id").agg(pl.col("first").first(),pl.col("last").last(),pl.col("n").sum(),pl.col("all_first").first(),pl.col("all_last").last(),pl.col("dl30_last").last())
g.write_parquet(f"{O}/ds_idspan.parquet"); print(g.height)
