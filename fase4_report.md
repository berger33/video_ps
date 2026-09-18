# VÍDEO 3 — FASE 4 · Build completo 60s (corte com áudio)

Script: `scripts/fase4_build.py` · QA: `scripts/fase4_qa.py`
Entregas: `assets/build/fase4/video_ps_fase4.mp4` (h264+AAC, 60.00s, 30fps,
1344×754) · `review_fase4.gif` · `_qa_sheet.png` · `report_fase4.json`

## O que o corte faz
- 0–6s: 1 raposa (protagonista, wander senoidal periódico → loop fecha).
- ADDs caem nos onsets da Fase 3: cada cópia nova = mesmo clipe em loop com
  **offset de tempo não uniforme distinto das ativas** (12/19/27/33/41/47f),
  reveal por **oclusão + wipe 17f** (desenhada sob a âncora) ou **entrada
  andando pela borda** (16–18f).
- REMOVEs nos onsets: cópia sai em disparada p/ borda mais próxima.
- Técnicas 1–6 ativas em toda cópia: matting, foot-anchor no chão, cor por
  ambiente local, sombra de contato, escala por profundidade (0.55–1.0).
- 58–60s: 1 instância; frame 1800 == frame 0 (mesmo trecho de origem).

## CHECKLIST (números)
| Item | Resultado | Gate |
|---|---|---|
| Frames de reveal por evento (máscara/visibilidade 0→100%) | **32 eventos: mín 16, méd 16.8** (occl 17f; enter 16–18f) | ≥8 ✅ |
| 2+ cópias simultâneas com pose idêntica? | **NÃO** — diff mín 6.99/255 entre instâncias visíveis | ✅ |
| Distância início-evento → onset | ≤0.493 frame (eventos = frames dos onsets da Fase 3) | ≤1 ✅ |
| Contagem visível/s × RMS | **Pearson 0.888** | ✅ |
| 1º/último frame: mesmo trecho, sem cópias extras? | **SIM** (diff pontas do gif 1.61/255; count 1 nas pontas) | ✅ |
| Blocos/retângulos estáticos? | **NÃO** (ver `_qa_sheet.png`) | ✅ |
| Sombras de contato / cor casada | em todas as instâncias | ✅ |
| Instâncias totais / pico | 33 / 8 | — |
| Áudio | AAC 44.1k muxado, 60.00s | ✅ |

## Observações p/ FASE 5 (polimento)
- Multidão concentra-se no centro-esquerda; espalhar slots de spawn p/
  preencher melhor o campo no pico.
- Saídas em disparada (24px/f) funcionam mas podem ganhar easing.
- Export final 1080p (hoje 1344×754) + ajuste fino de cor geral.

**Gate FASE 4:** aprovado por escrito → FASE 5.
