"""Replay the 'Most liked this week' leaderboard (likes_7d = likes(now) - likes(<= now-7d, 10d back), clip 0) for each week-end day;
count how many of the top-10 later lost a large share of their likes (purged / unliked), and the leaderboard on days near partial snapshots."""
import polars as pl, glob, sys, datetime as dt
H=sys.argv[1]
s=pl.concat([pl.read_parquet(f,columns=["id","day","likes"]) for f in sorted(glob.glob(f"{H}/spaces/series/*.parquet"))])
days=sorted(s["day"].unique().to_list())
last=days[-1]
fin=s.filter(pl.col("day")==last).select("id",pl.col("likes").alias("final"))
# peak likes and final likes (0 if gone is NOT assumed: use last observed)
lastobs=s.sort("day").group_by("id").agg(pl.col("likes").last().alias("lastobs"),pl.col("day").last().alias("lastday"),pl.col("likes").max().alias("peak"))
print("spaces",lastobs.height)
big=lastobs.filter((pl.col("peak")>=50)&(pl.col("lastobs")<=pl.col("peak")*0.5))
print("peak>=50 and lost >=50% of peak:",big.height, "of", lastobs.filter(pl.col("peak")>=50).height)
print("of these still present on last day:", big.filter(pl.col("lastday")==last).height)
# replay weekly boards on the Sunday-ish every 7 days
res=[]
dayset=set(days)
def at_or_before(ref):
    lo=ref-dt.timedelta(days=10)
    return s.filter((pl.col("day")<=ref)&(pl.col("day")>=lo)).sort("day").group_by("id").last()
for d in days[7::7]:
    if d<dt.date(2024,9,15): continue
    now=s.filter(pl.col("day")==d).select("id","likes")
    w=at_or_before(d-dt.timedelta(days=7)).select("id",pl.col("likes").alias("l7"),pl.col("day").alias("d7"))
    j=now.join(w,on="id",how="left").with_columns((pl.col("likes")-pl.col("l7").fill_null(0)).clip(0).alias("g")).sort("g",descending=True).head(10)
    j=j.join(lastobs,on="id")
    lost=j.filter(pl.col("lastobs")<pl.col("likes")*0.5)
    gone=j.filter(pl.col("lastday")<last)
    fullnull=j.filter(pl.col("l7").is_null()&(pl.col("likes")>=200))
    res.append(dict(day=d,top1=j["id"][0],top1_g=j["g"][0],lost50=lost.height,gone=gone.height,null_prior_big=fullnull.height,max_window=(d-j["d7"].min()).days if j["d7"].min() else None))
r=pl.DataFrame(res); pl.Config.set_tbl_rows(100); pl.Config.set_fmt_str_lengths(40); pl.Config.set_tbl_cols(20)
r.write_csv("E_space_boards_replay.csv")
print(r.filter((pl.col("lost50")>0)|(pl.col("null_prior_big")>0)|(pl.col("max_window")>8)))
print("weeks",r.height,"weeks with top10 containing a Space that later lost >=50% of likes:",r.filter(pl.col("lost50")>0).height, "total slots", r["lost50"].sum())
