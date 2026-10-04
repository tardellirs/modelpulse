# Datasets vs models stalls, and snapshot timing (analysis C)

Read-only analysis. Scripts (all in this directory): `C_commits.py` (hub-stats commit list -> `C_commits.csv`), `C_timing.py` (commit -> snapshot day mapping -> `C_snapshots.csv`), `C_frozen.py` (server, per-day raw totals and frozen shares for models/datasets), `C_analyze.py`, `C_analyze2.py`, `C_analyze3.py` (tables; outputs in `C_analyze*_out.txt`, `C_daily_table.csv`), `C_daycheck.py` + `C_daycheck_tab.py` (all-repo unchanged shares on selected days; `C_daycheck_out.txt`).

## Method (what exactly was computed)
- Totals: from the RAW per-repo `dl_all` series (not the smoothed `hub_series`), sum of positive deltas between consecutive snapshots, divided by the calendar gap and spread over the gap days (same as `build.hub_series`), ratio to the centred 15-day rolling median (min 5 samples). Window 2025-02-28 .. 2026-10-04 (dl_all exists from 2025-02-27).
- Frozen share of day D: among repos whose median daily delta (over their whole history, gap-aware, deltas clipped at 0, at least 30 observations) is >= threshold, share with `dl_all(D) == dl_all(previous snapshot)`. Computed only on days whose previous snapshot is exactly D-1 (gap 1, 475 days for models, 443 for datasets), so days after a missing snapshot are excluded. Thresholds: models >=2,000 (3,845 ids); datasets >=200 (3,210 ids), >=1,000 (375), >=2,000 (194). The three dataset thresholds give the same picture; tables below use >=1,000 unless noted. Ids are pre-selected by a monthly-mean filter that provably contains every id with overall median >= threshold.
- Commit mapping: same rule as the pipeline (`backfill*.py`): UTC date of `created_at`, latest "Upload models.parquet" / "Upload datasets.parquet" commit of each date. Interval = hours between this snapshot's commit and the previous snapshot's commit. Caveat: 10 dates since 2025-02-27 have more than one commit; only the latest is used.
- Sanity: on "normal" days (ratio > 0.9 on both sides) the median frozen share is 0.0016 (models >=2000), 0.004 (datasets >=200), 0 (datasets >=1000), so a frozen share of 0.4 or more is far outside normal noise.

## Q1. Same dates? Same depth?

Days with ratio < 0.3 (gap-1 days): models 13, datasets 31; both 10, models only 3, datasets only 21.
- Models only (<0.3): 2025-05-04 (dataset 0.31), 2026-04-01 (0.38), 2026-06-13 (0.83). In all three the model frozen share is ~0 (0.01, 0.01, 0.00), i.e. these are low days with no counter freezing, not stalls of the same kind (they sit between stalled days, 2026-06-13 is catch-up/neighbour of the 06-12 window).
- Datasets only (<0.3), 21 days: 2025-04-14, 07-16, 07-23, 08-13, 08-20, 09-17, 10-01, 10-08, 12-17, 2026-01-28, 02-11, 03-12, 04-29, 05-12, 06-15, 07-08, 07-22, 07-29, 08-05, 08-12, 09-02. On these the dataset frozen share is 1.00 (all of them: 100% of datasets with median >=1000/day, and 100% of ALL ~450k-1M datasets, see below).
- Both (<0.3): 2025-03-04, 05-03, 08-16, 08-17, 08-19, 09-10, 10-15, 2026-07-20, 08-28, 09-09 (model frozen share 1.00 on 6 of them, 0.88 on 2026-09-09, 0.78 on 2025-09-10, 0.26 on 2025-05-03).

Key result: the two sides are the same events, but the dataset side is all-or-nothing and the model side is partial.
- Dataset frozen share >= 0.9 on 31 days. On 7 of them models are >= 0.9 frozen too (full stall), on 21 models are partially frozen (41% - 88% of big models) and only on 3 are models normal (2025-04-14, 2026-03-12, 2026-06-15).
- Conversely, every day on which the model frozen share is partial (0.3 to 0.9) has the dataset side 100% frozen: 19 of 19 days where a dataset snapshot exists (the other 2, 2025-11-05 and 2025-11-26, have no datasets snapshot at all, so the dataset side is unobservable there). Dataset frozen share is never partial on these days: it is 1.00 (0.99 once).
- Dataset total ratio is exactly 0.000 on those days (total delta is 0 or a few hundred downloads out of a normal ~5-10 M/day), whereas the model total on the same day is 0.19 - 1.26 of its median (median 0.54). The depth of the model dip does not follow the frozen share (2026-07-08: 61% of big models frozen, ratio 1.26; 2026-07-22: 49% frozen, ratio 1.74; 2025-08-20: 45% frozen, ratio 2.60, because the not-frozen big models carry catch-up).
- Correlations over gap-1 days: model ratio vs dataset ratio r = 0.38 (Spearman 0.51); model frozen share vs dataset frozen share r = 0.87 (Pearson, dominated by the 7 full stalls; Spearman 0.2 because the partial days sit between 0.4 and 0.9 on one side and exactly 1 on the other).
- Frozen share vs ratio (same side): models r = -0.31; datasets r = -0.48.

### The 12 half-stall days of the reviewer

| day | model ratio | model frozen (>=2000) | dataset ratio | dataset frozen (>=1000) | interval models (h) | interval datasets (h) | datasets minus models commit (min) |
|---|---|---|---|---|---|---|---|
| 2025-07-16 | 0.68 | 0.41 | 0.00 | 1.00 | 23.999 | 23.995 | +4.4 |
| 2025-08-13 | 0.39 | 0.72 | 0.00 | 1.00 | 23.998 | 23.992 | +4.8 |
| 2025-10-01 | 0.67 | 0.46 | 0.00 | 1.00 | 23.979 | 23.981 | +4.8 |
| 2025-10-08 | 0.51 | 0.68 | 0.00 | 1.00 | 23.988 | 23.987 | +4.6 |
| 2025-11-26 | 0.46 | 0.74 | no datasets snapshot | - | 24.023 | - | - |
| 2026-02-11 | 0.59 | 0.65 | 0.00 | 1.00 | 23.979 | 23.976 | +1.8 |
| 2026-04-29 | 0.67 | 0.53 | 0.00 | 1.00 | 24.008 | 24.009 | +2.2 |
| 2026-06-25 | 0.56 | 0.03 | 1.25 | 0.00 | 23.994 | 23.996 | +5.3 |
| 2026-07-29 | 0.44 | 0.77 | 0.00 | 1.00 | 24.111 | 24.141 | +6.7 |
| 2026-08-01 | 0.54 | 0.01 | 1.58 | 0.00 | 23.884 | 23.845 | +4.7 |
| 2026-08-05 | 0.59 | 0.71 | 0.00 | 1.00 | 23.958 | 23.944 | +4.9 |
| 2026-08-12 | 0.56 | 0.78 | 0.00 | 1.00 | 23.981 | 23.936 | +4.8 |

So 9 of 12 are dataset total stalls (dataset total = 0) with a partial model freeze (matches the reviewer's 42-79%); 2025-11-26 is the same model signature (74%) with no dataset snapshot to confirm; 2026-06-25 and 2026-08-01 (reviewer: almost no frozen models) show NO dataset stall (dataset ratio 1.25 and 1.58) and a normal frozen share on both sides, so they are a different phenomenon (genuine low days / not counter freezing), consistent with the reviewer's per-model check.

### All-repo check (not only big ones), `C_daycheck_out.txt`
On the dataset stall days, 100.0% of all 450k - 1M datasets have an unchanged `dl_all` (and on all but 4 of them also an unchanged `dl30`; the net dl30 change is only a few thousand downloads), with likes unchanged for 99.9% like on any day. So the whole datasets table's counters did not move, not just the big datasets. Models on the same days: 95% - 99% of all models unchanged in dl_all (baseline control days 53% - 90%), and 47% - 92% of models with stock dl_all >= 10k unchanged (control days 9% - 30%). Four days (2025-08-19, 2026-03-12, 2026-07-20, 2026-08-28) show `dl_all` frozen for ALL datasets while `dl30` still moved (d_dl30 of -2 M to -7.5 M, the 30-day window rolling off): dl_all and dl30 are not frozen by exactly the same mechanism; on 2026-07-20 and 2026-08-28 models are fully frozen in dl_all too (and dl30 moves), on 2026-03-12 only datasets.

Skip lists: pipeline `skip_days` has 20 model days and 57 dataset days. Of the 57 dataset skip days, 19 have dataset ratio >= 0.3 (they are catch-up days or neighbours in a window, e.g. 2025-08-14/15, 2025-10-09/10, 2025-12-18..20); of the 20 model skip days 7 have ratio >= 0.3 for the same reason. Stalls hit in this order: dataset stall day -> catch-up next day at 1.7x - 2.8x of its median (1.7x - 3.7x on 21 of the 31 dataset stall days; extremes 5.4x on 2025-08-21 and 6.6x on 2026-07-23) which equals roughly the one missing day, and the model catch-up is 1.2x - 1.9x.

## Q2. Snapshot timing

`C_snapshots.csv` has every snapshot with commit times. Findings:
- The intervals are essentially fixed: median 24.001 h for both models and datasets; since 2025-02-27 only 2 snapshots with gap 1 day are shorter than 22 h besides the first stall day (see list) - a handful of re-runs: 2025-02-28 17.1 h, 2025-03-04 10.3 h, 2025-07-10 17.6 h, 2025-11-25 19.4 h, 2025-12-10 16.2 h, 2026-02-19 20.9 h, 2026-03-12 20.3 h, 2026-04-25 15.5 h. Longer ones (e.g. 2026-03-11 27.8 h, 2026-02-18 27.1 h) also exist. Missing snapshots (calendar gap > 1 day) are separate (17 in models since 2025-02-27, e.g. 36 days / 860 h before 2025-07-09 and 17-19 days in 2026-04/06) and are excluded from the frozen-share and interval statistics.
- Upload time of day: 23:40 UTC until 2025-07-09, 13:07 UTC afterwards (drifting to ~13:35-13:50 by mid 2026); one cron job per day.
- All 12 half-stall days, and all dataset stall days, have an interval of 23.7 - 24.4 h (24.00 +- 0.1 h on 22 of the 31 dataset stall days; the others are 10.4 h on 2025-03-04, 20.3 h on 2026-03-12, 23.6-24.5 h on the rest). The "two snapshots close together" idea is NOT supported for these days: the intervals are normal.
- Short interval days are not low days: of the 8 snapshots with interval < 22 h, ratios (models) are 1.14, 1.59, 0.82, 1.00, 1.20, 1.07, 1.13 and 0.00 (only 2025-03-04, the 10.3 h one, which is a zero day on both sides after a 72 h gap; stall at the first hours after the 2025-03-03 snapshot, a one-off). The only gap-1 day with an interval above 30 h is 2025-03-09 (47 h, ratio 1.83, i.e. the expected ~2x of a double interval, a normal consequence).

Interval vs daily ratio, gap-1 days (models n=475, datasets n=443); normal-volume days only (20-28 h interval: 467 and 436):

| interval bucket | n models | mean / median ratio models | share < 0.7 | n datasets | mean / median ratio datasets | share < 0.7 |
|---|---|---|---|---|---|---|
| < 22 h | 8 | 0.99 / 1.10 | 0.125 | 6 | 0.76 / 1.08 | 0.333 |
| 22 - 23.9 h | 27 | 1.10 / 1.01 | 0.111 | 32 | 1.26 / 1.00 | 0.094 |
| 24.0 h +- 0.1 | 406 | 1.04 / 1.00 | 0.071 | 367 | 1.05 / 1.00 | 0.109 |
| 24.1 - 30 h | 33 | 1.01 / 1.01 | 0.182 | 35 | 1.09 / 1.00 | 0.229 |
| > 30 h | 1 | 1.83 | 0 | 3 | 1.20 / 1.00 | 0 |

Correlation interval vs ratio: models Pearson 0.075, Spearman -0.053; datasets Pearson -0.002, Spearman -0.036 (20-28 h only: -0.025/-0.054 and -0.005/-0.036). Normalising the ratio by interval/24 does not change it (-0.04, -0.08). Stall days' intervals: models stalls mean 23.91 +- 0.73 h vs others 23.95 +- 0.84 h. No relation: 98% of the snapshots are 24 h apart, and the dips occur at exactly 24 h.

Other timing checks (since 2025-07-10, 13 UTC era, `C_analyze3_out.txt`): upload minute-of-day deviation from the local median does not relate to stalls (Mann-Whitney p = 0.05 for dataset stalls, 0.45 for model half-stalls, correlation with ratio -0.03); the datasets-minus-models commit spacing is a bit larger on dataset stall days (4.8 vs 4.1 min, p = 0.03 and 4.7 vs 4.1, p = 0.07) but this is confounded by era (spacing was 4.4-4.9 min in 2025-07..11 and 1.8-2.2 min in 2025-12..05) and I treat it as noise. Dataset stalls are spread through the whole 13 UTC era (0-5 per month). The 23 UTC era (2025-03..07) had 2 dataset stalls (ratio<0.3) in 81 days vs 28 in 386 days since; the era also coincides with a different Hub period, so no causal reading.

What can and cannot be concluded: the commit time is the time of the upload (after fetching and writing the parquet), not when the Hub counters were read; the reading could have happened any number of minutes before. But since consecutive uploads are 24.00 h apart almost always, any reading delay would have to be equally constant, and the dips occur on days that are indistinguishable from normal days in timing. A short-interval explanation is ruled out for these days; a "read at the wrong moment relative to the Hub's internal counter update" cannot be ruled out by commit times and is in fact what the data resemble (see Q3).

## Q3. Same snapshot (commit) for models and datasets?

No: models.parquet and datasets.parquet are separate commits ("Upload models.parquet", "Upload datasets.parquet", plus spaces.parquet, posts.parquet, daily_papers.parquet...), but they come from the same daily job a few minutes apart. Datasets-minus-models commit time, since 2025-02-27 (443 days): median +3.2 min, IQR +1.8 .. +4.7, range -15 .. +53 min; 2025-03 to 2025-05 datasets came about 7-8 min BEFORE models; from 2025-07 about +4.4-5 min; since 2025-12 about +1.8-2.2; since 2026-06 about +4.5-9 min (12 min on 2026-07-22, which is also a stall day). Latest example (2026-10-04): models 13:49:31, spaces 13:54:49, datasets 13:59:34, posts 13:59:36.

So the counters are read at slightly different times (minutes) for each type, within one job run. When a stall hits both sides, the cause is upstream of the snapshot job (the Hub's counters, or a shared stage such as a cached API), because the two files would otherwise not both be frozen on 10 days with 100% of datasets frozen and 41%-100% of big models frozen. The partial model freeze vs total dataset freeze hints that the Hub's counter update is not instantaneous: it is applied progressively (models partly updated when read, datasets not at all, or datasets updated later than models in the same batch). That is a hypothesis; it fits that a stall always has the dataset side "all or nothing" and that datasets are always at least as frozen as models (never the reverse: 31 days dataset frozen >= 0.9 vs 7 with models >= 0.9, no day with models frozen >= 0.9 and datasets <0.9). But on the commit order itself, models are uploaded BEFORE datasets (since 2025-07) which would be the opposite direction if the Hub updated datasets before models, and the spacing is only minutes, so nothing about update order in the Hub can be inferred from these timestamps alone.

## Surprises / recommendations
1. The datasets-side detector is cleaner than the model-side one. A dataset total ratio < 0.1 (in fact exactly 0) is observed on all of the model half-stall days that can be checked (all 19 with a dataset snapshot and a partial model frozen share), and on no normal day. The 21 days of dataset-total-zero where models are only partially (or not) frozen have model ratios from 0.19 to 2.6. Applying the dataset stall windows to models too would also catch 2025-07-16, 2025-07-23, 2025-08-13, 2025-10-01, 2025-10-08, 2025-12-17, 2026-01-28, 2026-02-11, 2026-04-29, 2026-05-12, 2026-07-29, 2026-08-05, 2026-08-12, 2026-09-02 (these are not in the current model skip_days). Caution: on 2026-07-08, 2026-07-22 and 2025-08-20 the model total is not low (1.26, 1.74, 2.60) even though 45-61% of big models are frozen, so a plain copy of the dataset window can move/spread correct downloads there; a window-spreading approach is exact in sums anyway.
2. 2025-11-05 and 2025-11-26 (datasets have a 509 h hole in their commit history before 2025-11-24; models are missing 2025-06-04 .. 06-29 while datasets are present) mean the dataset side cannot confirm a few model days.
3. 2026-06-25 and 2026-08-01 are not freeze events (frozen share 0.03 / 0.01, datasets normal, interval 23.9-24.0 h): their cause is not in these data; they are not explained by interval or by a dataset stall.
4. Dataset skip_days windows include 19 days with dataset ratio >= 0.3 (neighbours/catch-up), as designed.
