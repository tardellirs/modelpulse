# Audit D: hub-level MODEL totals and what is derived from them

Read-only. Data: published `hub_series.parquet` + `meta.json` (built 2026-10-04, 584 calendar days 2025-02-28..2026-10-04, 43,476,273,236 downloads, 59 skip_days, 24 low_days) and, on the server (read-only, docker `--memory 4g`, finished 07:55 local), the per-model `series/*.parquet` (683 snapshot days, 493 with dl_all).
Scripts next to this file: `D_1_daystats.py` (server, per-snapshot hub stats), `D_3b_boundaries.py` (server, month-boundary diffs), `D_3_permodel.py` (server, per-model/quarter and spike-day deltas), `D_2_hub.py`, `D_4_tags.py`, `D_5_weekday.py`, `D_6_conserve.py`, `D_7_lowruns.py`, `D_8_tagdrift.py`, `D_9_checks.py`, `D_10_boundary.py`, `D_11_week.py`, `D_12_spikes.py` (local, small inputs). Intermediates live in the session scratchpad, not in the repo.
Not repeated: A/B/C analyses (frozen metric, rule variants, datasets timing). Where I lean on them it is marked.

## 0. Headline findings

| # | Finding | Severity | Reviewer likely? |
|---|---|---|---|
| 1 | Several `low_days` ARE made up, by a neighbouring spike the rules cannot pair (pair-sum edge, 3-day catch-up limit, gap dilution). 7 of the 13 low-day runs (13 of 24 days) net to about zero within +-3 days. | high | yes, it is his own line of attack |
| 2 | Every spike above 1.3x that I decomposed is a broad counter artefact, not a release: 80-90% of big models run at 1.8-2.8x on the same day. None is "real". Some are the catch-up of an earlier dip that the 3-day window cannot reach. | high | yes |
| 3 | 2025-11-24 hub-stats snapshot has only 289,425 of 1,130,658 models (74% missing). Nothing detects it; 11-24 and 11-25 sit at 0.72 and 0.82 of median (above the 0.7 low-day cut) and about 30M downloads are lost. | medium | yes (visible dip, no marker) |
| 4 | Gap spreading dilutes stalls: after a missing day the stall depth is averaged with the gap (r 0.74 instead of 0.5), so it escapes both the stall and the pair rule. Pairs of days, 2025-12-04/05 and 2026-03-17/18, show it, plus 2026-04-01/02 where the catch-up falls into a 17-day gap average. | medium | probably |
| 5 | `dl30` summed over models is NOT the rolling 30-day sum of the daily series: ratio 1.00 until June 2025, then a step to about 0.965 from 2025-07-09 (the end of the 36-day gap), 0.91-0.94 in Jun-Jul 2026. The Hub's own 30-day field and the all-time counter disagree by 3-9% in aggregate. | medium | yes if he sums dl30 |
| 6 | "This week" numbers on the leaderboards use a window longer than 7 days on 17% of possible dates (the 7-day anchor is a skip day, so an earlier snapshot, up to 10 days back, is used); the last snapshot is never skipped, so a stalled Wednesday goes into "this week" unsettled. | medium | maybe |
| 7 | Weekly cycle is mild (Sun and Mon about 0.87 of median, Wed-Fri 1.05). 5 of 24 low days (the Sun/Mon pairs 2026-01-18/19, 2026-02-01, 2026-09-06/07) stop being low after a weekday adjustment; 3 more are marginal. | low | yes, easy to see |
| 8 | Deleted/untagged models and tag drift: small. 217,684 models gone from today's snapshot hold 0.24B (0.54%) of downloads, reassigned to "other" for all history (1.3% of 2025Q1, 0.3% in 2026). Tag changes move 0.7-2.9% of a quarter. | low | maybe |
| 9 | Conservation checks out. Sum of positive deltas 44.453B, minus 0.977B rollback phantom, equals the published 43.476B; identity pos+neg+new-gone = net growth holds to 1.4M. Hub vs monthly boundary differences within +-2%. | OK | n/a |
| 10 | The stalled-window plateaus 2026-06-12..19 (135M/day) and 2026-08-12..15 (172M/day) are consistent with the counters (dl30 recovers to 0.98 of the rolling sum on 06-19), so not phantom. Spike/plateau values in spread windows look odd but conserve. | OK / low | maybe |

### Finding 1. low_days that something does make up

What. `low_days` is documented as "fell behind and never caught up". The chart note says the same. I compared each run's deficit against the surplus in its surroundings (`D_7_lowruns.py`; baseline = median of days -21..-8 and +8..+21 around the run, no weekday adjustment). Net balance over run +-3 days, in "normal days":

| run | net +-3 | reading |
|---|---|---|
| 2025-07-13/14 | -0.01 | made up: 07-10 is +34M (1.59x), 07-13/14 are -49M. The spike comes 3 days BEFORE the dip (just after the 36-day gap ended 07-09) |
| 2025-12-04/05 | -0.13 | made up 98%: 27M, 27M, then 82M x4 (12-06..09 is one 4-day average of the 12-09 snapshot) |
| 2026-08-01 | +0.20 | made up: 08-01 51M (0.54), 08-02 173M (1.86). Pair sum 0.542+1.861 = 2.403, the PAIR_SUM upper bound is 2.4: missed by 0.003 |
| 2026-09-06/07 | +0.19 | 09-04 is +105M (1.97x raw, spike), 09-05 121M; the dip is the weekend |
| 2026-07-19 | +0.97 | made up: 07-17 +50M (1.45x), 07-20..22 window |
| 2026-01-18/19 | +0.80 | Sun/Mon in a week with a +67M surplus before |
| 2026-06-20 | +3.8 | inside the post-rollback regime, baseline not meaningful |
| 2025-03-04/05 | -1.55 | stall 03-04; the catch-up is 03-09 (142M, +64M) 5 days later, beyond the 3-day limit. Magnitudes match (-83M vs +64M) |
| 2025-11-08/09 | -0.82 | really lost (and 2,000-4,500 models went down on those days) |
| 2026-01-28..02-01 | -2.90 | really lost: about 175M. Five days at 31, 31, 22, 42, 42M against 61-70M; frozen share 0.016 on 01-30, so not a freeze |
| 2026-04-01/02 | -1.28 | see finding 4 |
| 2026-06-30 | -1.45 | 101, 88, 80, 66 then 123 (07-01); gradual slide, not a freeze |
| 2025-04-23 | -0.4 | lost |

So 13 days that are listed as "never made up" are made up within three days; about 8 normal days (roughly 0.6B, 1.4% of the total) are really lost. Frozen share on all of these low days is under 0.05 (checked in `stats`, n_big_zero/n_big): they are uniform dips, not Wednesday-type partial freezes.
Why the rules miss them. (a) PAIR_SUM caps the pair at 2.4; (b) catch-up is searched at most 3 days after a stall and 2 days before; the 07-10 -> 07-13 (3 days before) and 03-04 -> 03-09 (5 days after) cases are out of reach; (c) a low day next to a window is not merged (07-19 sits right before the 07-20..22 window; the "a-1" extension only fires if r>1.5).
Verified how. Published daily totals; frozen shares from the per-model series.
Fix. Judge low_days by a local balance, not by the day: after settling, list a run only if the sum over run +-3 days is below, say, -0.5 normal days; and extend PAIR_SUM to about 2.6 or test "dip day plus any neighbour within 3 days whose excess is at least 60% of the deficit". Alternatively, spread the dip and its neighbour (a pair window), as already done for other pairs.

### Finding 2. Spikes: counter artefacts, not releases

Method. For spike days I took every model with |delta| >= 500, and compared its per-day delta on D with the mean of D-2, D-1, D+1, D+2 (`D_12_spikes.py`). Day-level concentration is in `D_9_checks.py`.

| day | excess over local median | top-10 models' share of excess | big models (>=5k/day) with ratio > 1.5 | median ratio of those | top-1 model |
|---|---|---|---|---|---|
| 2025-03-09 | 69M | 35% | 737 of 973 | 1.90 | timm/mobilenetv3_small_100 (2.6x) |
| 2025-07-10 | 47M | 36% | 515 of 759 | 2.02 | Falconsai/nsfw_image_detection |
| 2026-03-19 | 73M | 15% | 769 of 1,053 | 2.77 | sentence-transformers/all-MiniLM-L6-v2 |
| 2026-07-08 | 63M | 35% | 664 of 794 | 1.81 | all-MiniLM-L6-v2 |
| 2026-08-02 | 78M | 28% | 1,191 of 1,653 | 1.80 | all-MiniLM-L6-v2 |

Across the 43 gap-1 days with raw ratio > 1.3, 75-100% of the excess is in the top 1,000 models, which is also where 89% of all downloads sit, so that alone proves nothing; the discriminating fact is that 70-90% of the big models are up together at about 2x and the number of models that moved (`n_up`) is 1.1-3x its median. A release would show one to a few models at 10x. The biggest single contributor adds 3-8M of a 50-80M excess. Conclusion: none of these is a real spike; they are one day's counters booked twice, balanced by a thin neighbour (see finding 1: 2026-03-19 vs 03-17/18; 2026-08-02 vs 08-01; 2025-07-10 vs 07-13/14; 2025-03-09 vs 03-04/05).
Open: 2026-06-17/18/19 (raw 2.3x, 3.5x, 3.8x) and 2025-05-21 (7.4x) are rollback recoveries (B covered); the published series is settled there (see finding 10).
Severity. High only because the site's chart still shows 2026-03-19 (130M, 1.67x), 2025-03-09 (142M, 1.83x), 2026-08-02 (173M, 1.86x), 2025-07-10 (91M), 2026-07-09 (162M), 2026-07-17 (158M) as single-day peaks, and the Jan 2026 numbers etc. Fix: widen the pair/catch-up rule as in finding 1 and spread; a reviewer will otherwise point at those peaks.

### Finding 3. A truncated snapshot (2025-11-24) goes unnoticed

`n_cur` by snapshot: 11-23 1,130,658; **11-24 289,425**; 11-25 1,134,263. 841,310 models disappear and 844,846 "new" ones appear a day later (3.96B and 3.98B of all-time counters entering and leaving: bookkeeping, not downloads).
Effect: the increment joins the two snapshots on id, so the 841k models absent on 11-24 contribute to neither 11-24 nor 11-25: published 46.5M (r 0.72) and 53.1M (r 0.82) where 2 x 65M is expected; about 30M (0.07% of total) lost. dl30 sum on 11-24 is 1.543B vs 1.79B around it (ratio 0.84). Neither day is below PAIR_LOW, so neither is in low_days. Per-model series for 841k models simply have a missing day. The frozen share on that day is computed on a biased subset (n_big 1,314 instead of about 1,900).
Other model-count jumps (|dn| > 1%): 2026-02-05/06 (1,212,984 -> 1,171,652 -> 1,215,771, 41,492 models absent for one day; hub effect about 8M, r 1.0 and 1.2 so invisible), plus the multi-day gaps. Same mechanism, smaller.
Fix: add a snapshot sanity rule (model count down more than 5% vs the previous snapshot => treat as missing day, i.e. do not compute a delta against it, spread across the gap). For 2026-02-05 the same rule would have caught it at 3.4%.

### Finding 4. Gap spreading hides stalls

`hub_series` spreads an interval of g days evenly. A stall at the snapshot after a missing day is diluted: 2026-03-18 (gap 2) shows two days of 58M (r 0.74, above PAIR_LOW 0.7, but sum with the 03-19 spike 0.74+1.67 = 2.41 > 2.4), and 03-19 is +52M (1.67x, finding 2). 2025-12-05 (gap 2, then gap 4): 27M, 27M, then 82M x4: the stall is on a snapshot with a gap before and a gap after, so r on the neighbouring spread days is 1.19, under HIGH 1.3. The frozen signal is recorded only for gap == 1 days (`measure`), and the 23 snapshots after a gap > 1 are not tested for frozen at all (their frozen shares are all < 0.035, so there is nothing missed there in practice).
2026-04-01/02: snapshot 04-01 is a stall (21M, r 0.25), then a 17-day gap (04-18 snapshot averaged at 84.8M/day). windows() takes the next day (04-02, which is just 1/17th of the gap average) as catch-up, so the window is 21M + 85M spread over two days = 53M each; the real catch-up (about 64M) is smeared inside the 16 other days (85M vs 83M local median, about +2M each = +32M visible). Net: two days at 0.63x are listed as low days.
Double handling: I found no window that double-counts (smooth() conserves each window's sum; the published total equals the raw total outside rollbacks). Listing spread days in `skip_days` that have no snapshot (e.g. 2026-06-13..16) is harmless for the per-model series.
Fix: treat a day right after a gap as part of the same candidate (evaluate r on the interval total vs g x median, not on spread days) or extend the pair rule to "dip plus a neighbouring interval".

### Finding 5. dl30 vs the daily series

Sum of dl30 on day D / rolling 30-day sum of published hub_series ending D (`D_6_conserve.py`): median by month 2025-03..06 1.003-1.004 (June 0.993), then 2025-07 0.964, Aug 0.966, Sep-Nov 0.969-0.973, Dec 0.979, Jan 0.966, Feb 0.972, Mar 0.973, Apr-May 0.990, **Jun 2026 0.936, Jul 0.908**, Aug 0.961, Sep 0.956.
- The step to 0.965 happens at 2025-07-09, the end of the 36-day gap. It is not clip noise: Sum of negative deltas is only 0.15% of positives that month. Hub monthly sums are 0.6-1.1% BELOW (net positive delta + first-appearance downloads of new models), i.e. the daily series agrees with the all-time counters; it is the dl30 field that is lower than 30 days of all-time growth. I could not determine why (a change in what the Hub's 30-day window counts is my guess; unverified).
- Event days: 2025-05-20 0.75 (rollback hits dl30 too), 2026-06-13..17 0.71-0.76 (same, recovers to 0.98 on 06-19), 2025-08-18/19 0.90/0.87 and 2026-07-20/21 0.88 (stalls), 2025-11-24 0.84 (finding 3).
- Month-end dl30 x days/30 (the "est." method used before March 2025) vs the exact hub month: 1.004 (Mar), 1.004 (Apr), 1.002 (May 2025): no discontinuity at the switch. After July 2025 the same estimate would be 3-8% low (July 2026: 3.17B est vs 3.43B hub, 0.925), so the "agree within a few percent" statement in the article holds only for Mar-Jun 2025.
- The estimated period itself swings a lot: Σdl30 1.24B (2024-09-30) -> 2.36B (2024-11-01) -> 2.13B (12-09) -> 1.58B (12-30) -> 2.0B (2025-02-01): +90% then -26% in two months, with 50% jumps unrelated to the model count. Only "Jul 2024 (est.)" enters the article (1.67B, before the trough), so low severity, but the shaded months in the model charts carry these swings.
Severity medium: someone adding up dl30 across models gets 3-9% less than the chart. Suggest stating it in "How this was measured" (the daily series is derived from all-time counters; dl30 is the Hub's own window and is 3-9% lower in aggregate since Jul 2025).

### Finding 6. Leaderboard "this week"

`derived()` (build.py) reads the counters at `last`, `last-7`, `-14`, `-28` through `at_or_before(recent, ref, max_back=10)` on a series with skip days removed (except `last`). Simulating every possible `last` day from 2025-04-10 (434 dates, `D_11_week.py`):
- on 75 dates (17%) the "7-day" anchor is not D-7 (it is D-8..D-10), so "this week" covers 8-10 days (up to +43%) for every model;
- `last` itself is never excluded, so on a Wednesday half-stall (frozen share up to 0.8) the week ends on an unsettled snapshot: this-week sums are 5-25% below the smoothed hub 7-day sum on 20 dates (e.g. 2025-05-03..05 -11/-21/-25%, 2025-08-13 -9%, 2026-08-28 -16%, 2026-09-03 -12%); 97 dates (22%) differ by more than 5% in either direction.
The bias is common to all models so the ranking is mostly unaffected but "growth_7d" (week vs three-week average) and any hub-level "this week vs last week" shift with it. The hub chart is a TRAILING 7-day mean (api.ts `smooth`), so the grey low-day band marks the start of a 7-day depression, the first 6 points are averages over fewer days, and the last two days (never in low_days, windows left open) can show an unmarked dip; with half-stalls mostly on Wednesdays the right edge of the chart is wrong about 1 day in 5.
Fix: anchor on exact day offsets and, when an anchor is a skip day, rescale by the actual span (or divide by span days x 7); exclude `last` if it matches the stall signal and fall back to the previous day.

### Finding 7. Weekly seasonality

Ratio to the centred 7-day mean on clean days (`D_5_weekday.py`): Mon 0.85-0.89, Tue 1.00, Wed 1.06, Thu 1.05, Fri 1.04-1.05, Sat 1.00-1.02, Sun 0.87-0.88 (about 12% peak-to-trough, stable in 2025 and 2026). A day labelled Sun or Mon is the Sat/Sun activity (the snapshot is taken early in the next UTC day), so the chart weekend is shifted by a day against the calendar.
Weekday-adjusted ratio (r / weekday factor, same 0.7 cut): of the 24 low days, 5 are no longer below 0.7 (2026-01-18 0.704, 01-19 0.763, 02-01 0.797, 09-06 0.739, 09-07 0.797) and 3 are marginal (0.65-0.68: 2025-07-13/14, 2025-11-09). Low days by label weekday: Mon 3, Tue 2, Wed 4, Thu 1, Fri 1, Sat 3, Sun 5 of about 67 each: Sundays are over-represented but not overwhelmingly. I did not find any hole of 2x depth caused by the seasonality alone; the median rule is not a mass false-positive generator, only the 0.65-0.7 band is contaminated.
Fix: divide by a weekday factor before comparing with the 15-day median (or use a 14-day window so each weekday appears twice); easy and removes about 5 flags.

### Finding 8. pipeline_tag drift and deleted models

`hub_series` joins `models.parquet` (tracked models in the LATEST snapshot): ids absent from it (deleted or renamed) and untagged ids become "other", for all days.
- Deleted/renamed models: 217,684 ids, 0.241B of positive deltas = 0.54% overall; by quarter 1.28% (2025Q1), 0.95%, 1.03%, 0.58%, 0.26%, 0.24%, 0.29% (2026Q3). Their downloads are not lost, only moved to "other" (top: cognitivecomputations/dolphin-*, stabilityai/stable-diffusion-2*, ggml-org/models, michellejieli/emotion_text_classification, ds4sd/docling-models, 4-9M each).
- Tag changes, comparing tags in old hub-stats revisions (2025-03-03, 2025-09-15, 2026-03-01) with today's: downloads of models whose tag differs from today's are 2.85% (2025Q1), 2.23% (Q2), 0.95% (Q3), 2.03% (Q4), 1.09% (2026Q1), 0.66% (Q2). Largest effects: "other" as published is 20% above "other" with the tags of the time in 2025Q1 (257M vs 214M; 17% in Q2), text-classification -13% / -8%, feature-extraction -17.5% in 2025Q4 (52M moved to audio-classification, a few big models retagged), text-generation -1 to -4%. So per-task history before mid-2025 carries about 3% mass reassignment; the big tasks are within 4%, the small ones (text-classification, feature-extraction, audio-classification, image-to-video) can be off by 8-20%.
Severity low, but "text-ranking 10x", "feature extraction" style growth claims for small tags should say that tags are today's.

### Finding 9. Conservation (checks out)

Sum over all 493 snapshot intervals of positive per-model deltas 44.453B; negatives -1.268B; first-appearance all-time counters of new ids +4.787B; counters of ids that vanished -4.891B; sum(dl_all) 32.341B (2025-02-27) -> 75.421B (2026-10-04) = +43.080B; identity pos+neg+new-gone = 43.081B. Published hub_series 43.476B = positive deltas minus 0.977B, the rollback phantom (negatives of the two rollbacks are -0.44B and -0.57B). Net of the rollbacks the published total is 0.29B (0.7%) above the net counter growth: ordinary corrections. By month, hub_series vs per-model boundary diffs (`D_10_boundary.py`): +0.5 to +2.5% vs positive-only boundary diff, -0.6 to -1.1% vs boundary + new models; the two are the same data seen at two clipping levels. The article's 103.1M/day (Sep 2026, boundary method) vs hub_series Sep mean 101.3M (median 103.2M): -1.7%; Sep 2025 60.5M vs 59.9M; the "about 61M to about 103M" growth is +69% on both.
First-appearance downloads (models seen for the first time, so no delta): 0.81B excluding the 2025-11-24/25 artefact, about 1.9% of the total, mostly renames/moves (2025-03-07 150.9M in, 150.4M out; 2025-07-28 41.8M/41.6M). Real new-model first-day downloads are in there too (month-boundary method counts them, hub_series does not: 1.5-5% of a month in the boundary numbers). Not a bug, but the reason the two methods differ by 1-2%.
Gaps (23 intervals with gap > 1; 36 days in 2025-06/07, 17 in 2026-04, 19 in 2026-05/06): spread evenly, conserved, produce flat runs (e.g. 85M x 16 days in April 2026, 77M x 19 in June 2026, 92M x 5 in July) that a reviewer will see as suspiciously flat; they hide any real variation and distort the 15-day median and the weekly cycle around them.
Rollbacks: 2025-05-19..22 and 2026-06-12..18 are kept as skip_days; 2025-11-27..12-01 had 12% of models going down (-29M per day, 64k-140k models) and was not treated as a rollback (it does not appear in skip_days; negatives are clipped, loss -0.11B). That is probably the "release" branch (never came back), fine.

### Finding 10. Plateaus from spread windows

2026-06-12..19 reads 135M/day for 8 days against 77M (gap average before) and about 105M after; 2026-08-12..15 reads 172M/day (1.85x) against about 93M; 2026-07-08/09 162M. These are windows where the stall-plus-catch-up total exceeds a normal block (+460M, +300M, +120M). The June plateau is validated by dl30: its rolling sum equals 0.98 of the published rolling sum on 06-19. The August one: the days before (08-07..11) are a 3-day gap average at 71M and 63M and the days after are 93M, so the 9-day block averages 123M against a surrounding 90-105M; I cannot confirm that block from dl30 (ratio 0.96 at 08-31 vs 0.96 typical), so it is probably right but visibly odd. A reviewer reading the chart will see a 1.85x plateau. Suggest a short note or marking windows whose per-day value exceeds 1.5x median.

## 1. Details

### 1.1 Weekday and month tables
- Monthly mean per day (M, hub_series): 2025-03 72.3, 04 59.2, 05 58.6, 06 56.6, 07 59.5, 08 59.7, 09 59.9, 10 61.4, 11 61.0, 12 58.9, 2026-01 56.4, 02 72.4 (+28% in one month; the step happens 2026-02-03/04 after the hole 01-28..02-01), 03 77.0, 04 88.8, 05 91.3, 06 101.8, 07 110.7, 08 104.8, 09 101.3.
- Skip-day count per month: May 2025 7, Aug 2025 8, Jun 2026 8, Aug 2026 9; low-day count: Jan 2026 6. A month-on-month comparison with January 2026 as base (1.747B in 31 days vs 2.028B in 28 days, +28% per day) starts from a month that carries the unmade-up hole (about -175M, 10% of January), so about 3 points of that jump are the hole.
- Mean per day excluding low days would lift Sep 2026 by about 2% (101.3 -> about 103.3), i.e. exactly the gap to the boundary method's 103.1M, which does not know about days.

### 1.2 Low-day run list
See finding 1 and `D_7_lowruns.py` (printed table). Gap-spread days among low_days: 2025-12-04/05, 2026-01-31, 02-01, 04-02 (5 of 24: their values are interval averages, so they say nothing about a single day).

### 1.3 What was not checked
- Per-model hub-by-tag effects on the Spaces/datasets side (other audits).
- The final unsettled days (2026-10-03/04): not measurable until the catch-up arrives.
- Why dl30 fell from 1.00 to 0.965 of the daily sums in July 2025 and to 0.91 in July 2026 (needs the raw Hub definition).
