"""For selected days, compare snapshot D with the previous snapshot over ALL repos (not only big ones), for models and datasets:
share unchanged in dl_all / dl30 / likes, restricted to repos with stock dl_all>=10k and to all repos. Runs in the image."""
import json, datetime as dt, duckdb, sys
c = duckdb.connect(); c.execute("SET memory_limit='2500MB'; SET threads=2; SET temp_directory='/work/duck_tmp'")
meta = json.load(open("/data/meta.json")); rm = json.load(open("/data/repos_meta.json"))
H = "2025-07-16 2025-08-13 2025-10-01 2025-10-08 2025-11-26 2026-02-11 2026-04-29 2026-06-25 2026-07-29 2026-08-01 2026-08-05 2026-08-12".split()
CTRL = "2025-09-15 2025-12-01 2026-03-03 2026-05-20 2026-07-01 2026-09-15".split()
days = sorted(set(H + rm["skip_days"] + meta["skip_days"] + CTRL))
days = [d for d in days if d >= "2025-03-05"]
out = []
for kind, src, alld in [("models", "/data/series", meta["days"]), ("datasets", "/data/datasets/series", rm["datasets_days"])]:
    for d in days:
        if d not in alld: out.append((kind, d, None)); continue
        i = alld.index(d); p = alld[i - 1]
        fa = f"{src}/{d[:7]}.parquet"; fb = f"{src}/{p[:7]}.parquet"
        r = c.execute(f"""
          with a as (select id, dl_all, dl30, likes from '{fa}' where day = DATE '{d}'),
               b as (select id, dl_all, dl30, likes from '{fb}' where day = DATE '{p}')
          select count(*) n, sum((a.dl_all = b.dl_all)::int) f_all, sum((a.dl30 = b.dl30)::int) f30, sum((a.likes = b.likes)::int) flk,
                 sum((a.dl_all >= 10000)::int) nbig, sum((a.dl_all >= 10000 and a.dl_all = b.dl_all)::int) fbig,
                 sum((a.dl_all >= 10000 and a.dl30 = b.dl30)::int) f30big, sum(greatest(a.dl_all - b.dl_all, 0)) tot, sum(a.dl30 - b.dl30) d30
          from a join b using(id)""").fetchone()
        out.append((kind, d, (p,) + tuple(int(x) if x is not None else None for x in r)))
        print(kind, d, out[-1][2], flush=True)
json.dump(out, open("/work/stalls_C/C_daycheck.json", "w"))
