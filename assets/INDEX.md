# Fase 1 — índice de assets

**Peça:** COO · **sujeito:** pombo-das-rochas (variação A, clássica)
**Modelo de geração:** API de imagem da sessão Arena (text-to-image para 4 variações;
img2img a partir de `var_a_classic.jpg` para as poses). O checkpoint interno não é
exposto pela ferramenta — não inventar nome de modelo.

## Variações visuais (mín. 4)

| id | ficheiro | escolha |
|----|----------|---------|
| A clássica | `assets/raw/var_a_classic.jpg` | **HERÓI** — silhueta limpa, barras negras, iridescência, chroma uniforme |
| B checker | `assets/raw/var_b_checker.jpg` | reserva (padrão manchado, enfrenta o lado oposto) |
| C pale | `assets/raw/var_c_pale.jpg` | reserva (cinza-prata, menos contraste) |
| D dark | `assets/raw/var_d_dark.jpg` | reserva (melanística; chroma com gradiente, pior para key) |

Clipes e recortes de produção usam **apenas A** + poses img2img derivadas de A.

## Stills isolados (RGBA)

| pose | png | pivot pés (x,y) | fill ratio bbox |
|------|-----|-----------------|-----------------|
| `idle` | `assets/isolated/idle.png` | 316.6, 645.0 | 0.295 |
| `peck` | `assets/isolated/peck.png` | 626.1, 629.0 | 0.321 |
| `coo` | `assets/isolated/coo.png` | 284.7, 654.0 | 0.339 |
| `fluff` | `assets/isolated/fluff.png` | 429.4, 635.0 | 0.501 |
| `walk_a` | `assets/isolated/walk_a.png` | 394.1, 633.0 | 0.270 |
| `walk_b` | `assets/isolated/walk_b.png` | 363.9, 608.0 | 0.289 |
| `head_turn` | `assets/isolated/head_turn.png` | 319.5, 646.0 | 0.306 |

Fill ratio ≪ 1.0 = silhueta orgânica (não é um retângulo colado).

## Clipes 4.0 s · 30 fps · 1280×720 · loop

Fundo neutro `#3A3D40`. Câmera fixa. Uma instância do sujeito.
Animação: puppet cut-out (rotação/escala em torno dos pés; uma pose visível de cada vez).

| ficheiro | movimento |
|----------|-----------|
| `assets/clips/idle_bob.mp4` · `idle_bob.gif` | idle + head-bob (pivô nos pés) |
| `assets/clips/walk_in_place.mp4` · `walk_in_place.gif` | passo no sítio idle↔walk_a↔walk_b |
| `assets/clips/peck.mp4` · `peck.gif` | bicar o chão, 2x / 4s |
| `assets/clips/coo.mp4` · `coo.gif` | garganta inflada (display) |
| `assets/clips/fluff.mp4` · `fluff.gif` | eriçar / abrir a asa |
| `assets/clips/head_turn.mp4` · `head_turn.gif` | virar a cabeça à câmara |
| `assets/clips/weight_shift.mp4` · `weight_shift.gif` | transferência de peso, 1 ciclo / 4s |
| `assets/clips/strut.mp4` · `strut.gif` | passo + bob mais amplo |

## Preview

- grelha de todos os loops: `assets/previews/fase1_mosaic.mp4` / `.gif`
- contact sheet dos recortes: `assets/previews/fase1_stills.jpg`
- picos de pose + loop first/last: `assets/previews/fase1_pose_peaks.jpg`

## Regenerar

```
.venv/bin/python scripts/prepare_assets.py
```

## Checklist de autoverificação

- Instâncias no frame final de cada clipe: **1 em todos** (esperado = 1 nesta fase; a multiplicação é a Fase 2).
- Primeiro e último frame compatíveis para loop: **sim** (MAE médio last↔first = 0.61; MAE médio frame0↔frame1 = 0.59; salto de loop ≤ ~1 frame de movimento).
- Artefacto de bloco/retângulo estático: **não**.
- Picos de distorção/multiplicação: **N/A** — Fase 1 é o sujeito isolado, sem proliferação. O head-bob / peck / fluff têm picos de pose, não de contagem.

Relatório bruto: `assets/previews/fase1_checklist.json`
