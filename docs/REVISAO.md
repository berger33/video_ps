# Revisão de conformidade — o resultado atende ao pedido?

Revisão feita antes de continuar o pipeline: o trabalho parou na Fase 3 (o
README a marcava "em revisão"), com a Fase 4 bloqueada. Abaixo, cada exigência
do pedido original confrontada com o que existe no repositório, com a
evidência e — onde havia desvio — a correção aplicada.

## 1. O contrato que define o estilo

| Exigência | Situação | Evidência |
|-----------|----------|-----------|
| O elemento **duplica/prolifera dentro do próprio frame** | **atende** | N(t): 1 → 2 → 4 → 8 → 16 → 24 → **32** → 16 → 8 → 4 → 2 → 1. 32 cópias simultâneas em t=52,5 s |
| Várias cópias **visíveis simultaneamente** | **atende** | contagem por compositor reportada por degrau em `fase5_qa.json`; verificação visual na folha `fase5_timeline.jpg` |
| Feito por **composição** (recorte colado), não por filtro | **atende** | cada instância é um PNG RGBA recortado, escalado/rodado individualmente e colado (`blit_bgra`). Não existe nenhum filtro aplicado ao clipe inteiro |
| Deformação crescente além da contagem | **atende** | cada cópia tem Δposição/Δescala/Δrotação, head-bob e deriva próprios; as poses (walk/peck/coo/fluff/head_turn) entram por bloco; no colapso há sucção (contracção para o centro) |
| **Loop**: primeiro e último frame compatíveis | **atende** | MAE(primeiro, último) = **0,96** contra 1,63 de um frame adjacente e 2,96 de meio ciclo de head-bob — a costura é *mais suave* que uma transição normal da cena, e é exacta por construção (períodos divisores de 75 s) |

## 2. Anti-padrões (rejeição automática)

| Anti-padrão | Presente? | Nota |
|-------------|-----------|------|
| Filtro glitch/VHS/aberração cromática/cor vintage sobre o clipe inteiro | **não** | não há aberração cromática, VHS, vinheta vintage nem LUT "surreal". Há curva S leve, grão fino, bloom das altas luzes e jitter de ±1 px — todos com **gate por N(t)**: em t=0 e t=75 s (N=1) o efeito é ≈0 |
| Apenas 1–2 instâncias do início ao fim | **não** | 1–2 cópias só entre 0–22,5 s e na cauda (72,2–75 s), como o arco aprovado pede |
| Padrões constantes/mecânicos sem relação com música/narrativa | **não** | N(t) e a trilha partilham a mesma grelha (`score_grid.py`); arranjo musical com limiares de N; onsets 10–17× a linha de base em cada degrau |
| Blocos/retângulos congelados ou mal colados | **não** | fill ratio dos recortes 0,27–0,50 (silhueta orgânica); máscara com pena de 0,6 px; sombras em mapa acumulado. Verificado por inspecção a 100% em 14 instantes |

## 3. Fases

| Fase | Exigência | Situação |
|------|-----------|----------|
| 0 | 1 página: elemento, arco 60–90 s, BPM/estilo, paleta, 3 vídeos do Cyriak | **atende** — `docs/FASE0_BRIEF.md` (75 s, 128 BPM, paleta com hex, *cows & cows & cows* / *Baaa* / *HONK*) |
| 1 | 5–10 clipes de 3–6 s, câmara fixa, fundo neutro, loop; ≥4 variações com modelo indicado | **atende** — 8 clipes de 4,0 s a 30 fps; 4 variações A–D; índice em `assets/INDEX.md`. Ressalva honesta: as imagens vieram da API de imagem da sessão Arena e o *checkpoint* exacto **não** é exposto pela ferramenta — está registado assim no índice, em vez de inventar um nome de modelo |
| 2 | Protótipo: isolar, recortar, colar 2→4→8+ ao longo de 5–10 s; frame final ≥8 cópias | **atende** — 10 s, 1→12 cópias (gate ≥8), `fase2_checklist.json` |
| 3 | Escalar, loop perfeito, 60–90 s sem áudio | **atende** — 75 s mudas, loop (MAE 1,54). Script, corte, gif, first/last e checklist entregues em `assets/FASE3.md` |
| 4 | Trilha electrónica, extrair batidas (librosa), picos de multiplicação **nos beats**, não constante | **atende** — trilha original 128 BPM; librosa mede 127,84 BPM; 11/11 degraus na grelha; picos = sub-drops/risers a resolver no beat; `fase4_analysis.json` |
| 5 | Ajustes finos de timing, cor, textura; MP4 final 1080p | **atende** — `assets/final/coo_final_1080p.mp4` |

## 4. Desvios encontrados na revisão — e o que foi corrigido

Revisão da Fase 3 antes de continuar (o corte mudo estava bom no essencial,
a técnica estava correcta e sem artefactos):

1. **Colapso fora da grelha musical.** Os degraus de descida eram 65 / 69 /
   72 / 73,5 s — fora da grelha de compassos da trilha. *Corrigido na Fase 5:*
   descida em 63,75 / 66,5625 / 69,375 / 72,1875 s (compassos 34 / 35,5 / 37 /
   38,5), meio-compasso a meio-compasso, a espelhar subida.
2. **Cópias empilhadas no clímax.** Em t=53 s havia pares a **4,5 px** de
   distância (três aves no mesmo ponto) — lê-se como borrão, não como
   multiplicação. *Corrigido:* passo de *packing* determinístico (repulsão com
   raio por escala + coerência de plano). Distância mínima passou a ≥47 px,
   com raio de exclusão ~90 px para as aves do plano médio.
3. **Aves a flutuar.** A elipse antiga punha aves acima da linha do telhado,
   sem apoio no chão. *Corrigido:* cada plano tem uma faixa de `y` no chão do
   prato, com escala coerente com a profundidade (0,15 no fundo → 0,84 na
   frente) e sombra de contacto por ave.
4. **Leitura da densidade.** Em N=16 a composição somava um plano distante mas
   o quadro continuava a ler-se como "um anel". *Corrigido:* a ordem de
   revelação é dramática (plano principal → fundo → intermédio → primeiro
   plano), cada degrau é uma onda (0,03 s entre aves, do centro para fora) e o
   pico é diferente em espécie, não só em número.
5. **Grão a estragar a costura.** O jitter de ±1 px não era periódico: o
   primeiro e o último frame recebiam offsets opostos (salto de 2 px, MAE
   8,2). *Corrigido:* jitter periódico em 3 s (25 ciclos exactos) — MAE do
   loop caiu para 0,96.

## 5. Limites honestos desta entrega

- **Resolução do recorte.** O recorte do herói tem 674 px de largura; no
  clímax o primeiríssimo plano é ampliado ~2,2×. Com *unsharp* suave o
  resultado aguenta 1080p, mas se quiser o plano de frente absolutamente
  nítido, o caminho é re-gerar os assets da Fase 1 em 2× e voltar a correr
  este render — o pipeline já está parametrizado para isso.
- **Porta dos assets no fundo.** As aves são geradas a partir de imagens
  sintéticas; a 0,15 de escala (7 aves pequenas no fundo) a leitura é "bando
  ao longe", não "pombo idêntico" — é o que a profundidade pede.
- **Áudio sintetizado.** A trilha é original (numpy/scipy, sem samples de
  terceiros) — não há risco de licença, mas é um instrumental de sintetizador,
  não uma produção de estúdio. Trocar por uma faixa própria é uma linha:
  `python scripts/render_final.py` usa o WAV que estiver em `assets/audio/`.
- **Duração.** 75 s, dentro dos 60–90 s pedidos, e exactamente 40 compassos a
  128 BPM — o que permite o loop fechar em música *e* imagem.
