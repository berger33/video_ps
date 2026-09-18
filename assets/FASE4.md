# Fase 4 — sincronização sonora (128 BPM, loop exato)

Trilha **original**, sintetizada em Python (`numpy` + `scipy`), sem samples de
terceiros e sem licenças a atribuir. 75.000 s = 40 compassos a 128 BPM.

**Entrega:** `assets/audio/coo_score.wav` (48 kHz, 16-bit) · cópia FLAC
`coo_score.flac` · corte com áudio `assets/audio/fase4_sync.mp4`

## Grelha — a mesma do vídeo

Definida uma única vez em `scripts/score_grid.py` e importada pelos dois
lados (trilha e imagem), para que som e imagem não possam divergir:

```
128 BPM · 4/4 · BEAT = 0.46875 s · BAR = 1.875 s · 40 compassos = 75.000 s
```

| t (s) | compasso | N | leitura musical |
|-------|----------|---|-----------------|
| 0.0000 | 0 | 1 | só vento + pad, sem percussão |
| 15.0000 | 8 | 2 | **kick 4/4 entra** no degrau |
| 22.5000 | 12 | 4 | hats em 8as (ticks) |
| 30.0000 | 16 | 8 | baixo em movimento + ostinato de lead |
| 37.5000 | 20 | 16 | stab nos downbeats + hats em 16as |
| 45.0000 | 24 | 24 | clap nos beats 2 e 4 + lead agudo |
| 52.5000 | 28 | **32** | **clímax** — todas as camadas |
| 60.0000 | 32 | 16 | clap e lead agudo saem |
| 63.7500 | 34 | 8 | ostinato sai |
| 66.5625 | 35.5 | 4 | baixo volta a notas longas |
| 69.3750 | 37 | 2 | só kick, pad, vento |
| 72.1875 | 38.5 | 1 | silêncio rítmico: só pad e vento |

Todos os degraus caem na grelha (downbeats; o colapso corre em
meio-compasso). **Nada acontece "a meio".**

## Arranjo governado por N(t)

Cada camada tem um limiar de contagem — a música *é* a multiplicação:

| camada | entra com N ≥ | papel |
|--------|---------------|-------|
| vento + pad | 1 | leito contínuo (presente no frame 0) |
| kick | 2 | 4/4 seco, primeiro golpe no degrau |
| ticks (8as discretas) | — (compassos 4–36) | pulso sem bateria |
| hats 8as | 4 | |
| baixo | 4 | raiz do acorde (Am–F–C–G) |
| hats abertos | 8 | |
| baixo em movimento / lead | 8 | ostinato de 16as |
| stab | 16 | acorde curto no downbeat |
| hats 16as | 16 | |
| clap + lead agudo | 24 | clímax rítmico |

No colapso a música **desce a mesma escada em espelho** (24 → 16 → 8 → 4 → 2 → 1),
porque é a mesma função a descer. Bass/harmonia/lead levam *ducking* do kick
(sidechain) para não ensopar.

## Picos de multiplicação = eventos sonoros

Um **riser** por degrau, a resolver exactamente no beat: no crescimento,
impacto de *sub-drop* + transiente; no colapso, varredura descendente de
sucção + whoosh. Em nenhum instante a textura é constante do início ao fim.

## Loop

O buffer é periódico **por construção**: todos os eventos são escritos com
índice circular (`_add` dá a volta ao buffer) e a reverb é convolução
circular (FFT de comprimento N). O rabo do compasso 40 desagua no compasso
1 sem corte nem clique.

## Checklist de autoverificação (Fase 4)

Medições em `scripts/analyze_score.py`, saída `assets/audio/fase4_analysis.json`
e figura `assets/audio/fase4_score_qa.png`:

- **BPM**: detectado **127.84** (librosa) vs alvo 128 → erro −0.16 BPM.
- **Picos ≠ constante**: força de onset nos degraus = **14,0×** a linha de
  base (mediana); todos acima de 6×.
- **Som × imagem**: correlação entre RMS por compasso e N(t) = **+0.71**;
  cada camada tem limiar de N (tabela acima), logo a textura sobe e desce
  com a contagem de cópias.
- **Alinhamento**: desvio máximo de um pico ao beat detectado = **0,68 frame**
  (22 ms) — dentro de um frame de vídeo.
- **Loop**: |x[0] − x[−1]| = **0.040**, abaixo da inclinação local da forma
  de onda (0.137) → costura limpa.
- **Nível**: −15,1 LUFS integrado, pico −2,0 dBFS no WAV; no ficheiro
  final entregue, true peak −1,5 dBFS e LRA 6,2 LU.

```
.venv/bin/python scripts/compose_score.py     # sintetiza WAV + FLAC
.venv/bin/python scripts/analyze_score.py     # mede e reporta (checklist)
```
