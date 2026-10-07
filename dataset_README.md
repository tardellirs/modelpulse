---
license: apache-2.0
pretty_name: Model Pulse — daily history of Hugging Face models, datasets and Spaces
task_categories:
  - time-series-forecasting
tags:
  - hub-stats
  - huggingface-hub
  - downloads
  - time-series
  - analytics
  - open-source-ai
size_categories:
  - 1B<n<10B
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

<p align="center">
  <a href="https://modelpulse.ifsp.dev">
    <img src="https://huggingface.co/spaces/tardellirs/model-pulse/resolve/main/thumbnail-v3.png" alt="Model Pulse: download history for every model on the Hugging Face Hub" width="720">
  </a>
</p>

<p align="center">
  <a href="https://modelpulse.ifsp.dev"><b>Website</b></a> ·
  <a href="https://huggingface.co/spaces/tardellirs/model-pulse"><b>Space</b></a> ·
  <a href="#quick-start"><b>Quick start</b></a> ·
  <a href="#tables"><b>Tables</b></a> ·
  <a href="#methodology"><b>Methodology</b></a> ·
  <a href="#citation"><b>Citation</b></a>
</p>

# Model Pulse data

**A daily time series of the whole Hugging Face Hub.** Downloads and likes for every actively used model and dataset, and likes for every liked Space, one row per repo per day since **2024-07-29**, refreshed every day.

It is the data behind [Model Pulse](https://modelpulse.ifsp.dev), which has a page with the full history of every model, dataset and Space, along with model families (quantizations, fine-tunes, adapters and merges), author totals and weekly rankings.

| | |
|---|---|
| **Coverage** | 2024-07-29 → today, one snapshot per day |
| **Models** | 1.61M tracked · 25K families · 700M daily rows |
| **Datasets** | 1.06M tracked · 365M daily rows |
| **Spaces** | 104K tracked (at least one like) · 45M daily rows |
| **Total** | ~1.15B rows · ~2 GB of Parquet |
| **Update** | Daily, shortly after each new source snapshot |
| **License** | Apache 2.0 |

## Quick start

Every table is plain Parquet, so it can be queried in place without downloading the whole repo.

**DuckDB**: daily downloads of one model

```sql
SELECT day, dl30, dl_all - lag(dl_all) OVER (ORDER BY day) AS downloads
FROM 'hf://datasets/modelpulse/model-pulse-data/series/*.parquet'
WHERE id = 'Qwen/Qwen3-8B'
ORDER BY day;
```

**Polars**: this week's most downloaded models

```python
import polars as pl

top = (
    pl.read_parquet(
        "hf://datasets/modelpulse/model-pulse-data/models.parquet",
        columns=["id", "pipeline_tag", "dl_7d", "growth_7d", "rank_7d"],
    )
    .filter(pl.col("rank_7d").is_not_null())
    .sort("rank_7d")
    .head(20)
)
```

**🤗 Datasets**: load any table by its config name

```python
from datasets import load_dataset

hub = load_dataset("modelpulse/model-pulse-data", "hub_series", split="train")
models = load_dataset("modelpulse/model-pulse-data", "models", split="train")
```

> [!TIP]
> The daily series are split into monthly files (`series/2026-09.parquet`, …). To work with a recent window, read only the months you need.

## Tables

Each table below can be loaded as a config.

| Config | Path | One row per | Rows |
|---|---|---|---:|
| `series` | `series/YYYY-MM.parquet` | model × day | 700M |
| `models` | `models.parquet` | model | 1.61M |
| `family_series` | `family_series/YYYY-MM.parquet` | base model × day | 12M |
| `author_series` | `author_series/YYYY-MM.parquet` | author × day | 25M |
| `hub_series` | `hub_series.parquet` | day × task (`pipeline_tag`) | 32K |
| `dataset_series` | `datasets/series/YYYY-MM.parquet` | dataset × day | 365M |
| `datasets` | `datasets/datasets.parquet` | dataset | 1.06M |
| `space_series` | `spaces/series/YYYY-MM.parquet` | Space × day | 45M |
| `spaces` | `spaces/spaces.parquet` | Space with at least one like | 104K |
| `uses` | `uses.parquet` | reference (Space → model/dataset, model → dataset) | 464K |

<details>
<summary><b>Daily series</b>: <code>series</code>, <code>dataset_series</code>, <code>space_series</code>, <code>family_series</code>, <code>author_series</code>, <code>hub_series</code></summary>

| Column | Type | Description |
|---|---|---|
| `id` | string | Repo id (`org/name`), or the base model for `family_series` |
| `author` | string | Author or organization (`author_series` only) |
| `day` | date | Snapshot day |
| `dl30` | int | The Hub's rolling 30-day download count |
| `dl_all` | int | All-time downloads (available from 2025-02-27) |
| `likes` | int | Likes on that day |
| `trending` | float | Trending score (`space_series`) |
| `members` / `models` | int | Repos in the family / models by the author on that day |
| `pipeline_tag`, `dl` | string, int | Task and Hub-wide downloads that day (`hub_series`, from 2025-02-28) |

In `family_series` and `author_series`, downloads are summed over the base model and all its derivatives, or over all of the author's models.

</details>

<details>
<summary><b>Models</b>: <code>models.parquet</code></summary>

| Column | Description |
|---|---|
| `id`, `author`, `pipeline_tag`, `library_name`, `license`, `params`, `is_gguf` | Latest metadata from the Hub |
| `created_at`, `last_modified`, `first_seen` | Creation and update times, and the first day the model appears in the data |
| `dl30`, `dl_all`, `likes`, `trending` | Latest counters |
| `dl_7d`, `dl_prev7d`, `dl_base7d`, `growth_7d`, `likes_7d`, `peak_share`, `steps` | Weekly figures (see [Weekly figures](#weekly-figures)) |
| `rank_dl30`, `rank_task`, `rank_7d` | Overall rank by 30-day downloads, rank within the task, rank by 7-day downloads |
| `base_relation`, `base_ids` | How the model derives from its base model(s): `finetune`, `adapter`, `quantized` or `merge` |
| `fam_members`, `n_quantized`, `n_finetune`, `n_adapter`, `n_merge` | Size of the family built on this model |
| `fam_dl30`, `fam_all`, `fam_7d` (and `*_desc`) | Downloads summed over the model and its family (`*_desc`: derivatives only) |

</details>

<details>
<summary><b>Datasets</b>: <code>datasets/datasets.parquet</code></summary>

The same counters, weekly figures and ranks as for models, plus `gated`, `description`, `pipeline_tag`, `size`, `license` and `modality`, and the usage counts `used_by_models` and `used_by_spaces`.

</details>

<details>
<summary><b>Spaces</b>: <code>spaces/spaces.parquet</code></summary>

| Column | Description |
|---|---|
| `id`, `author`, `title`, `emoji`, `short_description`, `sdk` | Latest metadata |
| `created_at`, `last_modified`, `first_seen` | Creation and update times, first day in the data |
| `likes`, `likes_7d`, `likes_30d`, `trending` | Likes in total and gained over 7 and 30 days, trending score |
| `rank_likes`, `rank_7d` | Rank by total likes and by likes gained this week |
| `uses` | Number of models and datasets the Space references |

The Hub doesn't publish visit counts for Spaces, so Spaces are tracked by likes.

</details>

<details>
<summary><b>Usage graph</b>: <code>uses.parquet</code></summary>

| Column | Description |
|---|---|
| `src_kind`, `src` | The Space or model that references something |
| `dst_kind`, `dst` | The model or dataset it references |
| `created` | Creation date of the source repo |
| `weight` | Popularity of the source: its downloads for a model, its likes for a Space |

These rows come from the cards as they are today, dated by when each Space or model was created, not by when it started using what it lists.

</details>

### Other files

| Path | Contents |
|---|---|
| `children.parquet` | One row per base → derivative edge: `parent, id, base_relation, author, dl30, dl_all, dl_7d, likes` |
| `renames.parquet`, `datasets/renames.parquet` | Repos renamed on the Hub: `old, new, gone, came` (see [Renames](#renames)) |
| `spaces/new_by_sdk.parquet` | Spaces created each day by SDK, from the latest snapshot |
| `leaderboards.json`, `datasets/leaderboards.json`, `spaces/leaderboards.json` | The weekly rankings shown on the site |
| `meta.json` (models), `repos_meta.json` (datasets and Spaces) | Days covered, build and snapshot times, and the day lists used for quality control: `skip_days`, `low_days`, `short_days`, `partial`, `frozen` |

## Methodology

The data is rebuilt from the daily snapshots of [cfahlgren1/hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) by reading every historical revision of its `models.parquet`, `datasets.parquet` and `spaces.parquet`. The Hub's counters are noisy in a few known ways, and the rules below make the daily series reliable without changing any totals.

### Tracking

- A **model or dataset** is tracked once it has 10+ downloads in 30 days, 50+ all-time downloads, or at least one like.
- A **Space** is tracked once it has at least one like.
- Download counts follow the Hub's [download counting rules](https://huggingface.co/docs/hub/models-download-stats). The Hub occasionally books delayed downloads on a single day.

### Daily downloads

- `dl30` is the Hub's rolling 30-day count. `dl_all` (all-time downloads) only exists from **2025-02-27**, so exact daily downloads, computed as the difference of `dl_all` between snapshots, start on that date.
- When a repo's all-time counter hasn't moved in 31 days, `dl30` is set to 0, because the Hub sometimes keeps showing a stale 30-day count.

### Missing and partial snapshots

- Some days are missing from the source (Aug 2024, Jun 2025, Apr 2026, May–Jun 2026). Totals are unaffected: the days without a snapshot share the per-day average of the next snapshot.
- A few snapshots hold only part of the repos (for models, 2025-11-24 has 289K of 1.13M). A snapshot with fewer than half the rows of the one before is left out: nothing is measured from or to it, the gap around it is spread like any missing day, and it is listed in `partial` and in `skip_days`.

### Counter stalls

On some days the Hub's download counters stand still and catch up a day or two later, mostly on Wednesdays. Dataset counters freeze all at once. Model counters often freeze only in part (newer repos stop while older ones keep counting), so the model total may only drop by half.

A day is treated as a **stall** when any of these is true:

- the total is under 0.3 of its 15-day median;
- at least 25% of the models with 60K+ monthly downloads didn't move at all;
- a dip under 0.7 is made up by the next or the previous day. Here, a value spread over days without a snapshot counts as one measurement, with its days weighed in the sum.

`hub_series` spreads each stall evenly over its days, so sums don't change. The snapshots inside a stall are listed in `skip_days` so that per-repo series can be smoothed the same way, and `frozen` holds the recent daily share of frozen counters. A stall that reaches into a stretch without snapshots takes the whole stretch, up to the snapshot that closes it, so a catch-up booked across missing days is spread together with the stall it belongs to.

### Counter regressions

Twice (May 2025 and June 2026), the all-time counters went down for a large share of models and came back days later. Those snapshots are also in `skip_days`. Downloads across them are measured from the last good snapshot to the first one after the counters recovered, so the recovery isn't counted as new downloads. A drop that doesn't recover within 8 snapshots is treated as a lasting correction by the Hub and is not set aside.

### Low and short days

- **`low_days`** lists the few days that are still well below their local median after all the rules above, and that the days around them don't make up for. A day is low when it is under 0.7 of the 15-day median (adjusted for the day of the week and estimated from days with their own snapshot, since weekends run a little lower), in a run that the 3 days on each side don't make up by at least half. Days without a snapshot share one measurement with the snapshot that closes them, so they are judged together. For example, 2026-01-31 (no snapshot) and 2026-02-01 come out at 0.74 as one measurement, so they are not low. Low days keep their measured values, and the Hub chart greys them out instead of smoothing over them. The last two days are only judged once their neighbours are known.
- **`short_days`** lists the snapshots taken less than 18 hours after the previous one. This happened when hub-stats moved its collection time (2025-03-04 came 10.3 hours after 2025-03-03). The counters' daily update then lands in the next snapshot, so such a day is short, not low, and never counts as a low day. `snapshot_at` keeps the time of the latest snapshot.

### Weekly figures

- `dl_7d`, `likes_7d` and `growth_7d` are rates over the days that the reference snapshots actually span, so a skipped or missing snapshot never makes a week longer than 7 days.
- A repo with no reference snapshot has no weekly figure, unless it is new that week.
- The growth rankings leave out repos whose week came mostly from a single day: over 60%, or over 80% for repos created that month once they have three snapshots. `peak_share` holds that share.

### Renames

A repo counts as renamed when its old id disappears and a new id appears within 3 days, under the same name or the same owner, with the same all-time count (within 1%). On the site, old pages redirect to the new id, whose series and author and family totals include the old id's history.

## Source and license

- **Source:** [cfahlgren1/hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) (Apache 2.0), daily snapshots of the Hub API.
- **License:** Apache 2.0.
- Model Pulse is an independent project and is not affiliated with Hugging Face.

## Citation

```bibtex
@misc{stekel2026modelpulse,
  author       = {Stekel, Tardelli},
  title        = {Model Pulse: Daily History of Hugging Face Models, Datasets and Spaces},
  year         = {2026},
  publisher    = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/modelpulse/model-pulse-data}}
}
```

## Contact

Made by **Tardelli Stekel** ([@tardellirs](https://huggingface.co/tardellirs) · [stekel.ifsp.dev](https://stekel.ifsp.dev/)). Questions, corrections and ideas are welcome in the [Community tab](https://huggingface.co/datasets/modelpulse/model-pulse-data/discussions).
