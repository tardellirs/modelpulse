# Datasets do HF candidatos a "próximo Model Pulse" (2026-10-04)

Pesquisa somente leitura. Todos os números vêm dos scouts e do pesquisador de concorrência; nada foi medido de novo para este relatório. Onde a fonte não verificou algo, está dito.

> **Correções (verificadas em 2026-10-04, depois do relatório):**
> - O histórico do `hysts-bot-data/daily-papers-stats` não é de ~16 dias: o repositório tem 21.527 commits desde 2024-03-12 (cerca de 700 por mês, quase de hora em hora), e versões antigas baixam normalmente (2.130 papers em 03/2024, 8.087 em 06/2025, 18.535 hoje; campos `arxiv_id`, `upvotes` e, depois, `num_comments`). Uma versão por dia desde 2024 dá ~935 arquivos de até 1,5 MB, menos de 1 GB. O scout só paginou os primeiros 400 commits.
> - O histórico de estrelas do GitHub pode ser reconstruído pela API do GitHub (data de cada estrela), com custo de rate limit, não só desde 2026-07.
> - O Model Pulse aparece em "Spaces using" de lmarena, mteb e outros só porque o robô de links lista os datasets mais baixados no README; não consome esses dados. Essas ideias seriam produtos novos.
> - `hfmlsoc/hub_weekly_snapshots` começa em 2024-07-24, como o Model Pulse: não estende o histórico para trás, no máximo tapa buracos.

## Resumo: as 3 melhores ideias

1. **Papers do HF Daily Papers (hysts-bot-data: daily-papers-stats + paper-github-stars).** Uma página por paper com curva de upvotes e de estrelas no GitHub, e histórico de ranking. Os Spaces e páginas oficiais mostram só o estado atual. A fonte atualiza várias vezes por dia, mas o histórico é jovem (cerca de 16 dias nos stats, desde 2026-07 nas estrelas), então o valor vem de começar a acumular já.
2. **Arena de LLMs (lmarena-ai/leaderboard-dataset).** Uma página por modelo com Elo e rank por categoria (text, vision, search, agent, image_edit, video, document) ao longo do tempo, mais páginas de fornecedor. É o número mais acompanhado da área, com 124 commits em 30 dias. Custo: reconstruir a série exige reprocessar revisões git de parquets grandes, cerca de 6 GB de storage. Já existem sites de histórico agregado, mas nenhum produto polido por modelo.
3. **MTEB (mteb/results).** Uma página por modelo de embedding com notas por tarefa, data de entrada e rank ao longo do tempo. Autores olham o próprio resultado, os dados são CC0 e o Space oficial é pesado e só mostra a tabela atual. A limitação é que o "histórico" é sobretudo a data de primeira aparição, porque as notas raramente mudam.

Aviso importante: o Model Pulse já aparece em "Spaces using this dataset" de lmarena, mteb/results, Weyaxi/huggingface-leaderboard, open-asr-leaderboard-results e open-llm-leaderboard/requests. O pesquisador não conseguiu dizer se são fontes primárias. Se já são consumidas, essas ideias são um produto separado ou uma extensão do Model Pulse, não dados novos. Vale conferir isso no seu código antes de escolher.

## Tabela de pontuação

Critérios, 0 a 5 cada: **P1** atualização regular com histórico recuperável; **P2** página por entidade com público que se procura; **P3** público e distribuição no ecossistema HF; **P4** fraqueza dos produtos existentes (5 menos a força do concorrente da pesquisa); **F** viabilidade (tamanho, licença, custo em VPS pequena com DuckDB/polars). Total máximo 25. As notas são julgamento meu sobre os dados dos scouts; onde algo não foi verificado, a nota é conservadora.

| Candidato | P1 | P2 | P3 | P4 | F | Total | Veredito |
|---|---|---|---|---|---|---|---|
| [hysts-bot-data/daily-papers-stats](https://huggingface.co/datasets/hysts-bot-data/daily-papers-stats) | 3 | 5 | 5 | 3 | 3 | **19** | Top 1. Histórico curto, mas acumula desde já. Sem licença declarada. |
| [lmarena-ai/leaderboard-dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset) | 4 | 5 | 4 | 2 | 2 | **17** | Top 2. Maior público; reprocessar revisões é pesado. |
| [mteb/results](https://huggingface.co/datasets/mteb/results) | 3 | 4 | 5 | 2 | 3 | **17** | Top 3. CC0; história é basicamente a data de entrada. |
| [gaia-benchmark/results_public](https://huggingface.co/datasets/gaia-benchmark/results_public) | 4 | 3 | 3 | 3 | 4 | **17** | Top 4. Pouca concorrência, poucas páginas. |
| [hf-audio/open-asr-leaderboard-results](https://huggingface.co/datasets/hf-audio/open-asr-leaderboard-results) | 3 | 3 | 5 | 2 | 4 | **17** | Top 5. Conjunto pequeno de modelos. |
| [hysts-bot-data/paper-github-stars](https://huggingface.co/datasets/hysts-bot-data/paper-github-stars) | 3 | 4 | 4 | 3 | 3 | **17** | Entra junto com a ideia 1 (join por id do paper). |
| [hysts-bot-data/daily-papers](https://huggingface.co/datasets/hysts-bot-data/daily-papers) | 4 | 5 | 5 | 3 | 1 | **18** | Mesmo sinal que o stats, mas 37 MB por revisão e 110 GB de storage. Usar o stats. |
| [hfmlsoc/hub_weekly_snapshots](https://huggingface.co/datasets/hfmlsoc/hub_weekly_snapshots) | 4 | 4 | 5 | 3 | 3 | **19** | Backfill do Model Pulse, não produto novo. ODbL (share-alike). |
| [Weyaxi/followers-leaderboard](https://huggingface.co/datasets/Weyaxi/followers-leaderboard) | 4 | 3 | 5 | 3 | 3 | **18** | Backfill. Só top-N, quem está fora não tem histórico. |
| [Weyaxi/huggingface-leaderboard](https://huggingface.co/datasets/Weyaxi/huggingface-leaderboard) | 3 | 4 | 5 | 3 | 1 | **16** | Backfill. Não é 2x ao dia, é a cada 2 a 7 dias; cerca de 851 GB. |
| [librarian-bots/model_cards_with_metadata](https://huggingface.co/datasets/librarian-bots/model_cards_with_metadata) | 4 | 2 | 5 | 4 | 1 | **16** | Pouca demanda (759 downloads, 0 likes) e parquet substituído todo dia. |
| [hf-azure-internal/trending-models-analysis](https://huggingface.co/datasets/hf-azure-internal/trending-models-analysis) | 3 | 3 | 5 | 4 | 0 | **15** | Org interna, esquema não lido. Descartado. |
| [venvoo/openrouter-uptime](https://huggingface.co/datasets/venvoo/openrouter-uptime) | 4 | 3 | 2 | 2 | 4 | **15** | Vários concorrentes parciais, fora do HF, ToS do OpenRouter. |
| [open-llm-leaderboard/requests](https://huggingface.co/datasets/open-llm-leaderboard/requests) | 1 | 3 | 5 | 1 | 4 | **14** | Board aposentado, dados estáticos desde março de 2025. |
| [Pendrokar/TTS_Arena](https://huggingface.co/datasets/Pendrokar/TTS_Arena) | 3 | 4 | 4 | 2 | 0 | **13** | Um SQLite de 43 MB regravado, 742 GB de histórico; privacidade e licença sem verificação. |
| [tensorfeed/ai-ecosystem-daily](https://huggingface.co/datasets/tensorfeed/ai-ecosystem-daily) | 4 | 2 | 2 | 2 | 3 | **13** | Preços lotados de concorrentes, fonte única, licença "other". |
| [taesiri/ArXivSignals](https://huggingface.co/datasets/taesiri/ArXivSignals) | 4 | 2 | 1 | 2 | 2 | **11** | Esquema não lido, fora do HF, cerca de 9 GB. |
| [dynamicfeed/ai-model-pricing-daily](https://huggingface.co/datasets/dynamicfeed/ai-model-pricing-daily) | 3 | 1 | 2 | 1 | 4 | **11** | Mercado lotado; histórico possivelmente achatado (usedStorage negativo). |
| [librarian-bots/arxiv-metadata-snapshot](https://huggingface.co/datasets/librarian-bots/arxiv-metadata-snapshot) | 2 | 2 | 1 | 1 | 3 | **9** | Quase sem deriva, arXiv já tem tudo, fora do HF. |

Nota sobre a ordem do Top 5: os totais empatam em 17 para quatro candidatos, e o desempate foi a força do público que se procura (P2). hfmlsoc e Weyaxi/followers pontuam alto, mas ficam de fora do Top 5 porque cobrem as mesmas entidades do Model Pulse e servem melhor como backfill. O daily-papers (18) fica de fora por ser a versão pesada do stats.

## Top 5 em detalhe

### 1. Papers do Daily Papers (daily-papers-stats + paper-github-stars)

**O dataset.** `hysts-bot-data/daily-papers-stats` guarda upvotes, comentários e estrelas do GitHub dos Daily Papers num `data.json` sobrescrito a cada execução (1,5 MB; 4 MB de storage usado). Cadência: mais de 400 commits em 30 dias, cerca de um por hora. Os primeiros 400 commits vão até 2026-09-18, ou seja, cerca de 16 dias de histórico (o pesquisador de concorrência só confirmou cerca de 2 dias diretamente; os 16 vêm da paginação do scout). `paper-github-stars` é um `data/stars.parquet` (cerca de 18 MB), quase diário (50 commits em 47 dias distintos), criado em 2026-07-08, com 285 downloads. O stats tem 4.409 downloads e 3 likes. Nenhum tem licença declarada. A fonte original, `daily-papers`, é um JSON de 37 MB regravado a cada 2 a 4 horas e tem 110 GB de storage, ou seja, é pesado demais para reconstruir.

**O produto.** Páginas de paper (curva de upvotes e de estrelas, comentários), páginas de autor (os papers do autor e a evolução de cada um), ranking diário/semanal dos Daily Papers com histórico de posição, e selos ("subiu X posições", "passou de N estrelas"). O que ninguém tem: série temporal por paper. `hysts/daily-papers` (296 likes) e `huggingface/paper-central` (229 likes) mostram só o estado atual; paper-central tem páginas por paper mas sem série.

**Dado derivado novo.** Upvotes por dia por paper, tempo até o pico, posição diária no ranking, estrelas por dia por repo, e a relação entre upvotes e estrelas.

**Alcance.** Autores de papers procuram o próprio paper; links "Spaces using" nos datasets hysts-bot-data; posts no HF sobre os papers da semana; selos para os autores colocarem no README; SEO de cauda longa por título de paper.

**MVP (cerca de 1 semana).**
- Coletor: baixar a revisão atual do stats a cada hora e acrescentar em parquet próprio (e o mesmo para stars por dia). Não depender só do git.
- Recuperar o que der das revisões git dos últimos ~16 dias, só do arquivo de 1,5 MB.
- Página de paper com gráfico, página de autor, ranking do dia.
- Selo SVG por paper.
- Publicar no HF Space com o mesmo stack do Model Pulse.

**Riscos.** Sem licença declarada e derivado de páginas de papers do HF. Histórico jovem: a série só fica boa depois de semanas. Se o bot parar, a fonte seca. Cuidado com o volume de commits ao baixar revisões.

### 2. Arena de LLMs (lmarena-ai/leaderboard-dataset)

**O dataset.** Exportações oficiais do LMArena (text, vision, search, agent, image_edit, video, document), cada uma em parquet "full" e "latest", sobrescritas no lugar. 24 pastas de topo. 124 commits em 30 dias (cerca de 4 por dia); os primeiros 400 commits cobrem 2026-07-07 a 2026-10-03, e o pesquisador disse que revisões mais antigas provavelmente existem além do limite de 400 da API. 69.649 downloads, 28 likes, CC-BY-4.0, cerca de 6 GB de storage usado.

**O produto.** Uma página por modelo com Elo e rank por categoria ao longo do tempo, selos de mudança de rank, páginas de fornecedor/laboratório, e um "quem subiu e quem caiu esta semana". O que falta hoje: `lmarena-ai/arena-leaderboard` (5.010 likes) está estático (atualizado em 2026-02-21) e mostra só o quadro atual. Sites externos (benchlm.ai, llm-stats.com, repositórios no GitHub) têm histórico, mas agregado ou focado em "quem é o nº 1", sem páginas por modelo.

**Dado derivado novo.** Série de Elo/rank por modelo e categoria a partir das diferenças entre revisões do parquet "latest"; data de entrada de cada modelo no ranking; intervalo de confiança ao longo do tempo, se as colunas existirem (não verificado).

**Alcance.** Laboratórios e fine-tuners buscam o próprio modelo; selo de rank; posts no HF/X quando há mudança de topo; "Spaces using" (hoje só `jay0826/discord-bot` e o próprio Model Pulse); SEO por nome de modelo.

**MVP (cerca de 1 semana).**
- Listar os commits via API e baixar só o parquet "latest" de uma categoria (text) a cada N commits, para os últimos 90 dias.
- Normalizar nomes de modelo, gravar parquet de série em DuckDB.
- Páginas por modelo e fornecedor para text; depois as outras categorias.
- Coletor diário daqui para frente (um download por dia basta).
- Selo de rank.

**Riscos.** Replay de revisões pesado (parquets grandes, 6 GB de storage). Nomes de modelo podem mudar entre revisões. O quadro ao vivo do lmarena.ai é bom e o mercado de "histórico de arena" já tem vários sites. Dependência de a LMArena continuar publicando.

### 3. MTEB (mteb/results)

**O dataset.** JSONs de resultado em uma pasta por modelo e revisão, empurrados continuamente. 39 commits em 30 dias; os primeiros 400 commits vão até 2026-06-02 (listagem completa, verificada em 144 commits). 272.842 downloads, 18 likes, CC0-1.0. Muitos arquivos pequenos, então o repositório é grande em número de arquivos.

**O produto.** Uma página por modelo de embedding com nota por tarefa e categoria, data de entrada, posição ao longo do tempo e comparação com vizinhos. O que falta: `mteb/leaderboard` (7.703 likes) é uma tabela única, pesada e lenta (docker), sem página por modelo e sem histórico.

**Dado derivado novo.** Data de primeira aparição de cada modelo (via commit que adicionou a pasta), rank médio por data, e mudanças quando um modelo ganha resultados novos.

**Alcance.** Autores de modelos de embedding (BGE, Qwen, Jina, Voyage, OpenAI e outros) conferem o próprio MTEB; selo; link no dataset (hoje o "Spaces using" tem Spaces mortos ou menores além do Model Pulse); SEO por nome de modelo.

**MVP (cerca de 1 semana).**
- Clonar com sparse ou listar a árvore e ler os JSONs com polars; datar cada pasta pelo primeiro commit.
- Tabela modelo x tarefa x nota; calcular médias por categoria.
- Página por modelo e ranking com filtro.
- Rodar diariamente em modo incremental (39 commits por mês é pouco).

**Riscos.** A série é fraca, porque as notas raramente mudam e cada modelo entra uma vez. O Space oficial domina a atenção. O cálculo oficial da média MTEB pode ter regras que não estão nos JSONs (não verificado). Processar muitos arquivos pequenos é lento.

### 4. GAIA (gaia-benchmark/results_public)

**O dataset.** Submissões e notas públicas do benchmark GAIA de agentes. Segundo o scout, 169 commits em 30 dias e primeiros 400 commits desde 2026-06-18; o pesquisador de concorrência só enxergou commits de 2026-09-22 a 2026-10-04 e não verificou o que cada commit representa. Tem esquema no README: modelo, família, organização, nota, notas por nível e data, com splits de validação e teste. Cerca de algumas centenas de linhas (pesquisador). 4.039 downloads, 26 likes, sem licença declarada.

**O produto.** Página por submissão e por organização, ranking ao longo do tempo (a coluna de data permite reconstruir histórico mesmo sem git). `gaia-benchmark/leaderboard` (628 likes) mostra só o estado atual, atualizado em 2026-05-03.

**Dado derivado novo.** Rank da submissão por data, evolução do melhor resultado, quem ultrapassou quem.

**Alcance.** Construtores de agentes e laboratórios conferem seu rank GAIA; selo; hoje nenhum Space usa o dataset, então o link "Spaces using" apareceria sozinho.

**MVP (cerca de 1 semana).** Ler os arquivos, montar a série pela coluna de data, gerar páginas por organização e submissão, um gráfico de rank no tempo; um selo.

**Riscos.** Poucas linhas, então poucas páginas e pouco SEO. Os campos `system_prompt` e `url` ficariam republicados; verificar antes (sem licença declarada). Há divergência entre scout e pesquisador na profundidade do histórico, então confirmar no primeiro dia.

### 5. Open ASR Leaderboard (hf-audio/open-asr-leaderboard-results)

**O dataset.** Linhas de resultado (WER e RTFx por modelo e dataset) do Open ASR Leaderboard. 21 commits em 30 dias, 48 no total desde 2026-05-12, último commit 2026-10-01. 9.766 downloads, 1 like, sem licença declarada, pequeno. Cada commit provavelmente é uma submissão de modelo (não verificado).

**O produto.** Página por modelo ASR com WER/RTFx por dataset, data de entrada e rank ao longo do tempo. `hf-audio/open_asr_leaderboard` (1.479 likes) mostra só a tabela atual. Há também placares por idioma (árabe, 110 likes; `opedromartins/open_asr_leaderboard_ptbr`, 3 likes), que ajudam como extensão (o português brasileiro é um bom gancho para você).

**Dado derivado novo.** Data de entrada de cada modelo, rank por data, frente de Pareto WER x RTFx ao longo do tempo.

**Alcance.** Autores de Whisper, NVIDIA, Meta e fine-tunes comunitários; selo; o dataset já lista o Model Pulse como consumidor.

**MVP (cerca de 1 semana).** Ler os resultados via commits, uma página por modelo, uma página de ranking com Pareto, selo.

**Riscos.** Poucos modelos, então poucas páginas. O Space oficial tem muita tração. Cadência baixa (21 commits em 30 dias).

## Descartados e por quê

- **hfmlsoc/hub_weekly_snapshots** (19): mesmas entidades do Model Pulse; serve como backfill de cerca de 2 anos semanais (114 partições de modelos, 2024-07-24 a 2026-09-30). ODbL tem share-alike para base derivada.
- **Weyaxi/followers-leaderboard** (18): só top-N de seguidores, quem está fora não tem histórico. Sem licença. Bom como backfill de autores.
- **Weyaxi/huggingface-leaderboard** (16): o scout errou, não é 2x ao dia, é a cada 2 a 7 dias; cerca de 851 GB de storage e arquivos de 18 a 85 MB. Sem licença. Só vale para backfill pontual.
- **hysts-bot-data/daily-papers** (18): mesma informação que o stats, mas 37 MB por revisão e 110 GB; usar o stats.
- **librarian-bots/model_cards_with_metadata** (16): 759 downloads e 0 likes; parquet inteiro regravado por dia, histórico de vários GB por revisão.
- **hf-azure-internal/trending-models-analysis** (15): organização interna (republicar é questionável), esquema não lido, o HF já tem a lista oficial de trending.
- **venvoo/openrouter-uptime** (15): vários concorrentes parciais (status.openrouter.ai, dthinkr/openrouter-uptime, outros), fora do HF, depende do ToS do OpenRouter.
- **open-llm-leaderboard/requests** (14): board aposentado; contents e results estáticos desde março de 2025; sem eixo de tempo.
- **Pendrokar/TTS_Arena** (13): o scout errou, é um SQLite de 43 MB regravado a cada cerca de 5 minutos (742 GB de storage), não um log limpo de votos; sem audio; privacidade dos votantes não verificada e sem licença.
- **tensorfeed/ai-ecosystem-daily** (13): mercado de preços lotado, fonte única de um agregador, licença "other", esquema não lido.
- **taesiri/ArXivSignals** (11): esquema não lido, fora do HF, cerca de 9 GB.
- **dynamicfeed/ai-model-pricing-daily** (11): mercado muito lotado (pricepertoken, benchlm, tokencanopy/price e outros); usedStorage negativo sugere histórico achatado, a verificar; público não é de autores.
- **librarian-bots/arxiv-metadata-snapshot** (9): metadados quase não mudam entre snapshots; arXiv e Semantic Scholar já cobrem páginas por paper e autor; fora do HF.

## Correções aos scouts (para não propagar)

- Weyaxi/huggingface-leaderboard: a cadência real é de 2 a 7 dias, não 2 por dia.
- Pendrokar/TTS_Arena: é um SQLite sobrescrito, não um log de votos limpo.
- A profundidade de 16 dias do daily-papers-stats e a série diária do followers-leaderboard vieram de paginação do scout; o pesquisador só viu cerca de 2 dias diretamente.
- GAIA: 169 commits em 30 dias (scout) versus histórico visível só de 2026-09-22 a 10-04 (pesquisador). Confirmar.
- Itens não verificados por ninguém: tamanho real de lmarena e hfmlsoc, esquemas de parquet, ToS de fontes externas, recálculo de Elo a partir de votos brutos.

## Fontes

Dados dos scouts, via API pública do HF (`/api/datasets`, `/commits/main`, `/tree/main`) e páginas dos datasets listados na tabela acima. Concorrência e Spaces:

- [lmarena-ai/arena-leaderboard](https://huggingface.co/spaces/lmarena-ai/arena-leaderboard), [mteb/leaderboard](https://huggingface.co/spaces/mteb/leaderboard), [hf-audio/open_asr_leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard), [gaia-benchmark/leaderboard](https://huggingface.co/spaces/gaia-benchmark/leaderboard), [hysts/daily-papers](https://huggingface.co/spaces/hysts/daily-papers), [huggingface/paper-central](https://huggingface.co/spaces/huggingface/paper-central), [huggingface/whos-shipping-open-source-ai](https://huggingface.co/spaces/huggingface/whos-shipping-open-source-ai), [tardellirs/model-pulse](https://huggingface.co/spaces/tardellirs/model-pulse)
- [benchlm.ai/llm-leaderboard-history](https://benchlm.ai/llm-leaderboard-history), [llm-stats.com/benchmarks/lmarena-text](https://llm-stats.com/benchmarks/lmarena-text), [arielshakaramiro/llm-leaderboard-tracker](https://github.com/arielshakaramiro/llm-leaderboard-tracker), [rahulbkumar/lmarena-dataviz](https://github.com/rahulbkumar/lmarena-dataviz)
- [Trending Papers changelog](https://huggingface.co/changelog/trending-papers)
- [pricepertoken.com](https://pricepertoken.com/), [simonw/llm-prices](https://github.com/simonw/llm-prices), [tokencanopy/price](https://github.com/tokencanopy/price), [dthinkr/openrouter-uptime](https://github.com/dthinkr/openrouter-uptime)
