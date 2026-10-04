import json, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
rows = []
for k, d, v in json.load(open("C_daycheck.json")):
    if v: p, n, fa, f30, flk, nb, fb, f30b, tot, d30 = v; rows.append(dict(kind=k, day=d, prev=p, n=n, unch_all=fa/n, unch_dl30=f30/n, unch_likes=flk/n, nbig=nb, big_unch_all=fb/nb, big_unch_dl30=f30b/nb, tot=tot, d_dl30=d30))
df = pd.DataFrame(rows)
for k, s in df.groupby("kind"):
    print("\n==", k); print(s.drop(columns=["kind"]).round(3).to_string(index=False))
