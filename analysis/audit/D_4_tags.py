"""D stage 4 (local): pipeline_tag drift. Reads id+pipeline_tag from OLD hub-stats revisions (column-chunk range reads)
and compares with the tag of the latest snapshot (what hub_series uses for all history)."""
import sys, pyarrow.parquet as pq, polars as pl, datetime as dt
from huggingface_hub import HfApi, HfFileSystem
api=HfApi(); fs=HfFileSystem()
commits=[c for c in api.list_repo_commits("cfahlgren1/hub-stats",repo_type="dataset") if "models.parquet" in c.title]
by={c.created_at.date():c.commit_id for c in commits}
print(len(by),min(by),max(by))
def tags(day):
    # nearest revision on/after day
    d=min(k for k in by if k>=day)
    f=fs.open(f"datasets/cfahlgren1/hub-stats@{by[d]}/models.parquet")
    t=pq.ParquetFile(f).read(columns=["id","pipeline_tag"])
    return d,pl.from_arrow(t)
if __name__=="__main__":
    for day in sys.argv[1:]:
        d,t=tags(dt.date.fromisoformat(day)); t.write_parquet(f"/private/tmp/claude-501/-Users-tardelli-Workplace/fc6456dd-10fc-4dd5-98df-8a5194fff159/scratchpad/tags_{d}.parquet"); print(d,t.height)
