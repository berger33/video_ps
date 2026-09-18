# VÍDEO 3 — FASE 3 · Sincronia de áudio (timing), antes de aplicar ao vídeo

Scripts: `scripts/make_track.py` (trilha) · `scripts/fase3_audio.py` (análise)
Artefatos: `assets/src/trilha.wav` · `assets/build/fase3/{events_fase3.json,
report_fase3.json, curva_rms_count.png}`

## Trilha
- Original, royalty-free, determinística: 60.0s, ~112 BPM, eletrônica
  excêntrica (kicks toy, plucks pentatônicos c/ nota "errada" cômica, pad
  detunado). Arco: intro quieta → médio → alto → **pico 40–48s** → queda →
  silêncio final (loop).

## Análise (números)
| Métrica | Valor | Gate |
|---|---|---|
| Onsets detectados (`librosa.onset.onset_detect`) | 251 | — |
| Eventos totais / ADD / REMOVE | 64 / 32 / 32 | — |
| Distância máx. início-ADD → onset mais próximo | **0.442 frame** @30fps | ≤1 ✅ |
| Distância máx. (todos os eventos) → onset | 0.442 frame | ≤1 ✅ |
| Correlação (Pearson) contagem/s × RMS/s | **0.931** | visível no plot ✅ |
| Instâncias: início / pico / final | 1 / 8 / 1 | arco ✅ |
| Primeiro ADD | t=6.06s (após intro quieta) | ✅ |
| Último REMOVE | t=58.03s; 58–60s só 1 instância | loop ✅ |

## Como ler o plot (`curva_rms_count.png`)
- Azul preenchido = RMS normalizada (janela 1.5s) da trilha real.
- Vermelha em degraus = contagem-alvo de instâncias por segundo
  (`1 + round(8 * RMSnorm^1.1)`, forçada a 1 antes de 6s e depois de 57s).
- Linhas verdes = ADD, laranja = REMOVE — todas sobre onsets.

## Scheduler (regras)
- ADD só com cooldown ≥0.6s e antes de 50s; REMOVE cooldown ≥0.45s.
- Todo evento cai NO onset (frame = round(onset*30) → erro ≤0.5 frame).
- Garantia de fechamento: REMOVEs extras em onsets remanescentes até
  count==1 (dedupe por frame).

## Próximo passo (FASE 4, só após aprovação)
Aplicar `events_fase3.json` ao compositor da Fase 2 ao longo dos 60s:
cada ADD = novo clone (offset de tempo não uniforme p/ cópia nova, reveal
16f por oclusão+wipe, escala por profundidade, sombra, cor); cada REMOVE =
saída andando p/ fora do quadro/oclusão reversa; frame 0 e 1799 sem cópias
extras (loop).

**Gate FASE 3:** aprovar trilha + curva + lista de timestamps por escrito.
