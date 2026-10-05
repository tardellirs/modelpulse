"""Current datasets leaderboards: how much of each repo's 7-day number sits in its single biggest day (from the spark in leaderboards.json). usage: E_09_lb_bursts.py HFDIR"""
import json,sys
lb=json.load(open(f"{sys.argv[1]}/datasets/leaderboards.json"))
for k in ["gainers_7d","growth_7d","breakouts"]:
    rows=lb[k]; out=[]
    for i,r in enumerate(rows):
        sp=r["spark"][-7:]; t=sum(sp)
        if t>0: out.append((i+1,r["id"],max(sp)/t))
    for th in (0.5,0.7,0.9): print(k,"share of top-100 whose biggest day holds >=%d%% of last-7-day sum: %d"%(th*100,sum(1 for _,_,s in out if s>=th)))
    print("  top-10 ranks with >=70%:",[(i,n[:32],round(s,2)) for i,n,s in out[:10] if s>=0.7])
