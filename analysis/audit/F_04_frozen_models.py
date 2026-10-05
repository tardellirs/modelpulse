"""Models whose dl_all is flat while dl30 stays high (per-model frozen counters), and examples."""
from F_common import *
c = views(con(f"{WORK}/work.duckdb"))
show(c,"select count(*) n_dl30_ge1000, sum((dl_7d=0)::int) dl7_zero, sum((dl_7d*4.3<dl30*0.25)::int) dl7_far_below, sum((dl_7d>dl30*0.9 and dl30>=1000)::int) dl7_ge90pct from models where dl30>=1000")
show(c,"select id, dl30, dl_7d, dl_all, likes from models where dl30>=5000 and dl_7d=0 order by dl30 desc limit 20")
for mid in ['alexrzem/flux-loras','TenjinDas/Test']:
    print(mid)
    show(c,f"select day, dl30, dl_all from series where id='{mid}' and day>=DATE '{LAST}'-60 order by day",70)
