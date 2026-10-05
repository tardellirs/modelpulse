"""D stage 3b (server): month-boundary diffs like analysis/monthly.py (but no interpolation: nearest usable snapshot on/before
the 1st, else after): sum over models in both snapshots of clip(delta,0), sum of dl_all of models only in the later snapshot,
sum of dl_all of models only in the earlier one, sum of negatives. -> /a/out/boundaries.csv"""
import duckdb, glob, json, datetime as dt, csv
c=duckdb.connect(); c.execute("SET memory_limit='3000MB'; SET threads=3; SET temp_directory='/a/tmp'")
meta=json.load(open("/d/meta.json")); skip=set(meta["skip_days"])
days=sorted(dt.date.fromisoformat(d) for d in meta["days"] if d>="2025-02-27")
usable=[d for d in days if str(d) not in skip]
def pick(b):
    le=[d for d in usable if d<=b]; return le[-1] if le else usable[0]
bs=[]; y,mo=2025,3
while dt.date(y,mo,1)<=days[-1]:
    bs.append(dt.date(y,mo,1)); mo+=1
    if mo>12: y,mo=y+1,1
def load(name,d):
    f=f"/d/series/{d:%Y-%m}.parquet"
    c.execute(f"create or replace table {name} as select id, dl_all, dl30 from read_parquet('{f}') where day=DATE '{d}' and dl_all is not null")
rows=[]
for a,b in zip(bs,bs[1:]):
    da,db=pick(a),pick(b)
    load("x",da); load("y",db)
    r=c.execute("""select sum(greatest(y.dl_all-x.dl_all,0)), sum(least(y.dl_all-x.dl_all,0)) from y join x using(id)""").fetchone()
    new=c.execute("select sum(dl_all) from y where id not in (select id from x)").fetchone()[0]
    gone=c.execute("select sum(dl_all) from x where id not in (select id from y)").fetchone()[0]
    rows.append(dict(month=str(a),snap_a=str(da),snap_b=str(db),span_days=(db-da).days,cal_days=(b-a).days,pos=r[0],neg=r[1],new=new,gone=gone,dl30_b=c.execute("select sum(dl30) from y").fetchone()[0]))
    print(rows[-1],flush=True)
with open("/a/out/boundaries.csv","w") as f:
    w=csv.DictWriter(f,rows[0].keys()); w.writeheader(); w.writerows(rows)
