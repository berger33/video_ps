# Fase 3 — Sincronia de áudio

## Arquivos entregues

- Script reproduzível: `scripts/phase3_audio_timing.py`
- Trilha original criada para este projeto: `assets/audio/capybara_psych_original_60s.wav`
- Dados completos: `assets/phase3/timing.json`
- Curvas sobrepostas: `previews/fase3_rms_onsets_counts.png`
- Preview renderizado do timing: `previews/fase3_timing_preview.gif`

A trilha é uma composição original de 60 s, eletrônica/psicodélica, com referência de 150 BPM. Ela não copia a gravação de *Cows & Cows & Cows*. O script grava a WAV e analisa o arquivo efetivamente gerado, não uma estimativa manual.

## Método

- RMS: `librosa.feature.rms`, mono, 22.050 Hz, `hop_length=512`, janela efetiva de aproximadamente 23,22 ms
- Macro: mediana do RMS em blocos de 1 segundo, normalizada entre os percentis 5 e 95 e quantizada para 1–8 instâncias
- Micro: `librosa.onset.onset_detect`
- Cada transição da contagem macro é associada automaticamente ao onset mais próximo; o frame do evento é calculado em 30 fps

## Resultado numérico

- Duração analisada: **60,0000 s**
- BPM de referência da composição: **150**
- Onsets detectados: **236**
- Correlação RMS normalizado × contagem-alvo: **0,992975**
- Máxima distância evento → onset mais próximo: **0 frames**
- Limite exigido: **1 frame** — **passou**

## Eventos gerados

| Tipo | De → para | Boundary RMS | Frame do evento | Tempo | Distância ao onset |
|---|---:|---:|---:|---:|---:|
| duplicação | 1 → 2 | 4 s | 123 | 4,0867 s | 0 |
| duplicação | 2 → 3 | 9 s | 267 | 8,8932 s | 0 |
| duplicação | 3 → 4 | 13 s | 387 | 12,8871 s | 0 |
| duplicação | 4 → 5 | 16 s | 483 | 16,0914 s | 0 |
| duplicação | 5 → 6 | 20 s | 603 | 20,0853 s | 0 |
| duplicação | 6 → 7 | 28 s | 841 | 28,0265 s | 0 |
| duplicação | 7 → 8 | 36 s | 1080 | 36,0141 s | 0 |
| redução | 8 → 7 | 45 s | 1347 | 44,8842 s | 0 |
| redução | 7 → 6 | 47 s | 1407 | 46,9043 s | 0 |
| redução | 6 → 5 | 49 s | 1467 | 48,9012 s | 0 |
| duplicação | 5 → 6 | 50 s | 1503 | 50,0854 s | 0 |
| redução | 6 → 5 | 51 s | 1527 | 50,8981 s | 0 |
| redução | 5 → 4 | 53 s | 1587 | 52,8951 s | 0 |
| redução | 4 → 3 | 54 s | 1621 | 54,0328 s | 0 |
| redução | 3 → 2 | 56 s | 1683 | 56,0994 s | 0 |
| redução | 2 → 1 | 58 s | 1743 | 58,0963 s | 0 |

A oscilação breve de 5 → 6 → 5 entre 50 e 51 s é resultado da curva RMS real da trilha e foi preservada, em vez de ser suavizada manualmente.

## Checklist da fase

1. Eventos de duplicação/redução derivados programaticamente: **16**
2. Eventos de duplicação: **8**
3. Eventos de redução: **8**
4. Distância máxima para onset: **0 frames**
5. Correlação RMS × contagem: **0,992975**
6. Pico de contagem: **8 instâncias**, em torno de 36 s
7. Retorno final a 1 instância: **sim**, evento no frame 1743, aproximadamente 58,0963 s
8. Primeiro segundo com contagem 1: **sim**
9. Checklist de reveal visual: **N/A nesta fase**; nenhum evento foi aplicado ao vídeo
10. Artefato de composição: **N/A nesta fase**; apenas gráfico e dados de timing foram produzidos

A trilha, a curva RMS e os onsets ainda não foram aplicados ao vídeo. Aguarda-se aprovação da lista de timestamps antes da Fase 4.
