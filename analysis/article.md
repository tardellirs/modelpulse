# What 19 months of daily downloads say about the Hugging Face Hub

The Hub tells you how many times a model was downloaded in the last 30 days. It doesn't tell you how it got there, or how that compares with the rest of the Hub. So I rebuilt the history.

[Model Pulse](https://huggingface.co/spaces/modelpulse/model-pulse) reads every daily revision of [@cfahlgren1](https://huggingface.co/cfahlgren1)'s [hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) dataset, back to July 2024, and turns them into a day-by-day series for 1.6 million models. Since February 2025 the snapshots include all-time totals, which makes exact daily downloads possible. Everything below comes from that data, which is [open](https://huggingface.co/datasets/modelpulse/model-pulse-data).

Here is what stood out.

## 1. The Hub serves about 100 million model downloads a day

![Daily downloads across all public models, by task](01-hub.png)

In September 2026 public models were downloaded about 100M times a day, up from about 62M a year earlier. Monthly totals crossed 3 billion in the summer of 2026 and have stayed there.

Vision-language models grew fastest: about 1.6M downloads a day a year ago, 10.7M now.

## 2. Qwen gets half of all LLM downloads

![Share of text and vision-language model downloads, by publisher](02-text-orgs.png)

Count every download of a text-generation or vision-language model on the Hub, including all the quantizations and fine-tunes, and ask who published the repo. In March 2025 Meta's `meta-llama` repos and Qwen's were roughly tied, at about a quarter each. By September 2026 Qwen's own repos took 54%, and Meta's took 5%.

The crossover happened in the spring of 2025, and the gap kept widening. In September 2026 the most downloaded text model on the Hub was [Qwen3-0.6B](https://huggingface.co/spaces/modelpulse/model-pulse?model=Qwen/Qwen3-0.6B), with 30.6M downloads in the month. NVIDIA is the riser to watch: from under 1% to 6%.

## 3. Nearly half of all downloads go to derivatives

![Share of monthly downloads going to derivatives](03-derivatives.png)

A derivative is a model whose card declares a base model: a quantization, a fine-tune, an adapter or a merge. In March 2025 derivatives took 18% of all downloads on the Hub. In September 2026 they took 43%.

Quantizations drove most of it, going from 9% to 28%. GGUF files alone went from 5% to 11%, most of that jump in the last three months.

Take [Qwen3-8B](https://huggingface.co/spaces/modelpulse/model-pulse?model=Qwen/Qwen3-8B): 6,283 models build on it, and 37% of its family's monthly downloads go to those derivatives rather than to the original. Derivatives also reach scale faster. Among the 946 models launched since March 2025 that passed one million downloads, quantizations took a median of 100 days to get there, against 330 for originals.

## 4. The quantizers became some of the Hub's biggest publishers

![Monthly downloads of repackaged models, March 2025 vs September 2026](04-quantizers.png)

Unsloth went from 11M to 68M downloads a month. LM Studio's community org grew 24-fold, to 42M. mradermacher now maintains more than 70,000 repos and serves 47M downloads a month. TheBloke, who defined this category in 2023, is down to 2.8M as people move to newer models.

## 5. The head of the Hub is losing its grip

![Share of monthly downloads going to the top 10, 100 and 1,000 models](05-concentration.png)

In March 2025 the ten most downloaded models took 34% of all downloads; in September 2026 they took 22%. The top 100 fell from 64% to 47%. Demand is spreading out.

The tail is still enormous, though. Of the 1.59M models tracked in September 2026, 88% got fewer than 100 downloads in the month, and only 434 passed a million.

## 6. People download bigger models

![Share of text-generation downloads by model size](06-model-size.png)

Weighted by downloads, the typical text-generation model grew from 3.0B to 5.7B parameters in eighteen months. Models with 10B or more parameters went from 19% of text-generation downloads to 35%. Small models haven't gone away: anything under 2B still takes about a third, some of it from CI pipelines that pull tiny test models all day.

## 7. Embeddings quietly run the Hub

The `sentence-transformers` library went from 13% of all downloads to 27%. From April to September 2026 the `sentence-transformers` organization served 2.27B downloads, slightly more than Qwen's 2.16B. The most downloaded model on the whole Hub this week is [all-MiniLM-L6-v2](https://huggingface.co/spaces/modelpulse/model-pulse?model=sentence-transformers/all-MiniLM-L6-v2), with about 56M downloads.

Old models still matter too. Repos created in 2022 or earlier, which is when the Hub dates every migrated legacy repo, still take a third of all downloads. That is down from 56% in March 2025, and models created in 2026 already take 22%.

## 8. A launch spikes for two weeks, then plateaus

![Average weekly share of a model's first six months of downloads](07-launch-curve.png)

I took the 2,303 models launched between March 2025 and March 2026 that passed 100K downloads, and looked at how their first six months of downloads were spread out. On average the first two weeks take about 8% each, then downloads settle around 3% a week and stay there. They don't fade.

For the median model, the first month accounts for only 14% of the first six months. 43% of these models had their best week after their third month. Hype gets a model noticed; steady use carries it.

The fastest to a million downloads since March 2025 took 5 days: OpenAI's [gpt-oss-20b](https://huggingface.co/spaces/modelpulse/model-pulse?model=openai/gpt-oss-20b) and Comfy-Org's Z-Image Turbo repackage. A couple of niche repos matched them, most likely through automated pulls. Qwen3.6-35B-A3B followed in 10 days, and DeepSeek-V4-Flash and Lightricks' LTX-2 in 11. Several community GGUF and MLX builds of Qwen3.8-27B made it in 7 to 9 days.

## 9. Likes measure excitement, not use

![Likes per 100,000 monthly downloads, by task](08-likes.png)

Across models with at least 1,000 monthly downloads, likes and downloads are only moderately related (Spearman 0.42). The gap depends on what the model is for. Image generation models collect 854 likes per 100K downloads; rerankers collect 5.

Some of the busiest models have almost no likes: [amazon/chronos-bolt-small](https://huggingface.co/spaces/modelpulse/model-pulse?model=amazon/chronos-bolt-small) gets 6.9M downloads a month and 49 likes. Others are loved and rarely used: Stable Diffusion 3 Medium has more than 5,000 likes and about 2,700 downloads a month.

## How this was measured

- Downloads follow the Hub's own [counting rules](https://huggingface.co/docs/hub/models-download-stats), so they include CI jobs and other automated pulls. A few tiny test models rank surprisingly high for that reason.
- Monthly figures are the difference between month-end all-time totals. The source has gaps (August 2024, June 2025, and parts of April to June 2026). June 2025 is left out of the monthly charts because its snapshot is incomplete.
- The Hub sometimes books delayed downloads on a single day, which shows up as short spikes; the charts use 28-day averages where that matters.
- Publisher shares count downloads of an organization's own repos only; a Qwen model quantized by Unsloth counts for Unsloth.
- A model is tracked once it has 10 or more downloads in 30 days, 50 or more all-time downloads, or a like.

## Explore it yourself

Every number above can be checked on [Model Pulse](https://huggingface.co/spaces/modelpulse/model-pulse). Look up any model's daily history, compare up to five models, see how much of a model's reach comes from its derivatives, and browse the weekly rankings. Model authors can add a live badge to their model card. The full dataset is at [modelpulse/model-pulse-data](https://huggingface.co/datasets/modelpulse/model-pulse-data) and is updated every day.

What would you want to know about your own models? I'd love to hear it.
