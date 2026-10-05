"""D stage 8 (local): pipeline_tag drift. hub_series assigns each model's downloads of ALL history to its CURRENT tag
(models.parquet; ids absent from the last snapshot, i.e. deleted/renamed, and models without tag -> 'other').
Compares with the tag the model had in old hub-stats snapshots."""
import polars as pl, glob, os
pl.Config.set_tbl_rows(60); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(220)
S="/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad"
mq=pl.read_parquet(f"{S}/out/model_quarter.parquet")
now=pl.read_parquet(f"{S}/tags_now.parquet").select("id",pl.col("pipeline_tag").fill_null("other").alias("now"))
print("total pos (raw) B",mq["pos"].sum()/1e9)
j=mq.join(now,on="id",how="left").with_columns(pl.col("now").is_null().alias("deleted")).with_columns(pl.col("now").fill_null("other"))
d=j.group_by("q").agg(pl.col("pos").sum().alias("pos"),pl.col("pos").filter(pl.col("deleted")).sum().alias("pos_deleted")).with_columns((pl.col("pos_deleted")/pl.col("pos")*100).round(2).alias("pct_deleted")).sort("q")
print(d)
print("deleted-model downloads overall B",j.filter(pl.col("deleted"))["pos"].sum()/1e9, "n models",j.filter(pl.col("deleted"))["id"].n_unique())
top=j.filter(pl.col("deleted")).group_by("id").agg(pl.col("pos").sum()).sort("pos",descending=True).head(15)
print(top)
# old-tag comparison
for f,qs in [("tags_2025-03-03",["2025Q1","2025Q2"]),("tags_2025-09-15",["2025Q3","2025Q4"]),("tags_2026-03-01",["2026Q1","2026Q2"])]:
    p=f"{S}/{f}.parquet"
    if not os.path.exists(p): continue
    old=pl.read_parquet(p).select("id",pl.col("pipeline_tag").fill_null("other").alias("old"))
    for q in qs[:1]+qs[1:]:
        x=j.filter(pl.col("q")==q).join(old,on="id",how="left").with_columns(pl.col("old").fill_null(pl.col("now")))
        tot=x["pos"].sum()
        chg=x.filter((pl.col("old")!=pl.col("now")))
        print(f"\n{q} using tags of {f[5:]}: downloads of models whose tag differs from today's: {chg['pos'].sum()/1e9:.3f}B = {100*chg['pos'].sum()/tot:.2f}% of quarter ({tot/1e9:.2f}B)")
        a=x.group_by("now").agg(pl.col("pos").sum().alias("as_published")); b=x.group_by("old").agg(pl.col("pos").sum().alias("as_then")).rename({"old":"now"})
        c=a.join(b,on="now",how="full",coalesce=True).fill_null(0).with_columns(((pl.col("as_published")/pl.col("as_then")-1)*100).round(1).alias("pub_vs_then_%"),(pl.col("as_published")/1e6).round(0),(pl.col("as_then")/1e6).round(0)).sort("as_published",descending=True).head(10)
        print(c)
        mv=chg.group_by("old","now").agg(pl.col("pos").sum()).sort("pos",descending=True).head(8); print(mv)
