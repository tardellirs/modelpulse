# A. The "frozen metric" -- how robust is it, and what do the frozen / non-frozen models look like?

Read-only analysis of the daily `dl_all` counters, 2025-02-27 .. 2026-10-04 (493 snapshot days, 474 usable after the 14-day warm-up, i.e. from 2025-03-20). Scripts `A_1` .. `A_12` sit next to this file (steps run on the server for the heavy parts, local polars/pandas for the small extracts; intermediate CSVs `A_*.csv` are included).

## 0. Method

* Universe: every model with `max(dl30) >= 1000` on any day with `dl_all` (112,821 ids; 37.0M rows) so that no model is dropped because it is small *today*. Top-10,000-by-dl30 cut-offs on sampled days were 1.7k-6.8k, so the universe contains every model of the fixed top-N sets.
* Per model/day: `delta = dl_all(t) - dl_all(prev snapshot of that model)`, `g` = calendar days between them, `dd = delta/g` (gap-normalised). Trailing median `tmed` = median of `dd` over the previous 14 snapshot rows (needs >= 7). A gap never makes a model "frozen" (a gap row with `delta > 0` is moving; only an exact zero over the whole gap is frozen). 36.9M panel rows.
* Variants. Sets chosen with no look-ahead: `tN` = `tmed >= N` (N = 500 / 2,000 / 10,000; ~3,400 / 1,700 / 600 models per day, median) and `rN` = top-N by dl30 on that day (N = 500 / 2,500 / 10,000). Plus `orig` = your set re-built (current top-3,000, whole-history median `dd` >= 2,000: 2,147 models; median frozen share 0.28%, matches your 0.28%). Frozen definitions: `z` = `delta == 0`; `p5` = `delta == 0` or `dd < 0.05 * tmed` (needs `tmed`). 14 variants in all (`A_shares.csv`).
* Share = frozen models / models in the set that day (unweighted count). "Half stall" below means a day with frozen share 25-90%, "full stall" >= 90%.

## 1. Robustness of the metric (Q1)

**Headline: the day set is very stable once the plateau artefact is removed; the plateau and the p5 definition are the weak spots.**

Distribution of the daily share (474 days), `t2000_z`: 412 days < 1% (median 0.13%, p90 1.6%), 26 days 1-5%, 9 days 5-25%, 21 days 25-90%, 6 days >= 90%. Same bins for `t500_z` 410/27/9/22/6 and `t10000_z` 410/26/10/22/6. So the distribution is clearly **bimodal**: a tight mode at ~0.1% and a broad second mass from 30% to 100% (about uniform on 0.3-0.9, plus a point mass at 100%), with a valley 5-25% that holds only 9 days. Those 9 days are: 2025-05-03 (22%, an existing skip window), 2025-07-18, 07-29..08-01 and 08-03 (7-21%: the OpenMed cohort of section 2 and the first, small, "young-models-only" stalls), 2025-09-17 (20%, a genuine small half stall) and 2025-12-11 (13%, same type, see section 3).

Flagged-day sets (share >= threshold), Jaccard against `t2000_z`:

| threshold | n days t2000_z | Jaccard of the other `z` variants (t500, t10000, r500, r2500, r10000) | `p5` variants | `orig` | flagged by all 10 non-orig variants / by any |
|---|---|---|---|---|---|
| 0.15 | 31 | 0.85-0.91 | 0.71-0.79 | 0.40 (77 days) | 28 / 91 |
| 0.20 | 29 | 0.90-0.93 | 0.72-0.85 | 0.50 (58 days) | 26 / 77 |
| **0.25** | **27** | **0.93-0.96** | 0.75-0.84 | 0.93 (29) | **26 / 41** |
| 0.30 | 26 | 0.90-0.96 | 0.71-0.87 | 0.93 | 24 / 40 |
| 0.35 | 25 | 0.86-0.96 | 0.70-0.89 | 0.89 | 22 / 37 |
| 0.40 | 24 | 0.75-0.96 | 0.59-0.86 | 0.89 | 18 / 36 |

Observations:

1. Your 10-of-12 reviewer days are not a survivorship artefact: with sets chosen only from the past, each of the 10 has 30-85% frozen in every `z` variant (table below). The only differences are level: the stricter the set (`t10000`, `r500`) the lower the share (the freeze hits young models, section 3, and big models are older), `r10000` the highest. 2026-06-25 and 2026-08-01 are < 6% in every variant (so they are **not freezes**, see section 4).
2. `orig` (current top-3000, survivors) is the only variant with a false plateau: at threshold 0.15 it flags 77 days vs 31, because of the 0.21 plateau (section 2). It is clean at 0.25 only because the plateau sits just under it.
3. `p5` is worse than `z`: baseline median 2.5% (vs 0.13%), more disagreement between variants, and it picks up three non-freeze days: 2025-05-19 (28% of models with a *negative* delta), 2025-05-20 (72%) and 2026-06-13 (95%). On those days `dl_all` **went down** (set total -1x to -5x its median per day; 2025-05-21 then shows +7.7x). That is a counter rollback/correction, a different phenomenon from a freeze, and 06-13 is already in `skip_days`. If you want to catch it, test `delta < 0` explicitly rather than "< 5% of median".
4. Fixed rank sets work for `z` too (top-500/2,500) but have a higher baseline (`r2500_z` median 0.64%, p90 5.3%; `r10000_z` 3.6%) because the top by dl30 includes spiky models that are legitimately idle on some days. `tmed`-based sets have the cleanest baseline (0.13%).
5. Weighting by `tmed` (download-weighted share) is worse: giant models dominate, there is no valley (5-25% on 28 days, e.g. many days of 2025-04/05 and 2026-06-18..25), see `A_weighted.csv`. Use the count share.
6. Tried "frozen only if it moved on the previous snapshot" (`A_refined.csv`, `A_11`): does not change anything meaningful (the 07-29 and 08-03 bumps stay), so those bumps are real small freezes, not pure cohort-ending artefacts. Only `t10000` is contaminated by the OpenMed cohort at 07-29..08-01 (29%/18%/14%) because it had a 22k/day trailing median there.

**Proposed rule:** frozen = `delta == 0` (exact), set = models whose median `dd` over the previous 14 snapshots (>= 7 obs) is >= 2,000 (500 or 10,000 give the same days), day flagged when share >= **0.25**, and check negatives separately (`delta < 0` share >= 0.25). Justification: baseline 0.13% and p99 of non-event days ~3%; the second mode starts at ~0.3; the valley 0.05-0.25 has only 9 days, all explained. The threshold is not very sensitive between 0.25 and 0.35 (26 vs 25 days). It misses only 2025-09-17 (20%) and 2025-12-11 (13%), small partial freezes whose cost is minor (set total / median = 0.97 on 09-17, see section 3). Lower to 0.15 only if you accept 07-29 and 07-18-type false positives. Note the share is bounded by the share of "young" models in the set (section 3), so it creeps upward as the Hub grows: 2025 half stalls are 29-78%, 2026 ones 48-77%.

Reviewer / user days across variants (% of models frozen):

| day | dow | orig_z | t500_z | **t2000_z** | t10000_z | r500_z | r2500_z | r10000_z | t2000_p5 |
|---|---|---|---|---|---|---|---|---|---|
| 2025-07-16 | Wed | 42.0 | 44.3 | 38.9 | 30.3 | 33.6 | 46.5 | 58.3 | 40.4 |
| 2025-08-13 | Wed | 77.4 | 76.6 | 72.3 | 67.3 | 66.8 | 78.4 | 85.1 | 72.6 |
| 2025-10-01 | Wed | 55.2 | 47.2 | 43.6 | 37.5 | 38.0 | 48.5 | 60.6 | 44.5 |
| 2025-10-08 | Wed | 72.6 | 68.3 | 64.8 | 60.8 | 62.0 | 69.7 | 80.5 | 65.2 |
| 2025-11-26 | Wed | 77.0 | 78.1 | 71.8 | 65.7 | 63.4 | 74.9 | 82.5 | 73.0 |
| 2026-02-11 | Wed | 65.7 | 67.5 | 65.4 | 52.0 | 47.2 | 64.2 | 71.5 | 65.6 |
| 2026-04-29 | Wed | 53.7 | 53.1 | 50.2 | 39.3 | 36.8 | 49.7 | 57.3 | 50.5 |
| 2026-06-25 | Thu | 2.9 | 1.6 | 2.1 | 3.5 | 5.2 | 2.5 | 2.4 | 5.1 |
| 2026-07-29 | Wed | 78.1 | 78.5 | 76.8 | 73.8 | 71.0 | 74.9 | 81.8 | 76.8 |
| 2026-08-01 | Sat | 0.1 | 0.2 | 0.1 | 0.0 | 0.2 | 0.6 | 2.6 | 4.1 |
| 2026-08-05 | Wed | 72.6 | 71.3 | 69.9 | 63.8 | 61.0 | 68.2 | 75.2 | 70.5 |
| 2026-08-12 | Wed | 78.7 | 78.7 | 77.2 | 72.0 | 72.0 | 76.4 | 82.0 | 77.2 |
| 2025-07-23 | Wed | 51.1 | 39.1 | 33.8 | 28.9 | 27.2 | 47.4 | 56.1 | 34.2 |
| 2025-09-17 | Wed | 36.3 | 23.9 | 20.0 | 12.6 | 13.4 | 23.4 | 36.7 | 20.7 |
| 2025-11-05 | Wed | 41.5 | 38.7 | 29.5 | 25.0 | 19.8 | 31.3 | 41.5 | 31.2 |
| 2025-12-17 | Wed | 76.4 | 75.3 | 71.2 | 66.5 | 64.6 | 73.8 | 82.4 | 71.7 |
| 2026-01-28 | Wed | 49.6 | 51.3 | 50.4 | 30.7 | 26.6 | 47.5 | 53.0 | 51.1 |
| 2026-05-12 | **Tue** | 52.2 | 51.0 | 48.2 | 37.5 | 34.0 | 47.5 | 54.3 | 49.1 |
| 2026-07-08 | Wed | 61.8 | 62.1 | 60.7 | 53.5 | 45.6 | 57.2 | 63.1 | 60.9 |
| 2026-09-02 | Wed | 59.2 | 54.2 | 54.4 | 50.7 | 42.8 | 51.1 | 55.8 | 55.6 |

### Surprise: it is (almost) always a Wednesday
Of the 21 half-stall days (25-90% frozen) in `t2000_z`, **20 are Wednesdays and 1 a Tuesday** (2026-05-12). Of the 68 Wednesday snapshots since 2025-03-20, 21 (31%) are flagged >= 25% (20 half + 2025-10-15 full), against 6 non-Wednesday flags in the other 406 days (the full stalls 2025-08-16/17/19, 2026-07-20, 2026-08-28 and 05-12). 10 of the reviewer's 12 days are Wednesdays (the two non-Wednesday ones are the two non-freezes). The other weekdays have 0 half stalls. Since 2025-10-01, 16 of 47 Wednesdays are flagged. Full 100% stalls are on random weekdays. This looks like a weekly Wednesday job on the Hub side (counter refresh), not random outages: a pair rule could be tied to Wednesdays but I would not hard-code it.

## 2. The ~0.21 plateau, Aug-Oct 2025 (Q2)

**It is a survivorship artefact of your set, not a Hub phenomenon. Same ~283 models every day, not alternating, and it ends abruptly on 2025-10-19.**

* The plateau is present only in `orig` (and slightly in `r2500_p5`); in `t500/t2000/t10000_z` those days are 0.0-0.9%, in `r500/r2500_z` 0.1-3%.
* Between 2025-08-24 and 2025-10-18 (56 snapshot days) 35 days sit at `orig_z` = 13-23%, mostly 16-23% (n = 1,328-1,358 models, 220-300 frozen), 14 at < 5%, 5 are real stalls (09-10 82%, 09-17 36%, 10-01 55%, 10-08 73%, 10-15 100%) and 2 in between. (In fact it starts ~2025-08-04 (cohort frozen share per week: 52%, 89%, 50%, 77% ...).)
* The set: **283 models frozen on >= 80% of plateau days; 281 of them are `OpenMed/OpenMed-NER-*`** (token-classification, transformers, apache-2.0, params median 184M, all created 2025-07-16..18, first_seen 2025-07-17), plus `kernels-community/flash-attn3` and `DeepBeepMeep/...`. 99.3% OpenMed vs 14% of the set. 1,360 distinct ids were frozen at least once in the window; mean Jaccard between consecutive plateau days 0.70, the 283 are frozen on 75-99% of plateau days and on only 0.7-14% of the 14 off days (09-05/09-06 are in-between).
* Why they are "frozen": these models had practically **no real traffic** in that window (their trailing median is 0, a few get 1-3 downloads on some days). History of the cohort (301-384 models): 2025-07-19..07-27 every model gets exactly ~16k, 22k, 22k, 22k, (07-23 all frozen: a real stall), 44k (07-24 catch-up = 2x), 22k, 22k per day, then traffic collapses on 07-28; from a few hundred to a few thousand downloads per day for the whole cohort until 10-18 (barring single-model bursts, e.g. one model at 25-65k/day on 10-02..10-12); step up on **2025-10-19** to a uniform ~1,300 per model per day (about 1.1-1.2M/day for the cohort), 2.7-3.5k per model per day since 2025-12 (about 1M/day for the cohort). They are in the current top-3000 only because of that later traffic, so a "current top-N" set imports 283 dormant models for the 12 earlier weeks.
* Alternation (0 one day, 2x the next): **no**. Because `tmed` is 0 there is no meaningful ratio; the data show the deltas on off days are tiny (the cohort ticks together, e.g. 08-31, 09-02, 09-09, 09-13..16, 09-18, 09-30, 10-02), never a 2x spike. Updates are not every-other-day; they are simply near-zero demand.
* Ends: abruptly (share 0.20 on 10-18, 0.004 on 10-19 and after). `orig_z` plateau ~0.2 therefore is "283/1,340".
* Side effect for the other direction: sets defined by trailing medians (`t10000`) include that cohort at 22k/day just after its traffic stopped, which gives 29%/18%/14% frozen on 2025-07-29..08-01 (and 15%/21% in `t2000` on 07-29 and 08-03). That is the only contamination I found for `t` sets.

## 3. Who keeps counting during a half stall (Q3)

On the 21 half-stall days (43,958 model-days, 5,907 models with `tmed >= 2000`): overall 39.5% keep counting. **It is the same set each time (pairwise Jaccard of non-frozen sets over common models mean 0.65, median 0.67) and the determinant is model age**, not size, library or author alone.

Share of model-days still counting, by creation date (current `created_at`; 2022-03-02 is the Hub's date for pre-existing repos):

| created | models | still counting |
|---|---|---|
| <= 2022-03-02 | 683 | **98.1%** |
| 2022 Q2-Q4 | 300 | 75-81% |
| 2023 Q1 / Q2 | 119 / 150 | 91% / 79% |
| 2023 Q3 / Q4 | 153 / 175 | 67% / 60% |
| 2024 Q1 / Q2 | 193 / 240 | 55% / 42% |
| 2024 Q3 / Q4 | 392 / 304 | 35% / 25% |
| 2025 Q1 | 336 | 8.6% |
| 2025 Q2 | 402 | 0.6% |
| 2025 Q3 .. 2026 Q3 | ~2,350 | 0.0-0.3% |

* "Always counting" (non-frozen on >= 80% of half days, >= 5 days present): 698 models, median created 2022-03-02, 99% created before 2024, 0% GGUF, median 110M params; 514 `transformers` + 76 `sentence-transformers` + 61 `timm`; top authors timm 61, facebook 52, microsoft 44, sentence-transformers 39, google 23, Helsinki-NLP 22, cross-encoder 13; tags fill-mask, image-classification, text-classification, sentence-similarity, ASR. Named: `sentence-transformers/all-MiniLM-L6-v2` counts on 19 of 21 half days (at 1.08x its median), all-mpnet-base-v2, bert-base-uncased (21/21), clip-vit-base-patch32 (21/21), roberta, gpt2, distilbert, electra, Bingsu/adetailer (17/21), timm/mobilenetv3_small (21/21).
* "Never counting" (<= 10%): 1,471 models, median created 2025-08-06, 0% before 2024, median 1.7B params, 46% derivative (`base_relation`), 16% GGUF; Qwen (127), lmstudio-community (111), unsloth (84), nvidia, google, OpenMed (310), image-text-to-text, text-generation, token-classification (the OpenMed ones). Not-counting rates by trait: GGUF 89%, mlx 97%, gguf library 96%, quantized derivatives 85%, image-text-to-text 92%; but bert-style `fill-mask` models still count 91% of the time (they are old). Size is flat (non-frozen rate 28-49% across `tmed` sextiles).
* Reading: the Hub's all-time counter for old repos is refreshed through a path that does not stall on those days; for repos created after ~2024 it does. The 2024-2025 gradient is smooth, so it is likely a per-repo property (e.g. which backend/aggregation holds the counter) rather than an on/off date. It is **my inference** from correlation: I cannot see the Hub internals.
* This explains the "half" dips: the old models hold most of the Hub's volume (the original BERT/CLIP/MiniLM family), so even though 50-80% of the *models* freeze the Hub-wide *total* only drops to 0.30-0.75 of its median (sets total / median in the table below: 0.33 on 2025-12-17, 0.47 on 2026-07-29, 0.53 on 2026-09-02, 0.70 on 2025-10-01). Days with a low frozen share (2025-09-17 20%, 2025-12-11 13%) are when only the very youngest models froze, with set total at 0.97 (no visible dip). Because the frozen share depends on the age mix of the set, it is a poor proxy for the size of the dip: use the total as well.
* `amazon/chronos-2` (13 days present) is never counting, `Comfy-Org/MiniMax-H3` (2 days) too; `BAAI/bge-small-en-v1.5` and `BAAI/bge-m3` count on 13/21 half days (rate 62%): intermediate age (2023-24) gives intermediate odds, consistent with the gradient.

## 4. Shape of each candidate day and catch-up (Q4)

Candidates: all days with `t2000_z >= 20%` plus the reviewer / user lists. Columns: frozen share (t2000_z) on D-1, D, D+1..+3 (snapshot days; all gaps are 1 day in the neighbourhood); median of `dd/tmed(D)` for the models frozen on D, on D+1..+3; number of those models whose first >= 1.3x day is D+1 / D+2 / D+3; "recovery" = median over the cohort of `(dl_all(D+k) - dl_all(D-1)) / (tmed(D) * calendar days)` for k = 3, 7, 14 snapshot days, for the frozen cohort and for the models that kept counting on D (control; ~1.0 means nothing lost); set total / 15-day median = sum of `dd` over the `t2000` set divided by its centred median (not the smoothed `hub_series`). `Y` = D is already in `skip_days` (existing window).

| day | dow | frozen % D-1 | frozen % D | frozen % D+1/+2/+3 | frozen-cohort ratio D+1/+2/+3 | first >=1.3x at +1/+2/+3 (n models) | recovery frozen 3/7/14d | recovery non-frozen (control) 3/7/14d | set total / 15d median | in skip_days |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-03 | Sat | 1 | **22** | 1/0/0 | 0.1/0.5/2.4 | 3/17/226 | // | // | 0.13 | Y |
| 2025-07-16 | Wed | 0 | **39** | 0/8/0 | 2.3/0.6/1.1 | 423/1/3 | 1.02/0.91/1.04 | 1.08/1.03/1.05 | 0.75 |  |
| 2025-07-23 | Wed | 0 | **34** | 0/0/0 | 2.3/1.1/1.0 | 429/4/3 | 1.17/1.07/1.08 | 1.07/1.01/1.02 | 0.80 |  |
| 2025-08-03 | Sun | 1 | **21** | 1/0/0 | 0.0/0.0/0.0 | 0/0/0 | // | // | 0.82 |  |
| 2025-08-13 | Wed | 0 | **72** | 0/0/100 | 2.1/1.0/0.0 | 906/5/0 | 0.77/0.59/0.97 | 0.76/0.99/0.97 | 0.43 |  |
| 2025-08-16 | Sat | 0 | **100** | 100/0/100 | 0.0/0.7/0.0 | 0/107/0 | 0.17/0.96/0.97 | // | 0.00 | Y |
| 2025-08-17 | Sun | 100 | **100** | 0/100/44 | 0.7/0.0/1.7 | 125/0/670 | 0.63/1.09/1.04 | // | 0.00 | Y |
| 2025-08-19 | Tue | 0 | **100** | 44/0/0 | 1.9/1.6/1.0 | 728/616/2 | 1.55/1.27/1.15 | // | 0.00 | Y |
| 2025-08-20 | Wed | 100 | **44** | 0/0/0 | 5.4/1.1/1.0 | 554/0/0 | 1.93/1.49/1.31 | 1.86/1.43/1.25 | 2.81 | Y |
| 2025-09-10 | Wed | 0 | **78** | 0/0/0 | 1.9/1.0/1.0 | 973/7/5 | 0.99/0.94/0.99 | 1.02/1.00/1.00 | 0.29 | Y |
| 2025-09-17 | Wed | 0 | **20** | 0/0/0 | 2.1/1.0/1.0 | 262/2/2 | // | // | 0.97 |  |
| 2025-10-01 | Wed | 0 | **44** | 0/0/0 | 1.9/0.9/0.9 | 514/7/2 | 0.99/0.82/0.90 | 1.03/0.95/0.93 | 0.70 |  |
| 2025-10-08 | Wed | 0 | **65** | 0/0/0 | 2.1/1.1/1.1 | 774/4/6 | 1.07/0.88/1.05 | 1.07/0.87/1.07 | 0.54 |  |
| 2025-10-15 | Wed | 0 | **100** | 0/0/0 | 2.3/1.1/1.0 | 1283/7/9 | 1.14/1.06/1.06 | // | 0.00 | Y |
| 2025-11-05 | Wed | 0 | **30** | 0/0/0 | 2.0/0.8/0.7 | 408/1/1 | 0.88/0.89/0.93 | 0.91/0.90/0.95 | 0.85 |  |
| 2025-11-26 | Wed | 0 | **72** | 0/0/0 | 2.0/1.0/1.0 | 1032/10/4 | 1.00/0.96/0.94 | 0.99/0.96/0.92 | 0.52 |  |
| 2025-12-17 | Wed | 0 | **71** | 0/0/0 | 0.9/2.1/1.0 | 252/793/2 | 1.01/0.95/0.89 | 1.04/0.99/0.93 | 0.33 |  |
| 2026-01-28 | Wed | 0 | **50** | 0/0/0 | 0.9/0.3/0.7 | 131/4/26 | 0.53/0.75/0.88 | 0.52/0.73/0.88 | 0.49 |  |
| 2026-02-11 | Wed | 0 | **65** | 0/0/0 | 2.2/1.0/1.0 | 1189/7/4 | 1.09/1.07/1.10 | 1.15/1.07/1.10 | 0.64 |  |
| 2026-04-29 | Wed | 0 | **50** | 0/0/0 | 2.2/1.2/1.0 | 1112/9/2 | 1.12/1.08/1.07 | 1.18/1.13/1.15 | 0.70 |  |
| 2026-05-12 | Tue | 0 | **48** | 0/0/0 | 2.0/1.1/1.1 | 1154/4/6 | 1.04/1.03/0.75 | 1.07/1.04/0.76 | 0.68 |  |
| 2026-06-25 | Thu | 0 | **2** | 0/0/0 | 1.6/0.9/0.7 | 45/1/0 | // | // | 0.61 |  |
| 2026-07-08 | Wed | 1 | **61** | 0/0/0 | 3.1/1.0/0.7 | 1608/3/1 | 0.96/0.98/1.00 | 1.15/1.09/1.10 | 1.25 |  |
| 2026-07-20 | Mon | 0 | **100** | 0/48/0 | 1.0/0.5/1.8 | 531/1090/1019 | 1.12/1.05/1.04 | // |  | Y |
| 2026-07-22 | Wed | 0 | **48** | 0/0/0 | 3.5/1.1/1.0 | 1281/1/0 | 1.41/1.09/1.08 | 1.43/1.17/1.12 | 1.81 | Y |
| 2026-07-29 | Wed | 0 | **77** | 0/0/0 | 2.1/1.1/0.4 | 1961/16/0 | 0.93/0.91/0.99 | 0.95/1.03/1.01 | 0.47 |  |
| 2026-08-01 | Sat | 0 | **0** | 0/0/0 | // | 0/1/0 | // | // | 0.55 |  |
| 2026-08-05 | Wed | 0 | **70** | 0/0/0 | 1.1/0.6/0.6 | 608/14/36 | 0.58/0.90/0.96 | 0.58/0.90/0.96 | 0.60 |  |
| 2026-08-12 | Wed | 0 | **77** | 0/0/0 | 3.8/1.8/1.7 | 2019/4/2 | 1.84/1.46/1.26 | 1.82/1.44/1.28 | 0.58 |  |
| 2026-08-28 | Fri | 0 | **100** | 0/0/0 | 1.7/1.7/0.7 | 2523/68/1 | 1.06/1.03/1.00 | // | 0.00 | Y |
| 2026-09-02 | Wed | 0 | **54** | 0/0/0 | 1.1/1.9/1.1 | 411/1000/7 | 1.03/0.85/1.00 | 1.08/0.90/1.03 | 0.53 |  |
| 2026-09-09 | Wed | 0 | **88** | 0/0/0 | 2.2/1.1/1.0 | 2429/30/8 | 1.10/1.07/1.05 | 1.19/1.17/1.14 | 0.24 | Y |

Reading the table:

* **Typical half stall (about 20 of 26 days):** D-1 and D+1..+3 all < 1% frozen; frozen models come back on D+1 with ~1.9-3.8x their median (2.0-2.3x typically, i.e. the missed day arrives in one lump: 85-99% of the frozen models have >= 1.3x on D+1) and are back to ~1.0x afterwards. 3/7/14-day recovery is 0.9-1.1 for both the frozen cohort and the control, so **nothing is lost**, the downloads are delayed by one day. The non-frozen models on D run at ~1.0x (they are unaffected).
* **Catch-up on D+2, not D+1:** 2025-12-17 (793 models first catch up on D+2 vs 252 on D+1; D+1 ratio 0.95, D+2 2.07) and 2026-09-02 (1,000 vs 411; D+1 1.09, D+2 1.89); partly 2025-08-19/20 (adjacent to full stalls). A pair rule tied to D+1 only would miss them; a window up to D+2 (what the pipeline does: up to 3 days) is needed. On 2025-12-17 the day-after total is 0.72 and the lump (2.27x) lands on 12-19.
* **Possible "lost" / not-caught-up:** 
  * **2026-01-28 (Wed, 50% frozen):** frozen models have D+1/+2/+3 ratios 0.89/0.32/0.72, only 16% show >= 1.3x on any of D+1..D+3, recovery 0.53/0.75/0.88 (3/7/14 days). But the *non-frozen control is the same* (0.52/0.73/0.88) and the whole set runs at 0.49, 0.34, 0.75x its median on 01-29, 01-30, 02-01 with frozen share ~0: a hub-wide slump of ~a week (set total/median 0.49, 0.41, 0.31), not a freeze whose backlog is missing. 14 days later both cohorts are at 0.88: some downloads genuinely absent (either real traffic or a broader counter lag), no 2x catch-up exists to be recovered. Do not smooth this as a stall; the pipeline will treat 01-28 as a stall only if the hub total < 0.3x which it is not (0.49).
  * **2026-08-05 (Wed, 70%):** D+1 1.1x (only 30% of the frozen show >= 1.3x), D+2/+3 0.56/0.61x, 3-day recovery 0.58, 7-day 0.90, 14-day 0.96 (control identical). A partial catch-up spread over a week (weekend effect included), closes by day 14. Treat as spread, not lost.
  * 2025-08-13 (7-day 0.59, 0.97 at 14 days) and 2026-05-12 (14-day 0.75 in both cohorts) are distorted by neighbouring events (stalls 08-16..20; a later slump), not by this freeze; 2025-10-01 and 10-08 recover only 0.82-0.88 at 7 days and 0.90-1.05 at 14.
  * Elevated, not lost: 2026-08-12 (1.8x on D+1 and still 1.26-1.28x after 14 days in both cohorts: a hub-wide surge, total ratio 3.4 on 08-13).
  * **No day shows a frozen cohort that never recovers while the control does**; I find no evidence of lost downloads attributable to a freeze.
* **Non-freeze days (2026-06-25 and 2026-08-01, 2.1% and 0.1% frozen):** the counters moved but at about half the usual rate (all-set median `dd/tmed` 0.50 on 06-25 and 0.43 on 08-01; set total / median 0.61 and 0.55). The days around are elevated: set total / median is 1.80 on 06-24 (the day before 06-25) and, for 08-01, 2.13 on 08-02 and 1.36/1.66 on 08-03/04. That is a "half stall" in the **total**, as the reviewer saw (pair of days, sum ~2x), but not a freeze of counters: apparently a slower tick that is repaid by neighbouring days. The frozen metric cannot see them; they need a total-based rule (ratio of the day's total to the median < 0.7 next to a neighbour > 1.3). 
* **High frozen share on 2025-08-03 (21%) and 2025-05-03 (22%)** need care: 2025-08-03 (a Sunday, 21%) is not a Wednesday-type event and its shape table row is meaningless (the 'frozen' there are partly the dormant OpenMed cohort with `tmed` still inflated, ratio 0 by construction); 2025-05-03 is in a skip window (05-03..05) where the share is 22% in `t2000` but 54% in `r10000`.
* Full stalls (>= 90%): 2025-08-16, 08-17, 08-19 (08-18 fully moving in between), 2025-10-15, 2026-07-20, 2026-08-28 (+ 2026-09-09 at 88%, 2025-03-04 not in my window); all in `skip_days`, and the cohort recovers 0.96-1.09 after 7 days.

## 5. Take-aways

1. A frozen-share >= 0.25 on the age-agnostic set `tmed >= 2000`, `delta == 0` flags 27 days; 26 are common to 10 variants. The 12 reviewer days minus 2026-06-25 and 2026-08-01 are genuine freezes (31-77%), and 10 of 12 are Wednesdays.
2. The 0.21 plateau is a dormant OpenMed cohort (283 models, created 2025-07-16..18, no traffic 2025-08-04..2025-10-18) imported by a survivor-based set. Drop it by building sets from trailing data.
3. Half-stalls are age-selective: the Hub's counters for repos created before ~2024 keep ticking, for repos created after 2025Q1 they stall. Hub-wide dips are therefore ~0.3-0.75, not ~0. A threshold of 0.3 on the total misses most of them; the frozen share (for the t2000 set) or a pair rule is the right detector. Catch-up arrives on D+1 (most) or D+2 (2025-12-17, 2026-09-02).
4. 2026-06-25 and 2026-08-01 are rate dips, not freezes; 2026-01-28 and 2026-08-05 have a weak/slow catch-up, nothing demonstrably lost; 2025-05-20 and 2026-06-13 are counter rollbacks (negative deltas), handle separately.

## Caveats

* The universe is models that reached dl30 >= 1000 at some point; the snapshots are the project's own. `dl_all` begins 2025-02-27, so nothing earlier.
* `created_at` in `models.parquet` is the latest metadata; it is only available for models that survive in the current file.
* "Frozen" = exact zero delta between two snapshots of one model; a model that has no download at all that day is frozen too (matters for small `tmed` only, which the 2,000 floor avoids).
* The Wednesday finding and the age finding are correlations in this data; the causes are not visible here.
* Run times: 6 container runs of < 1 minute each, < 3 GB, none between 10:30 and 11:45 BRT; only `/opt/modelpulse/work/stalls_A/` (and its `chmod 777`, needed because the container user is uid 1000) was written on the server.

## Files

`A_1_extract.py` (universe), `A_2_panel.py` (deltas, tmed), `A_3_daily.py` (variant shares), `A_4_compare.py`, `A_7_flags.py` (stability), `A_5_dump.py` (small subset for local work), `A_6_plateau.py`, `A_6b_openmed.py` (Q2), `A_8_shapes.py`, `A_8b_recovery.py`, `A_12_tables.py` (Q4), `A_9_keepcounting.py` (Q3), `A_10_weighted.py`, `A_11_refine.py`; data: `daily.csv`, `A_shares.csv`, `A_shapes.csv`, `A_recovery.csv`, `A_weighted.csv`, `A_refined.csv`. Local scripts read `/tmp/sub.parquet`, `/tmp/submeta.parquet`, `/tmp/hub.parquet` and `/tmp/meta.json` (copies from the server `stalls_A/sub*.parquet`, `data/hub_series.parquet`, `data/meta.json`).
