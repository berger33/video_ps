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
| 0 | Entendimento do roteiro (sem código) | **entregue — aguardando aprovação** |
| 1 | Aquisição/preparação de assets (clipes + máscaras alpha) | pendente |
| 2 | Protótipo do mecanismo (1 bicada → 1 duplicação, por oclusão) | pendente |
| 3 | Áudio (diegético ou trilha pronta — decisão documentada) | pendente |
| 4 | Build do trecho completo 0:00–0:45 | pendente |
| 5 | Polimento e exportação MP4 1080p | pendente |

## Documentos

- [`docs/fase0-entendimento.md`](docs/fase0-entendimento.md) — arco 0:00–0:45 reescrito,
  regra causal, tabela de eventos, técnicas obrigatórias, anti-padrões, checklist de
  autoverificação com métricas e registro de decisões (Fase 0).

## Convenções

- Código, docs e listas de decisão entram no Git. **Assets de mídia não** — vídeo, máscaras,
  áudio, renders e modelos vivem no workspace local (ver `.gitignore`).
- Ambiente sem GPU (2 vCPU / 3 GB), com dependências recriadas a cada turno por script
  idempotente de setup.
