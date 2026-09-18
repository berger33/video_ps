# Fase 5 — polimento e exportação final

**Entrega:** `assets/final/coo_final_1080p.mp4` — 1920×1080, 30 fps, 75 s,
com trilha. 42,6 MB (H.264 High, CRF 22, AAC 256 kbps, faststart).

Previews no mesmo diretório:

| ficheiro | conteúdo |
|----------|----------|
| `coo_preview_climax.gif` | clímax (t=46–54), 480 px, 10 fps |
| `coo_preview_loop.gif` | abertura (t=0–8) — serve para julgar a costura |
| `coo_preview_climax_480p.mp4` | 10 s **com áudio** (t=46–56) |
| `coo_preview_abertura_480p.mp4` | 12 s **com áudio** (t=0–12) |
| `coo_poster.jpg`, `coo_poster_abertura.jpg` | stills 1080p |
| `fase5_timeline.jpg` | 14 instantes com N anotado |
| `fase5_first.jpg`, `fase5_last.jpg`, `fase5_loop_compare.jpg` | loop |

## O que o polimento mudou (sem sair do contrato)

A multiplicação continua a ser **colagem de recortes**; nada abaixo é filtro
aplicado ao clipe inteiro. Cada item tem um *gate* por N(t), pelo que o efeito
é ≈0 quando o pombo está sozinho — nos dois extremos do loop incluídos.

1. **Profundidade por planos.** Quatro planos (principal, distante,
   intermédio, primeiro plano), todos com o pé dentro da faixa de chão do
   prato (`y` 526–1075) e escala coerente com a profundidade (0,15 no fundo →
   0,84 na frente). O plano distante tem névoa atmosférica e metade das aves
   espelhadas.
2. **Packing determinístico.** Repulsão entre cópias até o raio de exclusão
   (0,46 × 430 × escala + 26 px), com atracção para o `y` do plano. Distância
   mínima entre aves no clímax: **≥47 px** (era **4,5 px** no corte mudo).
3. **Onda de nascimento.** Cada degrau revela as cópias em onda (0,03 s entre
   aves, do centro para fora) com pop de escala e fade de luminância: o pico
   dura ~0,4 s, não é um corte de montagem.
4. **Micro-movimento com períodos divisores de 75 s** — deriva 12,5 s (6×),
   giro suave 18,75 s (4×), head-bob 0,75 s (100×), cintilação 0,5 s (150×),
   grão 15 frames (150×), jitter ±1 px com período 3 s (25×). O quadro final
   coincide com o inicial **por construção**.
5. **Grounding.** Mapa de sombra acumulada (as cópias somam massa) + ponto de
   contacto por ave, ambos a crescer com N. Nenhuma ave flutua.
6. **Post com gate de N**: curva S leve, bloom das altas luzes, grão fino e
   jitter de ±1 px. Sem VHS, sem aberração cromática, sem vinheta vintage,
   sem marca de água — o pedido não definiu assinatura e inventar uma seria
   decoração por cima do trabalho. Se quiser crédito/assinatura no canto, é
   um `--watermark` de 10 linhas.
7. **Timing na grelha musical.** O colapso passou de 65 / 69 / 72 / 73,5 s
   (Fase 3, fora da grelha) para **63,75 / 66,5625 / 69,375 / 72,1875 s** —
   compassos 34 / 35,5 / 37 / 38,5, a espelhar a subida. Som e imagem partilham
   `scripts/score_grid.py`.
8. **Encode de entrega**: `libx264 -preset slow -crf 22`, `keyint=250`,
   `scenecut=0`, faststart, AAC 256k. `--crf 16` fica disponível para master
   intermédio (63 MB).

## Checklist de autoverificação (Fase 5)

Medições em `scripts/render_final.py --verify` → `assets/final/fase5_qa.json`.

| pergunta do checklist | resposta |
|-----------------------|----------|
| Quantas instâncias distintas no frame final do clipe? | **1** no último frame (é o fecho do loop), **32 no pico** (t=52,5 s), com a contagem a subir por degraus: 1 → 2 → 4 → 8 → 16 → 24 → 32 e a descer 16 → 8 → 4 → 2 → 1 |
| First e last são compatíveis para loop? | **sim** — MAE(first,last) = **0,96**, contra 1,63 de um frame adjacente (1/30 s) e 2,96 de meio ciclo de head-bob. No ficheiro final codificado, MAE = **1,61** |
| Há artefacto de bloco/retângulo estático? | **não** — fill ratio dos recortes 0,27–0,50; máscara com pena de 0,6 px; inspecção a 100% em 14 instantes (`fase5_timeline.jpg`) |
| A multiplicação tem picos identificáveis ou é constante? | **picos** — 12 degraus na grelha de compassos; onsets da trilha 10–17× a linha de base em cada degrau, desvio máx. 0,68 frame do beat |

Verificações extra desta fase: **0** aves acima da linha do telhado (coerência
de plano), **0** pares acima do raio de exclusão no pico, LUFS integrado
**−15,1** (true peak −1,5 dBFS, LRA 6,2 LU).

```
.venv/bin/python scripts/render_final.py --verify     # só QA (3 s)
.venv/bin/python scripts/render_final.py              # render + export 1080p
```
