# Fase 3 — corte bruto mudo (75 s, loop)

Composição de recortes da Fase 1 sobre o prato do telhado. Sem áudio.
**1920×1080** · 30 fps · 75 s · mudo

Técnica: o mesmo recorte (e poses discretas) colado N vezes com Δposição /
Δescala / Δrotação. Sem filtro no clipe inteiro.

## `N(t)` — picos, não constante

| t (s) | bloco | N | pose dominante |
|-------|-------|---|----------------|
| 0–15 | estabelecer | 1 | idle bob |
| 15 / 22.5 | duplicação | 2 → 4 | walk |
| 30 / 37.5 | geometria | 8 → 16 | peck / head_turn |
| 45 / 52.5 | clímax | 24 → **32** | idle + coo/fluff no anel interno |
| 60–73.5 | colapso | 16→8→4→2→1 | idle |
| 73.5–75 | lock de loop | 1 | idle, pose = frame 0 |

Layout explícito (não retângulo): N=1 centro; N=2 lado a lado; N=4 losango;
N=8 elipse (rx=370, ry=120); N≥16 anéis 8+12+12.

## Ficheiros

- script: `scripts/build_mute_timeline.py`
- corte: `assets/edit/fase3_mute.mp4`
- clímax gif: `assets/edit/fase3_climax.gif`
- first/last/loop: `assets/edit/fase3_first.jpg`, `fase3_last.jpg`, `fase3_loop_compare.jpg`
- timeline: `assets/edit/fase3_timeline.jpg`
- clímax still: `assets/edit/fase3_climax.jpg`

## Checklist de autoverificação

- Instâncias no **frame final**: **1** (colapso para loop; pico do filme = **32** em t=52.5s). Contagem visual: first/last = 1 pombo idle; N=2 = 2 cópias distintas; N=4 = 4 cabeças em losango; N=8 = 8 pombos em elipse; clímax ≈ 30 cópias contáveis no telhado.
- Loop first↔last: **sim** (MAE last↔first = 1.54; MAE frame0↔frame1 = 0.62).
- Artefacto de bloco/retângulo: **não**.
- Multiplicação com picos: **sim** — degraus em 15.0s(N=2), 22.5s(N=4), 30.0s(N=8), 37.5s(N=16), 45.0s(N=24), 52.5s(N=32), 60.0s(N=16), 65.0s(N=8), 69.0s(N=4), 72.0s(N=2), 73.5s(N=1).

```
.venv/bin/python scripts/build_mute_timeline.py
```
