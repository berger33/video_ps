# FASE 1 — Aquisição e preparação de assets

Status: **aguardando aprovação.** Todos os números abaixo foram medidos neste ambiente
(2 vCPU / 3 GB / sem GPU), não estimados.

---

## 1. O que chegou (commit `88cdf7d` "pidgeot videos")

| arquivo | duração | frames | resolução | fps | áudio |
|---|---|---|---|---|---|
| `crie_de_outro_video_de_pombo.mp4` | 20,01 s | 480 | 1280×720 | 24 | AAC 48 kHz estéreo |
| `consegue_criar_um_gid_deste_po.mp4` | 10,01 s | 240 | 1280×720 | 24 | AAC 48 kHz estéreo |
| `Gemini_Generated_Image_uoppefuoppefuopp.jpg` | — | — | 1574×880 | — | — pose parada |
| `Gemini_Generated_Image_535bze535bze535b.jpg` | — | — | 1574×880 | — | — meio-passo |

### 1.1 Achado 1 — os dois vídeos são o mesmo material

`consegue_criar_um_gid_deste_po.mp4` **é exatamente os primeiros 240 frames** de
`crie_de_outro_video_de_pombo.mp4`. Verificação: para 30 amostras de B (a cada 8 frames),
o melhor alinhamento em A foi sempre `j = i` (offset constante 0), com MAE ≈ 1,5 (só
recompressão). **Material único = 20 s.**

### 1.2 Achado 2 — a câmera panorâmica e o que isso custa

Sem stutter (0 pares consecutivos idênticos) e sem loop interno (melhor match em lag > 48
frames tem MAE ≥ 18) — ou seja, movimento contínuo e genuíno, bom para interpolação.

Mas a câmera **viaja**: translacção acumulada de **485 px** (de 1280) no clipe, e **6 px/frame**
nas janelas rápidas. Uma translação global **não** alinha o quadro (medido: alinhar piorava o
MAE). A causa é paralaxe: chão próximo e fundo distante se movem diferente. Solução
implementada: **campo de movimento por blocos + ajuste polinomial robusto**
(`tools/motion.py`) — residual mediano 0,2–0,7 px nas janelas boas.

### 1.3 Achado 3 — qualidade por região do clipe (decisivo)

Medindo alinhamento **e** nitidez (variância do Laplaciano no chão):

| região | pan | nitidez | alinhamento | usa para ciclo de caminhada |
|---|---|---|---|---|
| f0–90 | 6 px/f | baixa | fraco/ruim | não |
| **f160–235** | **1,6 px/f** | **alta (304)** | **ótimo** | **sim** |
| f240–280 | 6,3 px/f | baixa | ruim | não |
| f290–340 | ~3 px/f | média | ok | parcial |
| **f370–415** | **2,6 px/f** | média (71) | **ótimo (resid 0,1–0,5 px)** | **sim — inclui a bicada** |
| f420–455 | 6 px/f | baixa | ruim | não |

Nas janelas rápidas o pombo fica com **motion blur** — não é material aproveitável sem
inventar detalhe.

### 1.4 Achado 4 — a bicada existe e é limpa

No material **real** (não gerado): a cabeça começa a descer em **f393**, o bico toca o chão em
**f399–f401**, e a recuperação termina em **f406** — gesto de ~14 frames, com o corpo inclinado
para frente, exatamente a leitura de forrageio. É o núcleo do trecho: **bicada #1 = f400**.

---

## 2. Pivotamento técnico (e por quê)

**Tentativa 1 — matting por rede neural (rembg/U²-Net, SAM).** Inviável neste sandbox: GitHub
releases, `objects.githubusercontent`, HuggingFace, `download.pytorch.org`,
`storage.googleapis` e jsDelivr estão **bloqueados** (só PyPI e codeload respondem). Não há
caminho para baixar pesos. O wheel do MediaPipe não traz pesos e é segmentação de **pessoas**.

**Tentativa 2 — matting clássico por plate.** Implementado e medido (`tools/pigeon_matte.py`):
plate por doação espaço-temporal, separação de sombra por correlação de gradiente, trimap +
closed-form matting. Resultado nos frames da bicada: **máscara correta**, mas a borda ainda
suja (máx ≈ 41 px de erro de contorno — medido comparando áreas quadro a quadro). Para
composição de qualidade seria preciso matte limpo **frame a frame**, o que não fecha neste
hardware nem neste material de 720p com paralaxe no fundo.

**Conclusão honesta:** o clipe filmado serve como **plate e dublê**, não como fonte de matte
perfeito. Isso leva ao desenho que o roteiro realmente pede:

> **No trecho 0:00–0:45 quem duplica é a MIGALHA, não o pombo.** O pombo real é a âncora
> documental (piso 0:00–0:15 e ação de bicar). A migalha e o minipombo — os elementos cujo alfa
> precisa ser impecável — **não precisam sair de vídeo**: são assets sintetizados com
> fundo controlado e alpha limpo por construção.

Isso também **resolve** a técnica obrigatória nº 1 de forma verificável: matting por frame onde
o material permite (pombo) e **alpha exato por key + refinamento** onde o alfa é crítico
(migalha, minipombo).

---

## 3. Assets produzidos e medidos

### 3.1 Sprites (alpha limpo, verificado)

| asset | dimensão | px sólidos | borda suave | cor média BGR | sombra |
|---|---|---|---|---|---|
| `migalha_rgba.png` | 385×350 | 87.176 | 4.850 (5,6%) | 159,6 / 189,4 / 208,6 | sintetizada em composição |
| `minipombo_rgba.png` | 571×574 | 143.296 | 8.720 (6,1%) | 134,2 / 137,5 / 143,4 | idem |

A sombra difusa do estúdio foi **removida do alfa de propósito** (técnica nº 5: sombra é
sintetizada na cena, com direção/penumbra medidas da luz do plate).

### 3.2 Janela da bicada estabilizada — `assets/plates/w370_442/`

- 72 frames (f370–442) lidos em 1280×720 e estabilizados no referencial de **f406**.
- Residual do campo de movimento: **mediano 0,53 px**, p90 16,4 px (1 falha isolada).
- `preview_estab_370_442.mp4` — 72 frames, 1:1 do recorte de ação, para você conferir se o
  chão "para de derrapar" (critério da técnica nº 2).
- `plate_clean.png` + `plate_confianca.png`: tentativa de plate sem o pombo. **Ainda contém
  fantasma** (energia de borda 5,18 na região do pombo vs 1,81 no chão limpo → 2,9×).

### 3.3 Janela de caminhada — f160–235

Aprovada por medição e por inspeção: pan lento, nitidez alta, passos legíveis e o pombo
girando/andando na direção da câmera. É o candidato para o bloco 0:00–0:15.

### 3.4 Áudio

`assets/audio/A_ambiente.wav` e `B_ambiente.wav` (48 kHz mono, 20,01 s / 10,01 s). RMS ≈ 0,061
e 0,064 — existe cama de rua real, matéria-prima para a Fase 3 (bicada = kick etc.).

---

## 4. Soluções de engenharia que ficaram no repositório

| arquivo | função |
|---|---|
| `tools/setup_env.sh` | ambiente idempotente (venv + ffmpeg estático via wheel, pois `apt` está bloqueado) |
| `tools/motion.py` | campo de movimento por blocos + polinômio robusto (paralaxe) |
| `tools/pigeon_matte.py` | matting do pombo: campo de movimento, máscara de atividade, plate por doação, separação de sombra por gradiente, trimap + closed-form |
| `tools/build_plate.py` | estabilização de janela + plate limpo + confiabilidade |
| `tools/extract_sprites.py` | key de fundo branco com núcleo por luminância/saturação + refinamento de borda |
| `tools/analyze_clips.py`, `analyze_redundancy.py`, `analyze_pecking.py` | medições que fundamentam as decisões acima |

---

## 5. Checklist de autoverificação — estado atual (parcial; itens da Fase 1)

| item | medida | critério | estado |
|---|---|---|---|
| Frames por evento de revelação | não há revelação nesta fase | ≥ 8 | — (Fase 2) |
| Cópias simultâneas com pose idêntica | não há cópias nesta fase | MAE ≥ 2 | — (Fase 2) |
| Distância bicada visual ↔ som | bicada medida em **f400** | Δ = 0 (diegético) | ✅ evento localizado |
| Artefato de bloco/retângulo mal colado | nenhum elemento inserido ainda | zero | — (Fase 2) |
| Estabilização (téc. nº 2) | residual **0,53 px** mediano | ≤ 1 px | ✅ |
| Matte do pombo | erro de contorno máx **≈ 41 px** (720p) | 0 | ❌ **não aprovado** |
| Matte da migalha/minipombo | borda suave 5,6% / 6,1% com alfa contínuo | limpo | ✅ |
| Plate limpo sem pombo | 2,9× de energia de borda na área do pombo | ≈ 1× | ❌ **não aprovado** |

---

## 6. O que eu preciso de você para fechar a FASE 1

1. **Aprovação dos assets**: sprites (migalha/minipombo) e a janela da bicada estabilizada.
2. **Plate/plano de fundo**: o fantasma do plate importa para as oclusões. Duas saídas —
   (a) eu inpainto a área do pombo por **clonagem de chão de outro frame** (viável, mas o chão
   é laje grande e uniforme: erro visível pequeno), ou (b) você gera **um still limpo da mesma
   calçada** (um frame sem o pombo, mesmo enquadramento) e eu uso como plate oficial.
3. **Matte do pombo grande**: os minipombos são sprites; o pombo grande só precisa de matte se
   eu for **recompor sobre outro fundo**. Se ele ficar sobre o próprio material (recomposição
   com plate local), o problema do matte desaparece na prática. Confirma esse caminho?
4. **Cenário**: calçada do Centro de SP (pedra portuguesa) continua pendente. O material é
   parque com lajes de pedra, como as suas referências.
5. **Confirmação do plano de corte**: janelas utilizáveis são f160–235 (caminhada) e
   f370–442 (caminhada + bicada). Se você quiser 45 s contínuos desse material, será preciso
   repetição/reconstituição — o que é legítimo no gênero, mas muda o desenho da montagem.
