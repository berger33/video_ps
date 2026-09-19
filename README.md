# video_ps

Piloto do filme **"Pombo//Protocolo"** — trecho **0:00–0:45**, inspirado no estilo do animador
Cyriak Harris: um pombo comum de São Paulo numa calçada do Centro, com duplicação por bicada.

## Regra causal (não negociável)

**BICADA = DUPLICAÇÃO.** Cada bicada no chão duplica algo. No começo, a migalha; depois, as
migalhas duplicadas revelam pernas e viram minipombos; no clímax, todos bicam ao mesmo tempo.

## Status do projeto

Trabalho conduzido em fases, com aprovação humana obrigatória entre cada uma.

| Fase | Escopo | Status |
|---|---|---|
| 0 | Entendimento do roteiro (sem código) | **aprovada** |
| 1 | Aquisição/preparação de assets (clipes + máscaras alpha) | **aprovada** |
| 2 | Protótipo do mecanismo (1 bicada → 1 duplicação, por oclusão) | **aprovada (com ajustes)** |
| 3 | Áudio (diegético ou trilha pronta — decisão documentada) | **aprovada** |
| 4 | Build do trecho completo 0:00–0:45 | **entregue — aguardando aprovação** |
| 5 | Polimento e exportação MP4 1080p | pendente |

## Documentos

- [`docs/fase0-entendimento.md`](docs/fase0-entendimento.md) — arco 0:00–0:45 reescrito,
  regra causal, tabela de eventos, técnicas obrigatórias, anti-padrões, checklist de
  autoverificação com métricas e registro de decisões (Fase 0).
- [`docs/fase1-assets.md`](docs/fase1-assets.md) — análise medida do material recebido
  (redundância, paralaxe, qualidade por região, localização da bicada em f400), pivotamento
  do matting, assets produzidos com números e checklist parcial (Fase 1).
- [`docs/fase2-mecanismo.md`](docs/fase2-mecanismo.md) — protótipo do mecanismo: bicada →
  salto → oclusão (carapaça) → duplicação, com checklist medido (reveal 10 frames,
  MAE 45,1 entre poses, oclusão 100%, sombra Δ 8–12) e decisões de design (Fase 2).
- [`docs/fase3-audio.md`](docs/fase3-audio.md) — trilha 45,000s: caminho
  diegético (percussão 100% do clipe, baixo sintetizado por não haver arrulho
  no material), grade 120 BPM, eventos, regra de sincronia (bicada f400 =
  mestra) e checklist medido 5/5 (Fase 3).
- [`docs/fase4-build.md`](docs/fase4-build.md) — build completo: S1 documental + S2
  forrageio com 6 bicadas sincronizadas, cadeia de duplicação A→B/C/D→4 minipombos
  (revelação 100% por oclusão), regra anti-pop e checklist medido 9/9 (Fase 4).

## Material de origem

`crie_de_outro_video_de_pombo.mp4` (20 s, 1280×720, 24 fps, com áudio). O arquivo
`consegue_criar_um_gid_deste_po.mp4` é redundante (primeiros 240 frames do mesmo clipe).
Os assets de mídia não entram no Git; ver `.gitignore`.

## Convenções

- Código, docs e listas de decisão entram no Git. **Assets de mídia não** — vídeo, máscaras,
  áudio, renders e modelos vivem no workspace local (ver `.gitignore`).
- Ambiente sem GPU (2 vCPU / 3 GB), com dependências recriadas a cada turno por script
  idempotente de setup.
