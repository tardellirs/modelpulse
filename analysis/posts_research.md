# Hugging Face Posts: what performs, and drafts for the Model Pulse update

Research date: 2026-10-04. Read-only: public API and public pages only, nothing posted, commented or reacted. (My browser session happened to be signed in as tardellirs; I only loaded one public post page to inspect how text renders and took no action.)

## 1. Data and method

- Source: `https://huggingface.co/api/posts?limit=10&skip=N&sort=recent|trending`. The API caps `limit` at 10 and ignores author filters; `skip` paginates. `numTotalItems` says 8,339, but the listing is only reachable to roughly the 7,260 newest posts, with gaps (e.g. nothing for Jun-Aug 2024). There is no single-post endpoint (`/api/posts/{user}/{slug}` is 404); the post page embeds the comments as JSON.
- Fields per post: content (parsed into text / new_line / link / mention / resource / code), attachments (image, video), reactions with users, `numComments`, `commentators`, `publishedAt`, `totalUniqueImpressions` (useful and rarely used: it shows distribution, not just reactions), author with `followerCount` and `isPro`.
- Samples:
  - Core: the 1,503 newest posts (2026-04-15 to 2026-10-04); 1,431 are English and at least 7 days old (so reactions have settled). Follower count known for 1,388.
  - Robustness: 4,325 English posts from 2025-04 to 2026-09 (all reachable posts), with engagement adjusted for month (the median reaction count fell from about 6 to about 2-4 as feed volume grew) and for log followers.
- Metrics: reactions (sum over emoji, includes the author's own if they reacted), comments (including replies), impressions. "Top decile" = top 10% by reactions (>= 19 reactions in the core sample; top 10% of its month in the 12-month sample). "Adj." = mean residual of log(1+reactions) after removing author followers (and month); positive means better than an account of that size would typically get, and a difference of 0.1 is about +10%.
- `trending` is not a useful separate sample: the first 300 trending posts are almost the same posts as the recent set, ordered by recent engagement.

### Base rates
Median post: 3 reactions, 0 comments, about 325 impressions. 75th percentile 8 reactions, 90th 19, 95th about 31. Comments: median 0, 90th percentile 7. Most posts get 3 reactions or fewer, so 8-10 reactions is already a good result.

## 2. What the data says

### 2.1 Two things dominate: an image, and early engagement that unlocks distribution

Impressions are bimodal. Posts either sit around 100-300 impressions (author's followers and not much more) or jump to 2,000-6,000. The jump tracks early engagement:

| reactions + comments | share of posts with >= 1,000 impressions | median impressions |
|---|---|---|
| 0-1 | about 1% | about 130 |
| 2 | 7% | 157 |
| 3 | 18% | 172 |
| 4-5 | 44% | 687 |
| 6-8 | 65% | 1,840 |
| 9-12 | 82% | 2,717 |
| 20+ | 92% | 3,874 |

Roughly 4-6 reactions is where a post tips into wider feed distribution. Accounts with 3-13 followers (e.g. `pollix`) got 3,500-6,400 impressions once they passed about 6 reactions. Caveat: this is correlational and circular (more impressions also create more reactions), but it matches what the trending list looks like. Practical reading: the first hours matter, and what you want is a post that makes people react quickly.

### 2.2 Images (strongest, most robust feature)

12-month sample, adjusted for month and followers:

| images | n | median reactions | share in top decile | adj. |
|---|---|---|---|---|
| 0 | 2,615 | 3 | 5.8% | -0.12 |
| 1 | 1,187 | 5 | 13.4% | +0.07 |
| 2 | 198 | 8 | 27.3% | +0.41 |
| 3-4 | 170 | 8 | 24.7% | +0.45 |
| 5+ | 155 | 11 | 34.8% | +0.50 |

- Holds inside every follower tier (core sample): accounts with up to 100 followers got a median of 3 vs 2 reactions (mean 7.8 vs 3.4); 101-300 followers: median 7 vs 3. Holds when removing the four most prolific high-performing accounts (top-decile share 8.2% with no image, 16.1% with one, 23.5% with 2+). Within the same author (42 authors who posted both ways) the median goes from 3 to 6.5 reactions, and 79% of them did better with an image.
- Median impressions: 1,453 with one image, 242 with none.
- 67% of top-decile posts have an image, vs 36% of the rest. Top-decile median is exactly 1 image.
- Diminishing returns after 2 images. 2-4 images is the sweet spot; 5+ is slightly better but rare and mostly large accounts.
- Type: static images and GIFs do equally well (about 18% in top decile each); video adds a little (+0.09 adj.). I did not classify chart vs screenshot automatically. Looking at the 10 best small-account tool/analysis posts by eye: 5 were screenshots of a Space UI (leaderboards with a chart or ranking table visible), 2 were animated GIFs of a tool being used, the rest were banners/diagrams. Nothing in the data shows charts beating screenshots or the reverse; both work if the image already carries the number or the result.

### 2.3 Length and structure

- Top decile median is 112 words (rest: 82); first line is about 77 characters in both groups. So length itself is not the lever; the first line length does not matter (first line over 300 characters is mildly worse).
- 12-month sample, adj.: under 50 words -0.16, 50-100 +0.02, 101-150 +0.10, 151-250 +0.11, 250+ +0.12 (top-decile share rises to 18.7% for 250+, but that is mostly established accounts).
- For small accounts (up to 300 followers, n = 3,034), the best band is 60-200 words (adj. +0.09 and +0.14); over 200 words falls back to -0.14 (top-decile share 4.4%) and under 60 is -0.10. For small accounts linking a Space (n = 434), 150-250 words did best (10.3% in top decile, median 5, adj. +0.38).
- Paragraphs: posts with 1-3 paragraphs do worst (adj. -0.17 / -0.12); 4-12 paragraphs do better (+0.05 to +0.19). Short blocks with blank lines beat one dense block.
- Bullets: no effect either way (none 10.5% in top decile, 1-3 bullets 13.1%, 4+ 10.2%). Use them for scanning, not for reach.
- Markdown does not render. I checked a live post that contains `**bold**`: the page shows the asterisks literally and the DOM has no `<strong>`. The API's own parser also leaves `**` inside plain text. Posts using `**` are slightly worse (6.2% in top decile vs 10.8%). Newlines and blank lines are preserved; `- ` bullets show as typed.
- Link handling: Hugging Face URLs (models, datasets, Spaces, papers, collections, orgs) become link cards ("resource" type, 1,193 in the core sample); other URLs are plain links; `@user` becomes a mention; `inline_code` and code fences are parsed, hashtags are just text.

### 2.4 Hook, numbers, voice

- Numbers help: posts with 9-15 numbers in the text are 15.8% top decile, 16+ numbers 19.5%, vs 6.4% for none. A percentage or "Nx" in the text: 18.4% vs 9.4% in top decile (adj. +0.21 vs -0.03). A number in the first line: mild positive (13.2% vs 8.6%, adj. +0.04 vs -0.03).
- Hook types (regex-classified on the first line, 12-month sample, adj.): "Introducing / Excited to / New: / Meet" +0.33 (n = 229, median 7); "I built / we released / I shipped" +0.25 (n = 83, median 5); "X is out" +0.04; number-led +0.03; question -0.02; abstract claim -0.02; other -0.05. The announcement effect is partly the kind of account that announces products; read it as "say plainly what exists", not "use the word Introducing".
- Questions: a question as the first line gives nothing (10.9% vs 10.6% in top decile). A post that ends with a question is slightly worse on reactions (9.6% vs 10.7%) but gets about 25% more comments (1.95 vs 1.57 per post). For us comments were the useful outcome last time (see 2.7), so end with a specific request, not a generic question.
- Voice: "I" is neutral (-0.01 vs +0.01); "we" is better (+0.19 vs -0.10), but that is mostly organisation accounts. First person is fine.
- Ending the post with a bare URL line is slightly worse (8.0% vs 11.2% in top decile): put links in the body with context, or follow them with one closing line.
- Emojis: more is mildly better (0: 8.5% top decile; 6+: 14.7%), and an emoji starting the first line is +0.10. Tone-wise we want none or one. Hashtags: no effect on top-decile share (9.8% vs 10.7%).

### 2.5 Links, mentions, resource cards

- HF resource cards: 0 cards 9.4% top decile, 1 card 10.5%, 2 cards 14.7%, 3+ 15.6%. A Space card is the strongest (+0.17 adj., 15.0% vs 9.8%); a model card is mildly positive (+0.07); a dataset card is negative (-0.07, 5.8% vs 11.2%); a paper card is mildly positive.
- External links: 0 links 8.4% top decile, 1 link 10.9%, 2+ links 16.6%.
- @mentions: posts with one or more mentions get 2x the comments (2.9 vs 1.5) and a higher top-decile share (12.9% vs 10.5% in the 12-month sample; 22.5% vs 10.2% in the core sample, adj. +0.14 to +0.25). Mentioning the source of the data (we mention @cfahlgren1) fits this pattern, and the mentioned person is notified. I cannot separate causation from "posts that mention someone are written by well-connected people".

### 2.6 Timing (weak; do not over-trust)

- Day of week (12-month, adj.): Mon -0.04, Tue +0.01, Wed -0.04, Thu -0.02, Fri +0.03, Sat +0.02, Sun +0.07. Weekend posts: 12.3% top decile vs 10.2%, and 50% more comments (2.2 vs 1.4 per post). Effect is about +5%, and weekend volume is lower.
- Hour (UTC, adj.): best 01-04 UTC (+0.10 to +0.19, standard error about 0.08), worst 08-10 UTC and 13 UTC (-0.09 to -0.12, standard error about 0.05). 20-23 UTC was the worst block in the smaller core sample but neutral in the 12-month one, so treat it as noise. Posting volume peaks at 14-17 UTC (about 7% of posts per hour) and bottoms out at 01-05 UTC (about 2-3%), which is likely why the quiet hours do slightly better per post.
- Conclusion: timing moves results by roughly +/-10%, an image moves them by far more. Pick the time you can be online to answer comments in the first 2-3 hours, given 2.1.

### 2.7 Topic

Crude keyword classification (core sample); read directionally:

| topic | n | median reactions | top-decile share | adj. |
|---|---|---|---|---|
| tool / Space / app launch | 254 | 3 | 12.2% | +0.05 (85% have an image) |
| model release | 611 | 3 | 11.8% | +0.08 |
| dataset announcement | 99 | 2 | 6.1% | -0.10 |
| paper | 48 | 3 | 6.3% | -0.11 |
| discussion / other | 358 | 2 | 7.3% | -0.17 |

- Dataset announcements are the weakest topic. For us this argues for leading with a finding (robotics, training data) and treating "datasets are now covered" as the second paragraph.
- "Findings about the Hub" is almost empty territory. Across all 7,259 reachable posts I found only 5 that analyse or rank Hub downloads or likes. Closest neighbours: SeaWolf-AI "Introducing the Global LLM Download Leaderboard" (37 reactions, 5 comments, about 4,100 impressions, 2 screenshots, 352 followers, 2026-09-02) and SeaWolf-AI's Model Galaxy post (21 reactions, 2026-04-30). Our launch post is the third one. So there is little prior art to calibrate against, and no direct proof either way for this category.
- The top decile is concentrated: 53 distinct authors, but SeaWolf-AI (29 posts), danielhanchen (16) and Banaxi-Tech (12) supply 40% of the 144 top-decile posts. Their patterns (one image, an emoji or product name up front, numbers) are consistent with the rest but their audience is not comparable to ours.

### 2.8 Exemplary openings (paraphrased, with links)

Verbatim quoting kept to a minimum. All are high performers in tool/launch or data-findings territory.

1. danielhanchen (1,665 followers), 68 reactions, 2 images: opens with a download milestone for a whole org plus its top model, number first. https://huggingface.co/posts/danielhanchen/325897031933200
2. danielhanchen, 72 reactions, 2 images: a one-line product announcement with the rocket emoji, "Introducing Unsloth for AMD". https://huggingface.co/posts/danielhanchen/545619346735743
3. SeaWolf-AI (352 followers), 37 reactions, 5 comments, 2 screenshots: the closest neighbour to Model Pulse, a leaderboard of trailing 30-day downloads. Its first line is "Introducing the Global LLM Download Leaderboard", followed by a short argument for why cumulative counts mislead. https://huggingface.co/posts/SeaWolf-AI/285774524970283
4. SeaWolf-AI, 65 reactions, 1 image: first line is a count and a rate (candidate molecules received in five days from 83 accounts, about 700 a day), then a thank-you, then the context. https://huggingface.co/posts/SeaWolf-AI/186831623647012
5. HannesVonEssen (67 followers), 37 reactions, 1 GIF: "I made a visualizer for Hugging Face models", the link inline in the first line, one example link, and "give me feedback". Closest in size and kind to us; 4 short lines. https://huggingface.co/posts/HannesVonEssen/653987927113609
6. ginigen-ai (77 followers), 50 reactions, 3 screenshots: opens with a plain description of what the Space does in one sentence (every model, every provider, one table), a leaderboard post. https://huggingface.co/posts/ginigen-ai/922982632751472
7. mayafree (74 followers), 44 reactions, 1 image: states a question about Hub models and that it was "checked with public data", then links the tool and lists the method in bullets. https://huggingface.co/posts/mayafree/340116886441122
8. pollix (13 followers), 21 reactions and about 6,400 impressions for the "stuntd 0.1.2 is out" tool update (https://huggingface.co/posts/pollix/214213175502538). The next release post, 0.1.3 (https://huggingface.co/posts/pollix/200093791272900), opens by saying most of the release started from a comment under the previous post; at time of writing it has 6 reactions, 1 comment, 3,498 impressions and is number 4 on trending. It is the closest analogue to a "feature update credits the community" angle.

(Items 1-7 are numbered openings I read in the data; item 8 is a feature-update pattern.)

### 2.9 Our post (tardellirs, 358817887125841, Sat 2026-10-03 16:46 UTC = 13:46 Brazil)

- 9 reactions (6 fire, 3 thumbs-up; one of the fire reactions is the author's own), 6 comments (3 threads, each from one commenter with a reply from you), 3,205 impressions, 107 followers. It was number 3 on the trending list when I queried (2026-10-04 about 18:00 UTC).
- Against all English posts since April 2026, reactions beat about 77%, comments about 88%, impressions about 80%. Against accounts with 70-150 followers, reactions beat about 74% and impressions about 82% (their median is 3).
- It followed the pattern: 179 words, 1 image, 2 HF resource cards (Space and dataset), 1 mention, 14 numbers, 7 bullets, a question at the end. The one thing the data would change: a second image (top-decile share goes from about 13% to about 27%) and a final line that asks for something specific.
- What got discussed: only the data. All 3 threads (by `dipankarsarkar`) were data-quality reviews, none were about the app or the findings. (1) Daily totals in `hub_series.parquet` came out short after gaps in the snapshots because the average landed on the first day back and the missing days had no row; the reply confirms the audit and the file was changed. (2) Days that exist but are empty (all tags at zero). (3) Stalled counters that freeze depending on repo age; the reply says this "changed the data". So the post attracted a reviewer, which hardens the data; it also means the new post can truthfully say corrections came from comments (used in the closing line of draft A and optionally in the others). Worth deciding whether to thank them by name, e.g. an @mention, which is the user's call.
- The second post by tardellirs: I could not find it. The profile page links only to 358817887125841, and no other post by the account appears in the reachable feed (to Dec 2023). It may be deleted, in an organisation, or beyond what the API lists. Send me the URL if you want it analysed.

## 3. Recommendations (for Model Pulse posts)

1. Attach 2-3 images; first image is the hook (the chart that states the finding in its title). Static PNG charts are fine; a screenshot of the app adds "this exists, you can use it". Past 4 images returns shrink.
2. Length 150-220 words, 4-8 short paragraphs separated by blank lines. Above about 250 words small accounts do worse.
3. Lead with the finding, as a sentence with a number in it (first line about 60-90 characters), not with "datasets are now covered". Dataset announcements are the weakest topic in the sample; trends (robotics, reasoning traces) are not.
4. Be number-dense but selective: 9+ numbers in the post go with better results; do not repeat the same figure and do not add figures that are not in the charts.
5. No markdown (it shows as literal asterisks). Plain `- ` bullets are fine. 0-1 emoji.
6. Put a Space or model/dataset link in the body (cards help; Space cards most). Two or three links at most; do not end on a bare URL.
7. @mention the data source (@cfahlgren1). Mentions roughly double comments.
8. Do not end on a generic question; end with a concrete invitation to check or correct a number. That is the engagement that actually happened.
9. Timing: effects are small (about +/-10%). Wednesday 2026-10-07 at about 16:00 UTC (13:00 Brazil) matches the launch slot that worked (13:46 Brazil) and the hours when you can reply, and it is neutral to slightly good in the data. If you can be online late evening Brazil, 01:00-04:00 UTC (22:00-01:00 Brazil) was the best-measured slot and weekends do slightly better; neither beats being around to answer in the first hours.
10. Be present for 2-3 hours: reply to comments, since the visible tipping point is about 4-6 early reactions.

## 4. Drafts

Shared notes: plain text; Hugging Face URLs turn into cards (Space, dataset), the modelpulse.ifsp.dev link stays a plain link. All figures are as given in the brief. Word counts are approximate (they include URLs).

### Draft A: finding first (robotics), then breadth (about 201 words)

Hook type: number-led finding. Structure: finding with its numbers, source line, two more findings, what is new, links, request to check.

Images, in order: (1) analysis/charts/09-robotics.png, (2) analysis/charts/10-training-data.png, (3) analysis/charts/12-spaces-likes.png. One chart per finding, in the order the text introduces them.

Timing: Wed 2026-10-07, 16:00 UTC (13:00 Brazil).

```
One in 7 new datasets on the Hub is now robotics data.

6,570 were created in Sep 2026, 14% of all new datasets. Robotics dataset downloads are up 16x since Mar 2025, and the people publishing them went from 46 a quarter (Q3 2024) to 2,823 (Q3 2026).

I found this after adding datasets and Spaces to Model Pulse, which rebuilds daily download history from @cfahlgren1's hub-stats snapshots. Two more findings:

- In 2022, 36% of authors citing training data cited classic NLP sets (IMDb, SQuAD, GLUE...). In 2026 it is 2.4%. Reasoning traces went from almost nothing to 12% of authors, the most cited kind.
- At the peak (Oct 2025), 122K new Spaces were created in a month, 86K of them static sites, more than 4x the pace of late 2024. Likes given per month fell by almost half, from ~35K to ~20K.

Also new: dataset pages (daily downloads and the models trained on each, e.g. 629 for FineWeb), Space pages, "Spaces using this model" on every model page, and rankings for datasets and Spaces.

App: https://huggingface.co/spaces/tardellirs/model-pulse
Report: https://modelpulse.ifsp.dev/report
Data: https://huggingface.co/datasets/modelpulse/model-pulse-data

If a number looks wrong, tell me in the comments. The first round of fixes came from there.
```

### Draft B: one story (training data), then the dataset page (about 203 words)

Hook type: contrast, number-led ("In 2022 ... In 2026"). Structure: the shift and what replaced it, how I found it, the dataset page with a direct link, three supporting numbers, short feature mention, links, request to dataset authors. The FineWeb link is a plain link; if you would like a card instead, link https://huggingface.co/datasets/HuggingFaceFW/fineweb.

Images, in order: (1) analysis/charts/10-training-data.png, (2) analysis/charts/09-robotics.png, (3) the OG card for the dataset page, https://modelpulse.ifsp.dev/og/dataset/HuggingFaceFW/fineweb.png (shows the new page itself).

Timing: Thu 2026-10-08 16:00 UTC (13:00 Brazil) if you want a distinct day from the Wed slot; otherwise Wed 2026-10-07, 16:00 UTC.

```
In 2022, 36% of authors citing training data cited classic NLP sets (IMDb, SQuAD, GLUE...). In 2026 it is 2.4%.

What took their place: reasoning traces went from almost nothing to 12% of authors in 2026, now the most cited kind. Datasets distilled from closed models (Opus, Claude, GPT-4, Gemini in the name) are cited by 4.6% of authors, up from 2.0% in 2025.

I got there by adding datasets to Model Pulse, which now tracks 1.06M of them. Each dataset page shows daily downloads and the models trained on it. 629 models list FineWeb:
https://modelpulse.ifsp.dev/dataset/HuggingFaceFW/fineweb

Other things in the data:
- 1 in 7 new datasets is now robotics (6,570 created in Sep 2026, 14%)
- Datasets get ~8M downloads a day, about 1 for every 12 model downloads, but they grew 2.5x in a year vs 1.7x for models
- The top 10 datasets take 7% of downloads, vs 22% for models

The same update adds Space pages, "Spaces using this model" on every model page, and rankings for datasets and Spaces. Built on @cfahlgren1's hub-stats snapshots.

Try it: https://huggingface.co/spaces/tardellirs/model-pulse
Open data: https://huggingface.co/datasets/modelpulse/model-pulse-data

If you publish datasets, I would like to hear what else you would want on your dataset's page.
```

### Draft C: announcement plus a list of findings (about 184 words)

Hook type: announcement ("now covers datasets and Spaces"), the best-measured hook in the sample, followed by a list of six one-line findings that reaches the other facts (models, Qwen, Spaces concentration). Shorter and more scannable; includes the Xenova/detr-resnet-50 curiosity as the closing finding.

Images, in order: (1) analysis/charts/09-robotics.png, (2) analysis/charts/06-model-size.png, (3) analysis/charts/12-spaces-likes.png. Optionally add the Galaxy card https://modelpulse.ifsp.dev/og/galaxy/meta-llama/Llama-3.1-8B.png as the fourth image to show Galaxy; I would not add more.

Timing: Wed 2026-10-07, 16:00 UTC (13:00 Brazil), or Sat 2026-10-10 about 16:00 UTC if you prefer the weekend bump.

```
Model Pulse now covers datasets and Spaces, not just models. Here is what I found:

- 1 in 7 new datasets is now robotics: 6,570 created in Sep 2026 (14%), and robotics dataset downloads are up 16x since Mar 2025
- Downloads of 100B+ parameter models grew 14x since spring 2025, vs 2.6x for models under 10B (mostly mixture-of-experts: gpt-oss-120b, DeepSeek, GLM)
- Qwen's own repos went from 9% to 30% of LLM downloads (peak 50% in Apr 2026)
- Datasets get ~8M downloads a day, 1 for every 12 model downloads, but grew faster: 2.5x in a year vs 1.7x
- 65% of liked Spaces have exactly one like; the top 1% hold 59% of all likes
- The model listed by the most Spaces is Xenova/detr-resnet-50 (2,759 Spaces), from the Transformers.js tutorial

New pages: datasets (with the models trained on each, 629 for FineWeb), Spaces (likes over time), "Spaces using this model" on every model page, rankings for datasets and Spaces, Galaxy and Wrapped.

App: https://huggingface.co/spaces/tardellirs/model-pulse
Report: https://modelpulse.ifsp.dev/report
Data: https://huggingface.co/datasets/modelpulse/model-pulse-data

Numbers come from @cfahlgren1's hub-stats snapshots. If one looks wrong, tell me.
```

My pick: Draft A. It leads with a finding, carries one chart per finding, stays near 200 words, and its last line asks for exactly the kind of checking the first post attracted. Draft B is the best story and the best for ML authors; Draft C is the most scannable.

## 5. Limits of this analysis

- Observational. Account size, organisation vs individual, and early-reaction loops are not controlled beyond a log-follower adjustment; author clusters matter (SeaWolf-AI and danielhanchen alone are 31% of the core top decile). Effects for images, numbers, mentions and resource cards held when I dropped the biggest accounts; hour and weekday effects did not clearly survive noise.
- Reactions include self-reactions; impressions are only partly settled for posts under a week old (excluded), and I could not see the feed ranking algorithm, only its fingerprints.
- The reachable listing is a partial history, with large gaps in 2024; the core results rely on the last six months and are cross-checked on the last 12.
- Topic and hook labels are regex-based and rough. Image type (chart vs screenshot vs photo) is unclassified except by eye on 10 images.
- Only one Hub-analytics comparison post with real traction exists (SeaWolf-AI), so recommendations for this exact category extrapolate from tool and launch posts in general.
- I could not find the second tardellirs post.

## Final draft (chosen 2026-10-04: Draft A, revised)

Post Wed 2026-10-07 around 16:00 UTC (13:00 Brazil); be around to reply for the first 2-3 hours. Refresh the numbers with the day's data before posting.

Images, in order: charts/09-robotics.png, charts/10-training-data.png, charts/12-spaces-likes.png, optionally a screenshot of https://modelpulse.ifsp.dev/dataset/HuggingFaceFW/fineweb.

```
One in 7 new datasets on the Hub is now robotics data.

6,570 were created in September, 14% of all new datasets. Robotics dataset downloads are up 16x since March 2025, and the people publishing them went from 46 in a quarter in 2024 to 2,823 in the last one.

I found this after adding datasets and Spaces to Model Pulse, which rebuilds daily history from @cfahlgren1's hub-stats snapshots. Two more findings:

- In 2022, 36% of authors who list training data cited classic NLP sets like IMDb, SQuAD and GLUE. In 2026 it's 2.4%. Reasoning traces went from almost nothing to 12%, now the most cited kind.
- At the peak, in October 2025, 122K Spaces were created in a single month, 86K of them static sites. That's more than 4x the pace of late 2024, while likes given per month fell from about 35K to about 20K.

New in the app: a page for every dataset, with daily downloads and the models trained on it (629 list FineWeb), a page for every Space, "Spaces using this model" on model pages, and rankings for datasets and Spaces.

App: https://huggingface.co/spaces/tardellirs/model-pulse
Report: https://modelpulse.ifsp.dev/report
Data: https://huggingface.co/datasets/modelpulse/model-pulse-data

Thanks to @dipankarsarkar, whose comments on the last post fixed three data issues. If a number looks wrong, tell me.
```
