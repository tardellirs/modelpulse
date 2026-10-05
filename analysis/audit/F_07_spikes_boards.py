"""For each current leaderboard entry: how concentrated is its dl_7d in a single day? (increments from consecutive non-skip snapshots)."""
from F_common import *
import json
c = views(con(f"{WORK}/work.duckdb"))
lb = json.load(open(f"{DATA}/leaderboards.json"))
ids = {r["id"] for k in ("gainers_7d","growth_7d","breakouts","likes_7d","families") for r in lb[k]}
c.execute("CREATE OR REPLACE TEMP TABLE bid(id VARCHAR)")
c.executemany("INSERT INTO bid VALUES (?)", [(i,) for i in ids])
c.execute(f"""CREATE OR REPLACE TEMP TABLE inc AS
  SELECT id, day, dl_all - lag(dl_all) OVER w d, day - lag(day) OVER w gap FROM (
    SELECT id, day, dl_all FROM series WHERE id IN (SELECT id FROM bid) AND day>=DATE '{LAST}'-60 AND day NOT IN (SELECT day FROM skip)) WINDOW w AS (PARTITION BY id ORDER BY day)""")
rows = c.execute(f"""SELECT id, sum(d) FILTER (WHERE day>DATE '{LAST}'-7) w7, max(d) FILTER (WHERE day>DATE '{LAST}'-7) mx7,
   median(d/gap) FILTER (WHERE day<=DATE '{LAST}'-7 AND day>DATE '{LAST}'-35) med_prior, max(d) FILTER (WHERE day>DATE '{LAST}'-7)/nullif(median(d/gap) FILTER (WHERE day<=DATE '{LAST}'-7 AND day>DATE '{LAST}'-35),0) spike_ratio
   FROM inc WHERE d IS NOT NULL GROUP BY id""").fetchall()
st = {r[0]: r for r in rows}
for k in ("gainers_7d","growth_7d","breakouts","likes_7d","families"):
    ent = lb[k]; n = 0; flagged = []
    for i, r in enumerate(ent):
        s = st.get(r["id"])
        if not s or not s[1]: continue
        share = s[2] / s[1]
        if share >= 0.5: flagged.append((i + 1, r["id"], int(r["dl_7d"] or 0), round(share, 2), int(s[2])))
    print(f"== {k}: {len(flagged)} of {len(ent)} entries have >=50% of 7d in one snapshot step; in top25: {sum(1 for f in flagged if f[0] <= 25)}")
    for f in flagged[:30]: print("  ", f)
