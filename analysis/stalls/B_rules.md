# Model Pulse: comparing stall rules (current / PAIR / FROZEN-SHARE)

Read-only analysis. Scripts: `B_1_extract.py` (raw rebuild), `B_2_frozen.py`, `B_3_rules.py` (Q1-Q3), `B_4_models.py` (Q4-Q5), `B_5_diag.py`, `B_6_variants.py`, `B_7_extra.py`, `B_9_hwm.py`, `B_10_final.py`, `B_11_rollback.py`; helpers `B_common.py`, `B_stalls_copy.py` (verbatim copy of `pipeline/stalls.py`). Data tables: `agreement.csv`, `q4_episodes.csv`, `rules.json`.

## 0. Headline findings

1. **Reconstruction works.** Raw totals rebuilt from per-model `dl_all` deltas reproduce the published series outside windows (max relative difference 0.27%, median about 0.02%, published about 0.02% higher in total; 4,055 of 32,143 per-tag day rows differ because I use current `models.parquet` tags, about 5.6% of mass is tagged differently). Running `stalls.windows()` on my RAW series gives exactly the 10 published windows and exactly the 20 published `skip_days`.
2. **The reviewer's half stalls are almost all Wednesdays** (10 of 12; the others are a Thursday and a Saturday). 21 of 83 Wednesdays in the range have frozen share above 0.35; only 7 non-Wednesdays do, and 6 of those are full stalls (r about 0) or 2026-05-12 (Tue). 19 of the 26 windows of the union rule start on a Wednesday. This looks like a weekly Hub-side event, not noise.
3. **Mechanism differs between the two rules' catches.** On frozen-share days the models split bimodally (about 50-77% of big models exactly 0, the rest about normal) and the frozen models then show 2-4x their normal rate the next day: a one-day delay for a subset of models. On the two PAIR-only days (2026-06-25, 2026-08-01) NO model subset froze: every big model is uniformly about 0.45-0.6x that day and about 1.6-1.9x the neighbour, i.e. a hub-wide timing shift of roughly half a day between two snapshots (pair sum 2.1-2.4x). Both conserve downloads, so spreading is right in both, but they are different phenomena.
4. **Frozen-share cannot replace the total-based rule.** It misses 3 of the 10 current windows (2025-05-03/04, 2026-04-01, 2026-06-12/13): there the counters moved at 2-27% of normal rather than exactly 0 (share 0.00-0.27). Use it in addition to `r<0.3`, not instead.
5. **2025-05-21 (7.45x) is not a real spike.** It is the rebound after a hub-wide counter rollback: on 2025-05-19 and 05-20, `dl_all` DEcreased for 146k and 174k models (16% and 19% of all models; -116M and -324M). `clip(0)` discards the dip but counts the full rebound on 05-21, adding about 0.38B phantom downloads. Same artifact on 2026-06-13 (557k models, -541M) produces the 2.3x/3.5x/3.8x days 2026-06-17..19, which no rule touches. None of the three rules smooths 05-21 or 06-17..19 (good: spreading would conserve the phantom), but they stay in the published series as outliers.
6. **Recommendation:** `current OR frozen-share>0.35 OR pair` with the existing window/catch-up logic (26 windows, 76 days, 50 skip_days; all 20 published skip_days retained, 30 added). Plus a separate "rollback" fix (section 6.3). Do not use a per-model high-water mark (tested, it fails).

## 1. Raw reconstruction (Q1)

Method: per snapshot day with non-null `dl_all`, join to the previous snapshot day on id, `clip(delta,0)/gap`, sum, spread evenly over the `gap` calendar days (same as `build.hub_series`). 493 snapshot days, 2025-02-27..2026-10-04; 584 calendar days in the hub series. Snapshot gaps: 17 intervals with gap>1, notably 2025-06-03..07-09 (36 days), 2026-04-01..04-18 (17), 2026-05-23..06-11 (19). Inside a gap the raw series is flat, so ratios there are artificial (many ratios of exactly 1.00).

| check | result |
|---|---|
| days compared outside current windows | 554, none missing |
| max relative difference raw vs published daily total | 0.27% (265 days over 0.01%, 10 over 0.1%) |
| sum raw vs published | 44,453,163,454 vs 44,462,239,950 (+0.02%) |
| windows from `stalls.windows(raw)` | same 10 windows; `skip_days` identical to meta.json (20 days) |
| window sums raw vs published | differ by 0.003-0.06% |

So the raw series is a faithful input for rule comparison. (The small positive offset in the published series is unexplained; it does not matter for the rules.)

## 2. The rules and their windows (Q2)

Definitions (all on RAW totals, 15-day centred median ratio `r`):
- **current**: `r<0.3`, then the stalls.py window logic.
- **pair**: day with `0.3<=r<0.7` next to a day with `r>1.3`, `r_low + r_nbr` in [1.6, 2.4]; window = the two days, merged with the current windows (merge if <=2 days apart). Found 10 pairs.
- **frozen**: share of "big" models (2,650 models, median daily delta >= 2,000; 1,026-2,553 present per day) with `dl_all` delta exactly 0 (gap-aware) above 0.35, then the same window/catch-up logic as stalls.py with the flag replacing `r<0.3`.
- **frozen+cur**: flag = frozen OR `r<0.3`. **pair|frozen**: union of windows of pair and frozen+cur (merged).

Totals: 

| rule | windows | days in windows | skip_days | published skip_days dropped |
|---|---|---|---|---|
| current (= published) | 10 | 30 | 20 | none |
| pair (current + pair) | 18 | 52 | 34 | none |
| frozen alone | 23 | 63 | 40 | 6 (the 3 partial-stall windows) |
| frozen+cur | 26 | 72 | 46 | none |
| pair|frozen | 26 | 76 | 50 | none |

### Agreement table (all flagged seed days; `Y` = flagged by that rule; last column: day lies inside a window of current / pair / frozen / frozen+cur)

| date | dow | r | frozen share | cur (r<.3) | pair | frozen>.35 | in window: cur / pair / frozen / frozen+cur | note |
|---|---|---|---|---|---|---|---|---|
| 2025-03-04 | Tue | 0.00 | 1.00 | Y | . | Y | Y / Y / Y / Y | full stall |
| 2025-05-03 | Sat | 0.12 | 0.27 | Y | . | . | Y / Y / . / Y | partial stall, frozen misses |
| 2025-05-04 | Sun | 0.09 | 0.02 | Y | . | . | Y / Y / . / Y | partial stall, frozen misses |
| 2025-07-16 | Wed | 0.68 | 0.42 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2025-07-23 | Wed | 0.75 | 0.49 | . | . | Y | . / . / Y / Y | extra |
| 2025-08-13 | Wed | 0.39 | 0.76 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2025-08-16/17/19 | Sat/Sun/Tue | 0.00 | 1.00 | Y | . | Y | Y / Y / Y / Y | full stall |
| 2025-09-10 | Wed | 0.27 | 0.80 | Y | . | Y | Y / Y / Y / Y | |
| 2025-10-01 | Wed | 0.67 | 0.54 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2025-10-08 | Wed | 0.51 | 0.71 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2025-10-15 | Wed | 0.00 | 1.00 | Y | . | Y | Y / Y / Y / Y | |
| 2025-11-05 | Wed | 0.83 | 0.40 | . | . | Y | . / . / Y / Y | extra |
| 2025-11-26 | Wed | 0.46 | 0.75 | . | . (sum 2.41, band edge) | Y | . / . / Y / Y | reviewer |
| 2025-12-17 | Wed | 0.30 | 0.75 | . | . | Y | . / . / Y / Y | extra (r=0.30 exactly at LOW; catch-up lands 12-19) |
| 2026-01-28 | Wed | 0.53 | 0.49 | . | . | Y | . / . / Y / Y | extra; next day 0.49 too |
| 2026-02-11 | Wed | 0.59 | 0.65 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2026-04-01 | Wed | 0.25 | 0.01 | Y | . | . | Y / Y / . / Y | partial stall, frozen misses |
| 2026-04-29 | Wed | 0.67 | 0.53 | . | Y | Y | . / Y / Y / Y | reviewer |
| 2026-05-12 | Tue | 0.70 | 0.52 | . | . | Y | . / . / Y / Y | extra |
| 2026-06-13 | Sat | 0.18 | 0.00 | Y | . | . | Y / Y / . / Y | counters rolled back (39% of models decreased), frozen misses |
| **2026-06-25** | Thu | 0.56 | **0.03** | . | **Y** (pair with 06-24: 1.56) | . | . / Y / . / . | reviewer, pair-only |
| 2026-07-08 | Wed | 1.26 | 0.61 | . | . | Y | . / . / Y / Y | extra; r above 1 (a surge, see 4.3) |
| 2026-07-20 | Mon | 0.00 | 1.00 | Y | . | Y | Y / Y / Y / Y | |
| 2026-07-29 | Wed | 0.44 | 0.77 | . | Y | Y | . / Y / Y / Y | reviewer |
| **2026-08-01** | Sat | 0.54 | **0.004** | . | not at 2.4 band (sum 2.40); yes at 1.3-3.0 | . | . / . / . / . | reviewer, pair-only |
| 2026-08-05 | Wed | 0.59 | 0.71 | . | Y (pair with 08-04: 1.60) | Y | . / Y / Y / Y | reviewer |
| 2026-08-12 | Wed | 0.56 | 0.78 | . | . (partner 3.28, sum 3.84) | Y | . / . / Y / Y | reviewer; real surge follows |
| 2026-08-28 | Fri | 0.00 | 1.00 | Y | . | Y | Y / Y / Y / Y | |
| 2026-09-02 | Wed | 0.54 | 0.58 | . | Y | Y | . / Y / Y / Y | extra |
| 2026-09-09 | Wed | 0.19 | 0.87 | Y | . | Y | Y / Y / Y / Y | |
| 2025-09-17 | Wed | 0.95 | **0.343** | . | . | . (just below 0.35) | . | extra, marginal: my frozen share is 0.343 |

Notes:
- Of the reviewer's 12 days: pair (strict sum band 1.6-2.4) catches 10 (not 2025-11-26 sum 2.41, not 2026-08-01 sum 2.40, and 2026-08-12 has sum 3.84); frozen catches 10 (not 2026-06-25, 2026-08-01). Union: all 12 except 2026-08-01 under the strict band (the band 1.3-3.0 or <=2.6 catches it, but see 6.2).
- Frozen-share's 8 "extra" days: 7 of 8 flagged (2025-09-17 = 0.343 is below 0.35; threshold sensitivity: share>0.30 gives 29 days/24 windows, 0.35 gives 28/23, 0.40 gives 27/22, 0.50 gives 24/19, so the rule is stable between 0.30 and 0.40, but 2025-09-17 and 2025-11-05 sit on the edge).
- Pair sensitivity (B_7): with `lo` 0.6-0.8, `hi` 1.3, sum band 1.6-2.4 the only non-frozen pair is 2026-06-25 (08-01 enters when `hi`=1.2). Loosening to `lo`=0.85, `hi`=1.2 starts to pick ordinary jitter (2025-10-12 Sun 0.83, 2025-11-07 Fri 0.84, 2025-05-19 which is the rollback). So the pair rule has a narrow safe zone; it works because pairs of that shape are rare (10 in 584 days).
- Share distribution over all days: median 0.003, p90 0.18, p95 0.27, p99 1.0. Two-day windows add the "next day always"; most frozen windows have a 2-3x next day for the frozen models.

### Windows produced (pair|frozen; recommended). r = raw ratios, frozen share in brackets only where flagged

| window | days | r (raw) | source |
|---|---|---|---|
| 2025-03-04..03-05 | 2 | 0.00, 1.00 | cur+frozen (published) |
| 2025-05-03..05-06 | 4 | 0.12, 0.09, 0.63, 2.45 | cur (published) |
| 2025-07-16..07-19 | 4 | 0.68, 1.39, 1.00, 1.43 | pair+frozen (over-extended: 07-18 normal, lookahead to 07-19) |
| 2025-07-23..07-24 | 2 | 0.75, 1.56 | frozen |
| 2025-08-13..08-21 | 9 | 0.39, 1.78, 1.07, 0, 0, 0.88, 0, 2.60, 2.18 | merges 08-13 half stall with published 08-16..21 |
| 2025-09-10..09-11 | 2 | 0.27, 1.69 | cur+frozen (published) |
| 2025-10-01..10-02 | 2 | 0.67, 1.33 | pair+frozen |
| 2025-10-08..10-09 | 2 | 0.51, 1.87 | pair+frozen |
| 2025-10-15..10-16 | 2 | 0.00, 2.34 | cur+frozen (published) |
| 2025-11-05..11-06 | 2 | 0.83, 1.23 | frozen |
| 2025-11-26..11-27 | 2 | 0.46, 1.95 | frozen |
| 2025-12-17..12-19 | 3 | 0.30, 0.76, 2.25 | frozen |
| 2026-01-28..01-29 | 2 | 0.53, 0.49 | frozen (no catch-up, see 4.2) |
| 2026-02-11..02-12 | 2 | 0.59, 1.47 | pair+frozen |
| 2026-04-01..04-02 | 2 | 0.25, 1.00 | cur (published) |
| 2026-04-29..04-30 | 2 | 0.67, 1.57 | pair+frozen |
| 2026-05-12..05-13 | 2 | 0.70, 1.33 | frozen |
| 2026-06-12..06-14 | 3 | 2.05, 0.18, 1.24 | cur (published) |
| 2026-06-24..06-25 | 2 | 1.56, 0.56 | pair only |
| 2026-07-08..07-09 | 2 | 1.26, 1.93 | frozen (surge) |
| 2026-07-20..07-23 | 4 | 0.00, 1.01, 1.74, 1.82 | cur+frozen (published) |
| 2026-07-29..07-30 | 2 | 0.44, 1.78 | pair+frozen |
| 2026-08-04..08-06 | 3 | 1.60, 0.59, 1.21 | pair+frozen |
| 2026-08-12..08-15 | 4 | 0.56, 3.28, 1.83, 1.63 | frozen (surge) |
| 2026-08-28..09-04 | 8 | 0.00, 1.83, 1.96, 0.91, 1.38, 0.54, 0.99, 1.97 | merges published 08-28..30 with 09-02 half stall |
| 2026-09-09..09-10 | 2 | 0.19, 1.96 | cur+frozen (published) |

Per rule (full lists printed in `B_3_rules.py` output; `rules.json`): current = the 10 published windows; frozen alone = the table above without 2025-05-03, 2026-04-01, 2026-06-12 and 2026-06-24..25, and with 2026-08-28..30 and 2026-09-02..04 as separate windows; pair = current windows (2025-08-13 and 2026-08-28..09-02 merged into them) + the 10 pair windows (incl. 2026-06-24..25), without the frozen-only days.

## 3. Effect on the daily series (Q3)

`r` = ratio of the smoothed daily total to its own centred 15-day median (days up to last-3; 581 days). Windows smoothed per tag with `stalls.smooth`; grand total conserved to within rounding (+-40 downloads) for every rule.

| series | days outside 0.7-1.3 | below 0.7 | above 1.3 | below 0.5 | above 2 | std of log r | MAD of r |
|---|---|---|---|---|---|---|---|
| raw | 90 | 43 | 47 | 22 | 12 | 0.82 | 0.092 |
| current (published) | 70 | 34 | 36 | 10 | 7 | 0.262 | 0.087 |
| pair (current+pair) | 49 | 23 | 26 | 7 | 8 | 0.238 | 0.076 |
| frozen alone | 52 | 28 | 24 | 8 | 7 | 0.276 | 0.071 |
| frozen+cur | 48 | 25 | 23 | 4 | 5 | 0.224 | 0.072 |
| pair|frozen | **45** | 23 | 22 | 4 | 5 | **0.218** | **0.064** |

(B_6, tight variants: restricting catch-up to "next day plus consecutive >1.3 days" is WORSE: 56 outside, std 0.244, and it loses the real catch-ups of 2025-05-06, 2025-12-19, 2026-09-04. Keep the stalls.py 3-day look-ahead.)

Weekday pattern. Mean `r` by weekday (Mon..Sun) on days outside every rule's windows: 0.896, 1.007, **1.182**, 1.097, 1.084, 1.006, 0.917 (Wednesday is the busiest day on clean weeks). Over all days, raw: 0.88, 1.01, 1.05, **1.23**, 1.11, 1.00, 0.91 (Thursday inflated by catch-up, Wednesday deflated). After pair|frozen: 0.894, 0.990, 1.143, 1.085, 1.081, 1.006, 0.909, i.e. the profile is restored; Wednesday ends about 3% below its clean-week level because windows average Wed (1.18) with Thu (1.10). Weekday-adjusted noise (std of log of r / weekday profile): raw 0.64, current 0.260, pair 0.232, frozen 0.266, frozen+cur 0.213, pair|frozen 0.208.

Do any rules flatten something that looks real? Window total / (sum of median x weekday factor) per window (B_3, B_6):
- `~1.0` (0.86-1.05): delayed downloads; flattening is right. This is 17 of 25 windows.
- **Surges, not delays (ratio 1.4-1.7): 2026-07-08..09 (1.40) and 2026-08-12..15 (1.69).** Frozen flags them because half of the models stood still on the first day, but the whole hub (also the non-frozen models, 1.5-1.6x and 1.6x) was up. Spreading conserves the sum but smears a real 3-day rise into 4 days at 1.56-1.68x. Frozen-share would also flatten 2026-08-12..15 more than a total-based rule would.
- **Low ratio (about 0.45-0.55): 2025-03-04..05 (0.46), 2026-01-28..29 (0.44), 2026-04-01..02 (0.55), 2025-12-17..18 if cut to two days (0.46; fine with 3 days: 0.98).** No catch-up arrives: downloads are lost or under-booked, so smoothing only turns "0 then 1.0" into "0.5 and 0.5". Harmless to totals but the dip is real. 2026-04-01 is followed by a 17-day snapshot gap (catch-up hidden inside the gap average), 2026-01-28 is a multi-day outage (F profile 0, 1.24, 0.40, 0.78).
- 2025-05-03..06 looks lost at 4 days (0.87) but over the full 6 days to the next gap (05-03..05-08) it is 0.99: delayed.

## 4. Conservation: delayed or lost? (Q4)

Per episode: F = big models with delta == 0 on the stall day d*. Window actual vs baseline x days, baseline = each model's median daily delta within +-28 days outside all windows/dips; control = same F models in windows of the same length shifted by multiples of 7 days (keeps weekday mix). F_ratio = sum(actual)/sum(expected). F/control above ~1 means downloads were delayed, not lost. (`q4_episodes.csv`.)

| episode | d* (dow) | share | F models | F ratio | control | F/ctrl | non-frozen ratio | F next-day profile |
|---|---|---|---|---|---|---|---|---|
| 2025-07-16..19 | Wed | 0.42 | 484 | 1.22 | 1.13 | 1.08 | 1.21 | 0, 2.37, 0.87 |
| 2025-07-23..24 | Wed | 0.49 | 721 | 1.95 | 1.29 | 1.51 | 1.17 | 0, 3.90 |
| 2025-08-13..21 | Sat (full) | 1.00 | 1,521 | 1.12 | 1.02 | 1.10 | 0.03 (the 32 non-frozen) | |
| 2025-09-10..11 | Wed | 0.80 | 978 | 1.05 | 0.98 | 1.07 | 1.07 | 0, 2.10 |
| 2025-10-01..02 | Wed | 0.53 | 612 | 1.09 | 1.34 | 0.81 | 1.06 | 0, 2.19 |
| 2025-10-08..09 | Wed | 0.71 | 1,123 | 1.38 | 1.23 | 1.12 | 1.11 | 0, 2.75 |
| 2025-10-15..16 | Wed | 1.00 | 1,599 | 1.36 | 1.18 | 1.15 | 0.11 | 0, 2.73 |
| 2025-11-05..06 | Wed | 0.40 | 656 | 1.19 | 1.24 | 0.96 | 1.12 | 0, 2.38 |
| 2025-11-26..27 | Wed | 0.75 | 1,254 | 1.49 | 1.31 | 1.13 | 1.16 | 0, 2.98 |
| 2025-12-17..19 | Wed | 0.75 | 1,274 | 1.33 | 1.34 | 0.99 | 1.17 | 0, 1.25, 2.74 (catch-up on day +2) |
| 2026-01-28..29 | Wed | 0.49 | 863 | **0.62** | 1.46 | **0.42** | 0.50 | 0, 1.24, 0.40, 0.78 (lost) |
| 2026-02-11..12 | Wed | 0.65 | 1,153 | 1.09 | 1.29 | 0.85 | 1.10 | 0, 2.18 |
| 2026-04-29..30 | Wed | 0.53 | 1,076 | 1.68 | 1.11 | 1.52 | 1.08 | 0, 3.36 |
| 2026-05-12..13 | Tue | 0.52 | 1,056 | 1.19 | 0.99 | 1.20 | 1.05 | 0, 2.38 |
| 2026-07-08..09 | Wed | 0.61 | 1,349 | 1.57 | 1.12 | 1.40 | 1.54 | 0, 3.14 (surge, all models up) |
| 2026-07-29..30 | Wed | 0.77 | 1,745 | 1.37 | 1.19 | 1.16 | 1.12 | 0, 2.74 |
| 2026-08-04..06 | Wed (08-05) | 0.71 | 1,622 | 1.00 | 1.18 | 0.85 | 0.77 | 1.39 (08-04), 0, 1.60 |
| 2026-08-12..15 | Wed | 0.78 | 1,791 | 1.97 | 1.21 | 1.63 | 1.63 | 0, 4.0, 2.0, 1.85 (surge) |
| 2026-09-09..10 | Wed | 0.87 | 2,131 | 1.22 | 1.12 | 1.09 | 1.11 | 0, 2.43 |

Reading: for the 12 reviewer days that have a frozen subset, F/control has median about 1.1 (range 0.81-1.63); typical frozen models do exactly zero on d* and 2.1-3.4x their baseline the next day, while non-frozen models stay at about 1.0-1.2. That is a delay of about one day (spreading is right and conserves). Three episodes (2025-10-01, 2026-02-11, 2026-08-05) show 15-19% shortfall vs control: mild possible loss, not clear-cut. Two are genuinely lost or unobservable: 2026-01-28 (F/ctrl 0.42, no catch-up) and 2026-04-01 (F set is only 20 models, hub 0.25 then a 17-day snapshot gap). The first week of data (2025-03-04) is unreliable (only 32 non-frozen models, baseline from 3-day gap).

Hub-level conservation (window total / expected) agrees: 0.86-1.05 for the typical half stalls.

### 4.1 What happened on 2026-06-25 and 2026-08-01 (pair-only days)

| | 2026-06-24 Wed | **2026-06-25 Thu** | 2026-07-31 Fri | **2026-08-01 Sat** | 2026-08-02 Sun |
|---|---|---|---|---|---|
| hub total (M) | 176.1 | 60.9 | 126.1 | 50.9 | 173.3 |
| ratio to median | 1.56 | 0.56 | 1.23 | 0.54 | 1.86 |
| frozen share | 0.000 | 0.029 | 0.000 | 0.004 | 0.001 |
| big-model act/base quantiles 5/25/50/75/95% | 0.92/1.38/**1.59**/1.89/2.93 | 0.0/0.53/**0.62**/0.73/1.08 | 0.70/1.02/1.14/1.39/2.11 | 0.28/0.39/**0.45**/0.54/0.91 | 1.0/1.40/**1.65**/1.89/3.12 |
| share of big models below 0.05 / in 0.05-0.5 | 0.00 / 0.02 | 0.07 / 0.11 | 0.01 / 0.01 | 0.01 / **0.65** | 0.00 / 0.00 |

- It is NOT a single-model swing: the top-1 model explains 7% (06-25) and 10% (08-01) of the hub deviation, top-5 19% and 22%, top-20 33% and 35%. Biggest movers are the usual giants (all-MiniLM-L6-v2 -3.3M on 06-25, +5.8M on 06-24; bert-base-uncased -2.5M, 0 downloads that day).
- It is NOT a subset freeze either (compare frozen half stalls: median ratio 0.0 with 50-70% of models at exactly 0). Models move together: 65% of big models are at 0.05-0.5 of normal on 08-01 and the median is 0.45; on the neighbour day the median is 1.59 / 1.65 (and 1.14 the day before 08-01). Tags all move the same way: 06-25 text-generation 0.59, sentence-similarity 0.64, image-text-to-text 0.58, other 0.59; fill-mask 0.18 (a BERT-heavy tag, bert-base-uncased at 0).
- Pair sums are 2.12 (06-24+06-25) and 2.40 (08-01+08-02): downloads were shifted by about half a day between two consecutive snapshots (interval timing), consistent with "downloads delayed, not lost". Window ratio 0.94-1.07 (06-24..25: 1.07 of median; 07-31..08-02: 1.21).
- Weekday: 06-25 is a Thursday (follows a Wednesday spike, the usual Wednesday catch-up slot shifted); 08-01 is a Saturday, a low weekday (about 0.9), so the weekday-adjusted dip is 0.6 not 0.54. In the 8 days around 2026-08-01 the series has five distinct events (07-29, 08-01, 08-05 half stalls, 08-04 and 08-12): the Aug 2026 period is simply unusually volatile.

### 4.2 Other conservation notes
- 2026-06-12..14: the first day (2.05) follows a 19-day snapshot gap; 06-13 is the counter rollback (section 5); frozen share is 0.0 because counters moved by tiny non-zero amounts (92% of big models at <5% of normal).
- 2026-06-12 window cons 1.12 only appears conserved because phantom rebound is inside (section 5).

## 5. Spikes that must not be smoothed (Q5)

Days with r>1.5 on the raw series: 36. Those at or next to a flagged day are catch-up days. Not adjacent (nearest seed more than 3 days away): 2025-03-09 (1.83, Sunday), 2025-04-25 (1.51), 2025-05-21 (7.45), 2025-05-23 (2.08), 2025-07-10 (1.59), 2026-03-19 (1.67), 2026-06-17/18/19 (2.26, 3.49, 3.82), 2026-07-17 (1.55).

**2025-05-21 (7.45x, 441.8M vs median 59.3M):** not driven by any model. 1,099 of 1,149 big models are above 2x their baseline; top model 6.8% of the excess (Falconsai/nsfw_image_detection 30.7M vs 4.6M), top-5 27%; every tag is 6-13x (ASR 12.8x, zero-shot-image-classification 10.5x, image-classification 8.1x, sentence-similarity 8.6x). Cause found in the deltas: on 2025-05-19 and 05-20 the counters FELL for 146k and 174k models (16%/19% of all models; `dl_all` summed over models: -116M and -324M; 30% and 68% of big models), then recovered on 05-21 (all-model positive mass 441.8M, negative mass about 0). `clip(0)` ignores the dip and counts the rebound as new downloads. Net `dl_all` growth 05-18..05-21 is 167M clipped (55.7M/day, normal) vs 566M recorded. **It is a counting artifact, not real traffic and not a stall catch-up**; the 05-19/05-20 days are also not low in the clipped series (0.81, 1.29), which is why no total-based rule sees it, and why the PAIR rule leaves it alone ("no low neighbour").
- 2025-05-23 (2.08x): real, concentrated: fill-mask tag 10.5x (63.9M vs 6.1M), 89% of the deviation; bert-base-uncased 29.1M vs 2.0M (42% of the hub deviation), roberta-large 15.5M vs 0.76M; top-5 86.5%. Looks like a genuine model-level spike (mass download of BERT-family models). Leave it alone.
- 2026-06-17/18/19 (2.26, 3.49, 3.82): all tags 3-5x, 1,749-2,009 of 2,240 big models above 2x, top-1 about 9-10%. Same rollback artifact: on 2026-06-13 the counters FELL for 557k models (39%, -541M; 91% of big models); the recovery lands 06-14..06-19 (all-model positive mass 110, 118, 88, 266, 411, 449M; baseline about 110M) beyond the 3-day look-ahead of the window logic, so the published series still has 2.26 / 3.49 / 3.82 there. Treating 06-11->06-19 as one interval gives 131M/day (normal).
- 2025-03-09 (1.83, Sunday), 2025-04-25, 2025-07-10, 2026-03-19, 2026-07-17: not investigated beyond ratio; none is near a flagged day and none is touched by any rule.
- 2026-08-12..15 (3.28, 1.83, 1.63) and 2026-07-08..09 (1.93): see section 3, a real hub-wide rise on top of a frozen subset; frozen-share and frozen+cur windows smooth them (sum conserved).

Check: 2025-05-21, 2025-05-23, 2026-06-17/18/19, 2025-03-09, 2025-04-25, 2025-07-10, 2026-03-19 and 2026-07-17 lie outside the windows of ALL rules (current, pair, frozen, frozen+cur, pair|frozen). Pair and frozen only touch the surges directly attached to a dip (07-08/09, 08-12..15, which is intended for catch-up).

## 6. Recommendation (Q6)

### 6.1 Rule
Use the **union**: flag a day if `r<0.3` (current, catches partial stalls and rollbacks where counters tick but do not freeze) OR frozen share of big models above 0.35 (catches Wednesday half stalls even when the total dips only to 0.7-0.95) OR the pair test (0.3<=r<0.7 next to r>1.3, sum 1.6-2.4; catches timing shifts like 2026-06-25). Windows by the unchanged stalls.py logic (next day always, up to +3 days if >1.3x, day before if >1.5x, merge <=2 days). Result: 26 windows, 76 days, 50 skip_days (listed in section 2), best on every roughness metric (45 days outside 0.7-1.3 vs 70 now; std of log r 0.218 vs 0.262; MAD 0.064 vs 0.087; weekday profile restored).

Why not each alone: PAIR alone leaves 07-23, 11-05, 11-26, 12-17, 01-28, 05-12 (and 08-12 by sum), frozen alone drops 3 of the 10 published windows. The union costs only 2 pair-only windows on top of frozen+cur (2026-06-24..25 and, if the sum band is widened, 2026-08-01..02).

Caveats of the union to decide on:
- Frozen share is not robust at the edge (2025-09-17 0.343 and 2025-11-05 0.40 are marginal; windows with `r>=0.83` such as 2025-11-05 (0.83/1.23) only smooth a normal wobble). Consider requiring `r<0.85` or a neighbour >1.15 in addition to share>0.35. Note 2026-07-08 (r=1.26) and 2026-08-12 are flagged by frozen share though the day-level total is not a dip (they are surges).
- The pair band: widening the sum to 2.6 adds 2026-08-01 but merges 2026-07-29..08-06 into a 9-day window and does not improve roughness (47 vs 45). Keep 1.6-2.4 and accept 08-01 as an unflagged timing shift, or add it by hand.
- Windows with conservation far below 1 (2025-03-04, 2026-01-28, 2026-04-01) are dips, not delays; spreading is harmless but flags something that stays low.

### 6.2 Difference from the published `skip_days`
Published (20): 2025-03-04, 2025-05-03/04/05, 2025-08-16..20, 2025-09-10, 2025-10-15, 2026-04-01, 2026-06-12/13, 2026-07-20/21/22, 2026-08-28/29, 2026-09-09. Recommended (50) keeps all 20 and **adds 30**: 2025-07-16, 07-17, 07-18, 07-23, 2025-08-13, 08-14, 08-15, 2025-10-01, 2025-10-08, 2025-11-05, 2025-11-26, 2025-12-17, 12-18, 2026-01-28, 2026-02-11, 2026-04-29, 2026-05-12, 2026-06-24, 2026-07-08, 2026-07-29, 2026-08-04, 08-05, 2026-08-12, 08-13, 08-14, 2026-08-30, 08-31, 2026-09-01, 09-02, 09-03. (Window ends are not skip days: the last day of each window keeps its snapshot.)

### 6.3 Rollback fix (new, not asked, but it is the biggest remaining outlier source)
The three biggest residual outliers (2025-05-21 7.45x; 2026-06-17..19 2.3-3.8x) are counter rollbacks followed by recovery, invisible to `r<0.3`, frozen share, and pair. Detector: share of models with a negative `dl_all` delta above ~5% on a day (2025-05-19 16%, 05-20 19%, 2026-06-12 5%, 06-13 39% of all models; among big models 30%, 68%, 4.7%, 91%; the next highest day is 1.5%). Treatment: add the snapshots from the first rollback day to the recovery to `skip_days` AND recompute the hub totals from the bounding snapshots (net `clip` of the interval, spread evenly) instead of smoothing the already-clipped daily sums (smoothing would conserve the phantom 0.38-0.56B). With that: 05-18->05-21 = 55.7M/day, 06-11->06-19 = 131M/day, both normal.
Tested and rejected: a per-model high-water mark (`max(0, a_t - max_{<t} a)`): it fixes 2025-05-21 (7.45x -> 2.1x) but 2026-06 shows 643k models standing below their old max before the 06-13 dip (deficit 264M, 473k models still below at 2026-10-04), so it suppresses genuine downloads for days (06-14..17 collapse to 0.17-0.55x, 06-19 4.65x) and lowers the grand total by 2.4%.

### 6.4 Remaining open issues
- Why Wednesdays: 83 Wednesdays, 21 with a frozen subset; worth asking whether this follows a weekly Hub job. If it is regular, a calendar-aware prior (Wednesday + next day) would be a simpler detector.
- Data in snapshot gaps (17 intervals, one of 36 days) is flat by construction; rules should not be evaluated there.
- Per-tag tags in published series differ from the current `models.pipeline_tag` for about 5.6% of mass (tags at build time); irrelevant to totals but relevant to per-tag smoothing comparisons.
