# Fase 2 — protótipo da proliferação

**Fonte:** 1 clipe (`idle` cut-out + head-bob), o mesmo recorte colado N vezes.
**Técnica:** composição (warp de PNG com alpha). Sem filtro no clipe inteiro.
**Duração:** 10 s · 30 fps · 1920×1080

## Degraus de `N(t)` (picos)

| t (s) | N visível |
|-------|-----------|
| 0.0 | 1 |
| 2.0 | 2 |
| 4.0 | 4 |
| 6.0 | 8 |
| 8.0 | 12 |

Cada degrau nasce com um *pop* de escala (~0.28 s). Entre degraus as cópias
continuam o head-bob (fase desfasada) — a **contagem** não é constante do
início ao fim.

## Ficheiros

- script: `scripts/prototype_proliferation.py`
- vídeo: `assets/prototype/fase2_proliferation.mp4`
- gif: `assets/prototype/fase2_proliferation.gif`
- último frame (gate): `assets/prototype/fase2_last.jpg`
- first/last + timeline: `assets/prototype/fase2_first.jpg`, `fase2_timeline.jpg`

## Checklist de autoverificação

- Instâncias no frame final: **12** (compositor = 12; contagem visual de cabeças em `fase2_last.jpg` = 12). Gate: ≥ 8.
- Loop first↔last: **não** (MAE last↔first = 9.39). Esperado **não** neste protótipo: o arco é 1 → 12. Loop perfeito é a Fase 3.
- Artefacto de bloco/retângulo: **não** (fill ratio do recorte = 0.295).
- Multiplicação com picos: **sim** — degraus em t=2s, 4s, 6s, 8s.

```
.venv/bin/python scripts/prototype_proliferation.py
```
