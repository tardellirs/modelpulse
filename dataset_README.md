---
license: apache-2.0
pretty_name: Model Pulse — daily history of Hugging Face models, datasets and Spaces
tags:
  - hub-stats
  - downloads
  - time-series
size_categories:
  - 100M<n<1B
configs:
  - config_name: series
    data_files: "series/*.parquet"
  - config_name: models
    data_files: "models.parquet"
  - config_name: family_series
    data_files: "family_series/*.parquet"
  - config_name: author_series
    data_files: "author_series/*.parquet"
  - config_name: hub_series
    data_files: "hub_series.parquet"
  - config_name: dataset_series
    data_files: "datasets/series/*.parquet"
  - config_name: datasets
    data_files: "datasets/datasets.parquet"
  - config_name: space_series
    data_files: "spaces/series/*.parquet"
  - config_name: spaces
    data_files: "spaces/spaces.parquet"
  - config_name: uses
    data_files: "uses.parquet"
---

# Model Pulse data

Daily download and like history for every actively used model and dataset on the Hugging Face Hub, and daily likes for every liked Space, from 2024-07-29 onward, updated every day. It powers [Model Pulse](https://huggingface.co/spaces/tardellirs/model-pulse), also at [modelpulse.ifsp.dev](https://modelpulse.ifsp.dev) with a page for every model, dataset and Space.

Built from the daily snapshots of [cfahlgren1/hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) (Apache 2.0), reading each historical revision of `models.parquet`, `datasets.parquet` and `spaces.parquet`.

## Files

| Path | Rows | What it holds |
|---|---|---|
| `series/YYYY-MM.parquet` | one per model per snapshot day | `id, day, dl30, dl_all, likes` |
| `models.parquet` | one per tracked model | latest metadata plus derived metrics (`dl_7d`, `growth_7d`, ranks, family totals) |
| `children.parquet` | one per base→derivative edge | direct derivatives with relation and downloads |
| `family_series/YYYY-MM.parquet` | one per base model per day | downloads summed over the model and all its derivatives |
| `author_series/YYYY-MM.parquet` | one per author per day | downloads summed over the author's models |
| `hub_series.parquet` | one per day per task | Hub-wide daily downloads by `pipeline_tag` |
| `leaderboards.json` | | weekly rankings shown on the site |
| `datasets/series/YYYY-MM.parquet` | one per dataset per snapshot day | `id, day, dl30, dl_all, likes` |
| `datasets/datasets.parquet` | one per tracked dataset | latest metadata (task, size, license) plus derived metrics and usage counts |
| `datasets/author_series/`, `datasets/hub_series.parquet`, `datasets/leaderboards.json` | | the same views as for models |
| `spaces/series/YYYY-MM.parquet` | one per Space per snapshot day | `id, day, likes, trending` |
| `spaces/spaces.parquet` | one per Space with at least one like | title, emoji, SDK, likes gained in 7 and 30 days, ranks |
| `spaces/new_by_sdk.parquet` | one per day per SDK | Spaces created each day, from the latest snapshot |
| `uses.parquet` | one per reference | `src_kind, src, dst_kind, dst, created, weight`: a Space using a model or dataset, or a model trained on a dataset, from today's cards |
| `repos_meta.json` | | days covered and skipped snapshots for datasets and Spaces |

## Notes

- `dl30` is the Hub's rolling 30-day download count. `dl_all` (all-time downloads) only exists from 2025-02-27, so exact daily downloads, computed as the difference of `dl_all` between snapshots, start on that date.
- Some days are missing in the source (Aug 2024, Jun 2025, Apr 2026, May–Jun 2026). Totals are unaffected; daily values across a gap are averages.
- A model or dataset is tracked once it has 10+ downloads in 30 days, 50+ all-time downloads, or at least one like. A Space is tracked once it has a like; the Hub doesn't publish visits for Spaces.
- On some days the Hub's download counters stand still and catch up a day or two later, mostly on Wednesdays. Dataset counters freeze all at once; model counters often freeze only in part (newer repos stop, older ones keep counting), so the model total may only dip to half. A day is treated as a stall when the total is under 0.3 of its 15-day median, when at least 25% of the models with 60K+ monthly downloads didn't move at all, or when a dip under 0.7 is made up by the next or previous day. `hub_series` spreads each episode evenly over its days (sums unchanged), and the snapshots inside it are listed in `skip_days` (`meta.json` for models, `repos_meta.json` for datasets) so per-repo series can do the same. `frozen` in the same files holds the recent daily share of frozen counters.
- Twice (May 2025, June 2026) the all-time counters went down for a large share of models and came back days later. Those snapshots are in `skip_days` too, and downloads across them are measured from the last good snapshot to the first one after the counters recovered, so the recovery isn't counted as new downloads. A drop that doesn't recover within 8 snapshots is treated as a lasting correction by the Hub, not set aside.
- A few snapshots hold only part of the repos (for models, 2025-11-24 with 289k of 1.13M). A snapshot with fewer than half the rows of the one before is left out: nothing is measured from or to it, the gap around it is spread like any missing day, and it is listed in `partial` and in `skip_days`.
- Days without a snapshot share the per-day average of the next one. A stall window that reaches into such a stretch takes all of it, up to the snapshot that closes it, so a catch-up booked across missing days is spread together with the stall it belongs to.
- After all this, a few days are still well under their local median and the days around them don't make up for it. `low_days` lists them: under 0.7 of the 15-day median (adjusted for the day of the week, since weekends run a little lower), in runs that the 3 days on each side don't make up by at least half. They keep their measured values; the Hub chart greys them out instead of smoothing over them. The last two days are judged once their neighbours are known.
- `uses.parquet` comes from the cards as they are today, dated by when each Space or model was created, not by when it started using what it lists.
- Download counts follow the Hub's [counting rules](https://huggingface.co/docs/hub/models-download-stats); the Hub occasionally books delayed downloads on a single day.
