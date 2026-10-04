# What 19 months of daily downloads say about the Hugging Face Hub

Every model page on the Hub shows one number: downloads in the last 30 days. It's useful, but it's a snapshot. It can't tell you whether a model is growing or fading, how it compares with its peers, or how much of its reach comes from the quantizations and fine-tunes built on top of it.

So I rebuilt the history. [Model Pulse](https://huggingface.co/spaces/tardellirs/model-pulse) reads every daily revision of [@cfahlgren1](https://huggingface.co/cfahlgren1)'s [hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) dataset, back to July 2024, and turns them into a day-by-day series for 1.6 million models. Since February 2025 those snapshots include all-time totals, which makes exact daily downloads possible: 19 months of them, for every model that anyone actually uses. For the months before that, the 30-day counts still give a good monthly estimate, so the charts go back to July 2024.

This post walks through what that data shows. Every number comes from the [open dataset](https://huggingface.co/datasets/modelpulse/model-pulse-data), and every model mentioned can be looked up on Model Pulse.

## The short version

- The Hub serves about **100 million model downloads a day**, up from about 61 million a year ago.
- **Rerankers grew about 10x** and vision-language models more than 6x in that year. BERT-style fill-mask models are the only big category that shrank.
- **Qwen became the default open LLM publisher.** Its own repos went from 9% of text and vision-language model downloads in March 2025 to 30% in September 2026, after peaking at 50% in April. Meta's went from 10% to 3%.
- **43% of all downloads go to derivatives**, up from 18%. Quantizations alone went from 9% to 28%.
- **Unsloth grew 6x and LM Studio's community org 25x**, making the quantizers some of the biggest publishers on the Hub.
- **The top of the Hub is losing its grip**: the ten most downloaded models took 34% of downloads in March 2025 and 22% now.
- **Big models are the fastest-growing slice.** Downloads of 100B+ models grew 14x and of 10–35B models 8x, against 2.6x for models under 10B.
- **Old models still carry the Hub**: 10 of the 15 most downloaded models are dated 2022 or earlier.
- **A launch spikes for two weeks and then plateaus.** 40% of successful launches had their best week after their third month.
- **Likes measure excitement, not use.** Image models collect 160 times more likes per download than rerankers.
- **Dataset downloads grew 2.5x in a year**, to about 8M a day, and they're far less concentrated than model downloads.
- **Robotics is now the second most downloaded dataset category**, after text generation, up from 23rd two years ago. One in seven new datasets is robot data.
- **Fine-tuners moved from IMDb and SQuAD to reasoning traces**, now cited by 12% of the people who list their training data.
- **Spaces are being created faster than people like them.** At the peak, Spaces were created more than four times faster than in late 2024, while likes per month fell by almost half.

## 1. The Hub serves about 100 million model downloads a day

![Weekly downloads across all public models, by task](01-hub.png)

In September 2026 public models were downloaded about 103M times on a typical day, against about 61M a year earlier. The growth wasn't spread evenly across tasks:

| Task | Sep 2025, per day | Sep 2026, per day | Change |
|---|---:|---:|---:|
| Text generation | 9.2M | 19.3M | 2.1x |
| Sentence similarity | 6.7M | 16.3M | 2.5x |
| Vision-language (image-text-to-text) | 1.7M | 10.9M | 6.6x |
| Feature extraction | 2.8M | 6.1M | 2.2x |
| Automatic speech recognition | 2.4M | 4.8M | 2.0x |
| Fill-mask | 5.6M | 5.1M | 0.9x |
| Text ranking (rerankers) | 0.4M | 3.9M | 10.2x |
| Everything else | 31.7M | 36.7M | 1.2x |

Two things stand out. Rerankers went from a niche to nearly 4M downloads a day, which is what you'd expect as retrieval pipelines add a reranking step. And fill-mask, the task behind the original BERT wave, is the only large category that shrank.

Days when the Hub's counters stood still, or briefly went backwards, are spread over the days around them, keeping totals exact (see "How this was measured").

## 2. Embeddings and retrieval quietly run the Hub

Generative models get the attention, but the most downloaded models on the Hub are small encoders. These were the top 15 in September 2026:

| Model | Created | Downloads in September 2026 |
|---|---|---:|
| sentence-transformers/all-MiniLM-L6-v2 | 2022 or earlier | 253.3M |
| cross-encoder/ms-marco-MiniLM-L6-v2 | 2022 or earlier | 89.6M |
| BAAI/bge-small-en-v1.5 | 2023 | 65.9M |
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 2022 or earlier | 50.9M |
| google/electra-base-discriminator | 2022 or earlier | 48.8M |
| google-bert/bert-base-uncased | 2022 or earlier | 43.1M |
| BAAI/bge-m3 | 2024 | 37.0M |
| Qwen/Qwen3-0.6B | 2025 | 30.3M |
| google-t5/t5-small | 2022 or earlier | 25.4M |
| amazon/chronos-2 | 2025 | 23.6M |
| Comfy-Org/MiniMax-H3 | 2026 | 23.3M |
| openai/clip-vit-base-patch32 | 2022 or earlier | 22.3M |
| timm/mobilenetv3_small_100.lamb_in1k | 2022 or earlier | 22.0M |
| sentence-transformers/all-mpnet-base-v2 | 2022 or earlier | 21.1M |
| FacebookAI/xlm-roberta-base | 2022 or earlier | 17.9M |

From April to September 2026 the `sentence-transformers` organization served 2.28B downloads, slightly more than Qwen's 2.16B. The `sentence-transformers` library went from 12% of all downloads to 24%, while `transformers` went from 67% to 50%:

| Library | Mar 2025 | Sep 2026 |
|---|---:|---:|
| transformers | 66.7% | 49.8% |
| sentence-transformers | 12.3% | 24.3% |
| no library tag | 3.5% | 7.7% |
| timm | 5.3% | 1.7% |
| diffusers | 2.7% | 1.6% |
| gguf | 0.0% | 1.6% |
| mlx | 0.0% | 0.6% |
| transformers.js | 0.2% | 0.5% |

## 3. Qwen became the default open LLM publisher

![Share of text and vision-language model downloads, by publisher](02-text-orgs.png)

Count every download of a text-generation or vision-language model on the Hub, including every quantization and fine-tune, and ask who published the repo. Most of these downloads go to thousands of small publishers, so a single organization with a tenth of them is a giant. In July 2024 Meta's `meta-llama` repos took about 11% and Qwen's 6%. By March 2025 they were tied at about 9% each. Then Qwen pulled away: 27% in September 2025, a peak of 50% in April 2026, and 30% in September 2026. Since April its share has slipped while Google's rose from 1.5% to 4.3% and quantized repos kept growing. Meta's repos took 3%. NVIDIA is the riser to watch, from almost nothing to 3.4%.

The most downloaded text and vision-language models in September 2026:

| Model | Downloads in September 2026 |
|---|---:|
| Qwen/Qwen3-0.6B | 30.3M |
| Qwen/Qwen3-VL-8B-Instruct | 16.5M |
| openai-community/gpt2 | 16.2M |
| google/gemma-4-26B-A4B-it | 13.3M |
| Qwen/Qwen3-8B | 11.8M |
| trl-internal-testing/tiny-Qwen2ForCausalLM-2.5 | 11.1M |
| google/gemma-4-31B-it | 10.1M |
| Qwen/Qwen3.5-9B | 9.7M |
| unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF | 9.6M |
| Qwen/Qwen2.5-7B-Instruct | 9.6M |

Two of these are worth a second look. GPT-2, released in 2019, is still the third most downloaded text model. And a tiny test model used in TRL's CI makes the top ten, which shows how much of the Hub's traffic comes from automated pipelines.

## 4. Nearly half of all downloads go to derivatives

![Share of monthly downloads going to derivatives](03-derivatives.png)

A derivative is a model whose card declares a base model: a quantization, a fine-tune, an adapter or a merge. In July 2024 derivatives took about 8% of all downloads on the Hub, and 18% in March 2025. In September 2026 they took 43%. Quantizations drove most of it, going from 9% to 28%, and GGUF files alone went from 5% to 11%, most of that in the last three months.

Take [Qwen3-8B](https://huggingface.co/spaces/tardellirs/model-pulse?model=Qwen/Qwen3-8B). 6,283 models build on it, directly or through other derivatives, and 37% of its family's monthly downloads go to those derivatives rather than to the original. If you only look at the original repo, you miss more than a third of its reach.

Derivatives also reach scale faster. Of the models created since March 2025, 946 have passed one million downloads. Here is how long it took, by type:

| Type | Models past 1M downloads | Median days to 1M |
|---|---:|---:|
| Quantized | 297 | 100 |
| Adapter | 14 | 115 |
| Fine-tuned | 117 | 127 |
| Merge | 6 | 191 |
| Original (no declared base) | 512 | 331 |

## 5. The quantizers became some of the Hub's biggest publishers

![Monthly downloads of repackaged models, March 2025 vs September 2026](04-quantizers.png)

| Publisher | Monthly downloads, Mar 2025 | Monthly downloads, Sep 2026 | Repos with downloads, Sep 2026 |
|---|---:|---:|---:|
| unsloth | 11.1M | 66.9M | 1,440 |
| mradermacher | 7.2M | 46.7M | 70,233 |
| lmstudio-community | 1.7M | 42.1M | 750 |
| bartowski | 10.4M | 16.0M | 2,333 |
| MaziyarPanahi | 47.7M | 10.0M | 2,790 |
| mlx-community | 2.2M | 9.4M | 5,436 |
| ggml-org | 0.2M | 6.5M | 193 |
| TheBloke | 17.1M | 2.8M | 3,655 |

Unsloth grew sixfold and now ranks among the top dozen publishers on the whole Hub. LM Studio's community org grew 25-fold. mradermacher runs at a different scale altogether: more than 70,000 repos got at least one download in September. TheBloke, who defined this category in 2023, is down to 2.8M a month as people move to newer models, and MaziyarPanahi went the other way too, from 47.7M to 10.0M.

## 6. The head of the Hub is losing its grip

![Share of monthly downloads going to the top 10, 100 and 1,000 models](05-concentration.png)

| | Jul 2024 (est.) | Mar 2025 | Sep 2026 |
|---|---:|---:|---:|
| Share of downloads, top 10 models | 46.7% | 33.7% | 22.0% |
| Share of downloads, top 100 models | 76.5% | 62.9% | 47.2% |
| Share of downloads, top 1,000 models | 94.6% | 91.3% | 78.6% |
| Share of downloads, top 1% of models | 98.4% | 98.1% | 96.3% |
| Models with at least one download | 406K | 752K | 1.52M |

Demand is spreading out: the top ten took almost half of all downloads in mid-2024 and take a fifth now. The tail is still enormous, though. Of the 1.6M models tracked in September 2026, 47% got fewer than 10 downloads in the month and 88% got fewer than 100. Only 425 passed a million.

## 7. Big models are the fastest-growing slice

![Monthly text-generation downloads by model size, indexed](06-model-size.png)

Weighted by downloads, the typical text-generation model went from 3.0B parameters in March 2025 to 5.6B in September 2026, after peaking at 6.7B in July. That average hides where the growth happened. Text-generation downloads more than tripled overall, so every size band grew, but not at the same pace:

| Parameters | Mar–May 2025, per month | Jul–Sep 2026, per month | Change |
|---|---:|---:|---:|
| Under 10B | 109M | 280M | 2.6x |
| 10B to 35B | 13M | 104M | 8.2x |
| 35B to 100B | 7.7M | 18M | 2.3x |
| 100B and up | 3.1M | 42M | 14x |

Models with 10B or more parameters went from 19% of text-generation downloads to 35%, and 100B+ alone from 2% to 9%. The 35B–100B band, home of the dense 70B models, grew more slowly than the Hub. The growth went to the bands on either side of it.

These are total parameters, and that matters. The 100B+ band is mostly mixture-of-experts models that use a fraction of their weights per token: gpt-oss-120b (about 5B active), DeepSeek R1, V3 and V4, GLM-5.2, MiniMax M2.7 and Nemotron 3 Super 120B-A12B. The 10–35B band is led by NVIDIA's NVFP4 build of Qwen3.6-35B-A3B, gpt-oss-20b and Qwen3-32B. People download much bigger checkpoints, but much of that rise is mixture-of-experts.

Small models haven't gone away: anything under 2B still takes about a third of text-generation downloads, some of it from CI pipelines that pull tiny test models all day.

## 8. Old models still carry a third of the Hub

The Hub dates every repo migrated from its early days to March 2022, so "2022 or earlier" covers BERT, GPT-2, T5 and the rest of that generation. Here is the share of each month's downloads by the year the model was created:

| Created | Jul 2024 (est.) | Mar 2025 | Sep 2026 |
|---|---:|---:|---:|
| 2022 or earlier | 75.7% | 56.0% | 33.5% |
| 2023 | 16.1% | 17.6% | 11.4% |
| 2024 | 8.2% | 22.9% | 15.1% |
| 2025 | | 3.5% | 17.9% |
| 2026 | | | 22.0% |

New models win share fast, since 2026 models already take more than a fifth of all downloads, but the old guard erodes slowly: three quarters of downloads in mid-2024 went to models from 2022 or earlier, and a third still do.

## 9. A launch spikes for two weeks, then plateaus

![Average weekly share of a model's first six months of downloads](07-launch-curve.png)

I took the 2,301 models launched between March 2025 and March 2026 that passed 100K downloads in their first six months, and looked at how those downloads were spread over the 26 weeks:

- On average the first two weeks take about 8% of the six months each. After that, downloads settle at around 3% a week and stay there; they don't fade.
- For the median model, the first month accounts for only 14% of the first six months.
- Only 10% of these models had their best week at launch. The median best week is week 8 after launch, and 40% peaked after their third month.

This is a set of models that succeeded, so it says nothing about the many launches that never take off. But for the ones that do, steady use matters more than the launch spike.

The fastest to a million downloads since March 2025:

| Model | Days to 1M downloads |
|---|---:|
| openai/gpt-oss-20b | 5 |
| Comfy-Org/z_image_turbo | 5 |
| ornith-ai/Ornith-1.5-9B-GGUF | 6 |
| JonathanColetti/Qwen3.8-27B-Uncensored-GGUF | 7 |
| huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF | 8 |
| lmstudio-community/Qwen3.8-27B-MLX-4bit | 8 |
| unsloth/Qwen3.8-27B-NVFP4 | 8 |
| Comfy-Org/Wan_2.2_ComfyUI_Repackaged | 9 |
| Qwen/Qwen3.6-35B-A3B | 10 |

A couple of niche repos also crossed a million in five days, most likely through automated pulls, and are left out of the table. Note how many community builds of Qwen3.8-27B made the list: when a popular model ships, the GGUF, MLX and abliterated variants race each other to the top.

## 10. Likes measure excitement, not use

![Likes per 100,000 monthly downloads, by task](08-likes.png)

Across models with at least 1,000 monthly downloads, likes and downloads are only moderately related (Spearman 0.42). What a model is for matters more than how much it's used. Image generation models collect 854 likes per 100K monthly downloads; rerankers collect 5.

Some of the busiest models have almost no likes:

| Model | Downloads, last 30 days | Likes |
|---|---:|---:|
| mudler/locate-anything.cpp-gguf | 9.1M | 19 |
| amazon/chronos-bolt-small | 6.9M | 49 |
| cross-encoder/ms-marco-MiniLM-L4-v2 | 6.1M | 31 |
| autogluon/chronos-2-small | 4.5M | 8 |

And some of the most loved are rarely downloaded anymore:

| Model | Likes | Downloads, last 30 days |
|---|---:|---:|
| stabilityai/stable-diffusion-3-medium | 5,058 | 2,721 |
| WarriorMama777/OrangeMixs | 3,958 | 1,584 |
| prompthero/openjourney | 3,262 | 3,644 |
| zai-org/chatglm-6b | 2,915 | 2,881 |

If you rank models by likes, you're ranking them by how exciting they were. To see what people actually run, look at downloads over time.

## 11. Datasets: a smaller market, growing faster and less concentrated

Datasets are a smaller business than models. In September 2026 they were downloaded 253M times, about 8M a day, roughly one dataset download for every twelve model downloads. They're growing faster, though: 2.5x since September 2025, against 1.7x for models. The number of datasets downloaded at least once in a month doubled, from 510K to 1.05M.

Dataset downloads are also much less concentrated. The ten most downloaded datasets take 7.3% of all dataset downloads, against 22% for models, and the top 1,000 take 49%, against 79%. Both markets are spreading out, but datasets started flatter.

Some of the most downloaded datasets in September 2026:

| Dataset | Downloads in Sep 2026 | What it is |
|---|---:|---|
| m-a-p/FineFineWeb | 4.5M | Web text for pretraining |
| huggingface/documentation-images | 2.2M | Images used in the docs and tests |
| Salesforce/wikitext | 2.0M | Evaluation (perplexity) |
| nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim | 1.3M | Robot simulation data |
| openai/gsm8k | 1.2M | Math benchmark |
| allenai/c4 | 1.2M | Web text for pretraining |
| Lichess/standard-chess-games | 0.8M | Chess games |
| nyu-mll/glue | 0.8M | Classic NLP benchmark |
| allenai/ai2_arc | 0.7M | Reasoning benchmark |
| cais/mmlu | 0.7M | Knowledge benchmark |

Benchmarks are a large part of the head: evaluation harnesses download GSM8K, ARC and MMLU every time they run. And 28% of September's dataset downloads went to repos with no task, modality or size in their metadata at all. Many of those look like file storage (caches, asset bundles, model inputs) more than datasets in the ML sense.

## 12. Robotics is now the second most downloaded dataset category

![Rank of dataset task categories by monthly downloads](13-robotics-rank.png)

Among datasets that declare a task category, about a third of all dataset downloads, robotics went from 23rd in September 2024 to 2nd in September 2026, behind only text generation. It got 13.7M downloads that month, ahead of text classification (10.5M) and question answering (8.3M), up 16x from 0.9M in March 2025 and 5% of all dataset downloads. No other large category grew nearly as fast; the few that grew faster, like image-to-3d, are a tenth of its size.

![Robotics datasets created per month](09-robotics.png)

The number of datasets grew even faster. In September 2026, 6,570 new datasets were tagged robotics, 14% of all new datasets; two years earlier it was 136 a month. 46 authors created a robotics dataset in the third quarter of 2024, and 2,823 in the third quarter of 2026.

Most are LeRobot recordings. In a sample of 30 created in September, 26 carry the LeRobot tag, and most hold camera video plus joint positions from a few dozen demonstrations of a task, often pick-and-place on a low-cost SO-101 arm. They are small and personal: the median robotics dataset gets 31 downloads a month, and LeRobot tends to create one dataset per recording session, so the count overstates the activity a little. The downloads come mostly from large shared collections: NVIDIA's GR00T simulation data, the community's LeRobot conversions of Open X-Embodiment (Language Table, DROID, Kuka, Bridge), and new teleoperation sets.

## 13. Fine-tuners swapped IMDb and SQuAD for reasoning traces

![Share of model authors citing each kind of training data, by year](10-training-data.png)

Model cards can list the datasets a model was trained on, and between 10% and 20% of new models do. Counted by model, the ranking is dominated by accounts that publish thousands of near-identical models: one dataset is listed by 7,023 models, 7,020 of them from a single account. So the chart counts authors instead: the share of people who list a given kind of dataset, by the year their model was created.

In 2022, 36% of them cited a classic NLP set: IMDb, SQuAD, GLUE, CoNLL-2003, emotion. In 2026 it's 2.4%. Speech data went from 14% to 3.5%. Chat instruction sets (Alpaca, Dolly, UltraChat, OpenHermes, Orca) peaked at 10.5% in 2024 and have halved since.

Reasoning traces replaced them. Datasets of step-by-step solutions went from almost nothing to 12% of authors in 2026, the most cited kind. More and more of them are distilled from closed models: datasets with Opus, Claude, GPT-4 or Gemini in the name were cited by 4.6% of authors in 2026, up from 2.0% in 2025. Three of the eight most cited datasets this year are reasoning traces sampled from Claude Opus or Qwen3.5.

## 14. Spaces: more apps than ever, less attention each

![New Spaces per month, by SDK](11-spaces-sdk.png)

The Hub doesn't publish Space visits, but it does publish when each Space was created, its SDK and its likes. Creation took off in 2025. About 15,000 Spaces a month were created in 2024. In October 2025 the figure was 122,000, of which 86,000 were static sites, consistent with AI website builders that publish straight to a static Space. In 2026 Docker took over, with 45,000 new Docker Spaces in April alone. Then creation fell sharply from July 2026, to about 29,000 a month, with Docker down to about 2,000. This data doesn't say why. These counts include only Spaces that still exist.

![Spaces created and likes given per month, indexed](12-spaces-likes.png)

Likes didn't follow. Across all Spaces, people gave about 35,000 likes a month in late 2024 and about 20,000 a month in 2026. Attention is very concentrated:

- 104K Spaces have at least one like, and 65% of them have exactly one.
- The top 1% hold 59% of all 1.12M likes, and 137 Spaces have more than 1,000.
- The Spaces that gained the most likes in the last 30 days are mostly image and video generation and editing (Qwen-Image 2.1, Qwen-Image-Edit LoRAs, Wan 2.2), music generation and browser demos. Model downloads are mostly text. The likes on Spaces mostly go to images.

The model listed by the most Spaces isn't a frontier model. It's Xenova/detr-resnet-50, the object-detection model from the Transformers.js tutorial, which 2,759 Spaces list in their card while it gets about 16K downloads a month. Only about 3% of liked Spaces list a model or dataset in their card, so "used by" counts on Model Pulse are a lower bound.

## How this was measured

**Source.** [cfahlgren1/hub-stats](https://huggingface.co/datasets/cfahlgren1/hub-stats) publishes a fresh `models.parquet` with metadata for every public model on the Hub, usually daily. I read 681 of its historical revisions, from 2024-07-29 to 2026-10-02, keeping each model's 30-day downloads, all-time downloads and likes for each day. The latest snapshot adds the metadata: task, library, size, license and declared base models.

**Daily downloads.** The `downloadsAllTime` field exists from 2025-02-27. Daily downloads are the difference of that total between consecutive snapshots. Before that date only the rolling 30-day count exists, so Model Pulse shows that instead. Monthly figures in this post are the difference of each model's total between the first days of consecutive months, interpolated between the nearest snapshots when a boundary falls in a gap. Before March 2025 they are estimated from the 30-day count at the end of each month, scaled to the month's length; where both exist, the two agree within a few percent, and shares within about a point. Those months are shaded in the charts. The size chart starts in March 2025, because split into small size bands the estimates get noisy.

**Which models.** A model is tracked once it has 10 or more downloads in 30 days, 50 or more all-time downloads, or a like. That's 1.6M of the Hub's 3.1M models, and nearly all of its downloads.

**Datasets and Spaces.** The same snapshots include `datasets.parquet` (from 2024-07-29, all-time totals from 2025-02-27) and `spaces.parquet`. Datasets follow the same rules as models. Spaces have no downloads or visits in the data, so they're tracked by likes, for every Space with at least one. Training data and "used by" links come from the `datasets:` and `models:` lists in today's model and Space cards, dated by when the model or Space was created.

**Families.** A family is a base model plus every model that declares it as a base, directly or through other derivatives, following `base_model` up to six levels.

**Caveats.**
- Downloads follow the Hub's own [counting rules](https://huggingface.co/docs/hub/models-download-stats), so they include CI jobs, benchmarks and other automated pulls. That's why tiny test models rank surprisingly high.
- The source has gaps: two weeks in August 2024, most of June 2025, and parts of April to June 2026. Totals are unaffected, but daily values across a gap are averages, and monthly figures across one are interpolated.
- On some days the Hub's counters stand still and catch up a day or two later, mostly on Wednesdays and often only for newer repos while older ones keep counting. Twice, in May 2025 and June 2026, they went backwards for a large share of models and came back days later. The Hub-wide figures spread each such episode evenly over its days, which keeps totals exact, and measure across the rollbacks so a recovery isn't counted as new downloads.
- Publisher shares count downloads of an organization's own repos. A Qwen model quantized by Unsloth counts for Unsloth.
- "Created" dates come from the Hub, which dates repos migrated from its early days to March 2022.

## Explore it yourself

Every number above can be checked on [Model Pulse](https://huggingface.co/spaces/tardellirs/model-pulse):

- Open any model's daily and weekly history, with milestones such as the day it crossed a million downloads.
- Compare up to five models on one chart.
- See a model's family: how many quantizations, fine-tunes, adapters and merges build on it, and how many downloads they add up to.
- Browse the weekly rankings: most downloaded, fastest growing, new this month, most liked, biggest families and top organizations.
- Model authors can add a live badge to their model card.

The full dataset is open at [modelpulse/model-pulse-data](https://huggingface.co/datasets/modelpulse/model-pulse-data) and updated every day, so you can run your own analyses.

What would you want to know about your own models? I'd love to hear it in the comments.

*Made by [Tardelli Stekel](https://huggingface.co/tardellirs) ([stekel.ifsp.dev](https://stekel.ifsp.dev/)).*
