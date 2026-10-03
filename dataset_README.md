---
license: apache-2.0
pretty_name: Model Pulse — daily download history of Hugging Face models
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
---

# Model Pulse data

Daily download and like history for every actively used model on the Hugging Face Hub, from 2024-07-29 onward, updated every day. It powers [Model Pulse](https://huggingface.co/spaces/modelpulse/model-pulse).

Built from the daily snapshots of [cfahlgren1/hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) (Apache 2.0), reading each historical revision of `models.parquet`.

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

## Notes

- `dl30` is the Hub's rolling 30-day download count. `dl_all` (all-time downloads) only exists from 2025-02-27, so exact daily downloads, computed as the difference of `dl_all` between snapshots, start on that date.
- Some days are missing in the source (Aug 2024, Jun 2025, Apr 2026, May–Jun 2026). Totals are unaffected; daily values across a gap are averages.
- A model is tracked once it has 10+ downloads in 30 days, 50+ all-time downloads, or at least one like.
- Download counts follow the Hub's [counting rules](https://huggingface.co/docs/hub/models-download-stats); the Hub occasionally books delayed downloads on a single day.
