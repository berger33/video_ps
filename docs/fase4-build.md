# Fase 4 — Build do trecho completo 0:00–0:45

Status: **renderizado, verify 9/9** — aguardando gate (aprovação humana).

## 1. Estrutura (1080 frames @ 24fps = 45,000s)

| Trecho | Frames | Conteúdo |
|---|---|---|
| S1 | 0–257 (0:00–0:10,7) | Plano documental: caminhada real (janela `w160_235` = s160–s234, 75f) em 5 blocos de fases distintas (cortes f54/108/141/162/216 — polimento da F5), zero compostos |
| S2 | 258–1079 (0:10,7–0:45) | Forrageio contínuo na geometria f406: ciclos de caminhada (src 370–399 + 412–441 = 60f, taxas 0,96–1,03 por ciclo) com **6 bicadas reais** cravadas na grade da trilha |

A regra de sincronia (imagem manda, áudio acompanha; aprovada na F3) vale
para os 6 contatos: **f288, f400, f480 (duplo 480/483), f576, f744, f1068** —
cada um é o frame de contato da janela real (src f400) reposicionada no tempo.
O drag de 4f do KICK#2 (aprovado) permanece: bicada visual em f400, beat
musical em f396.

## 2. Corte da janela de forrageio

Cada bicada = pedaço de 19f da janela (src 393–411, contato no índice 7),
cravado no alvo; o resto é preenchido pelo ciclo de caminhada de 60f
(abordada + saída, sem a bicada) com taxa por ciclo (1,0 / 0,97 / 1,03 /
0,98 / 1,02 / 0,96) para disfarçar o loop. O clique duplo f480/f483 da
trilha = uma bicada visual + **salto duplo da migalha A** (arco reinicia em
483 — o tintimete do impact), documentado como desvio aceito.

## 3. Cadeia de duplicação (mecanismo F2 aprovado, generalizado)

| Evento | Frames | Leitura |
|---|---|---|
| Kick #1 (f288) | 288–299 | Bicada real; migalha A **salta** (14px), não duplica (A2 do roteiro) |
| Kick #2 (f400) | 400–421 | A salta, **racha** (412–421, gap 8px/±6°) e **B nasce por dentro** (slide +40px) — mecanismo F2 |
| Kick #3 (f480/483) | 480–510 | A racha mais (gap 12px/±8°): **C nasce** (492–501, slide −32px) e **D nasce** (501–510, slide +88px) → 2→4 |
| Kick #4 (f576) | 576–587 | Bicada de preparação; A salta, nada nasce |
| Kick #5 (f744) + crack (f756) | 744–765 | **B vira carapaça**: abre (756–765) e **minipombo #1 nasce por dentro** (22px) |
| Casulo | 780–800 | A carapaça B **sela** (gap→0) atrás do filhote que sai caminhando |
| Mini-pecks | 864 / 936 | C abre → **MP#2** (21px); D abre → **MP#3** (18px) |
| Reabertura | 1008–1017 | B **reabre** → **MP#4** (22px) — a carapaça que gera, leitura aprovada |
| Coletiva (f1068) | 1068–1079 | Bicada real do pombo (no lugar de A, que quica) + **4 minipombos bicam em stagger 0/2/4/6f** = os 4 minipecks da trilha; hold 12f; corte seco em 45,000s |

Bicadas dos minipombos ao longo de C (900, 948, 972, 990, 1014, 1032,
1044) cavalgam a camada de mini-pecks da trilha (grade 12f→6f→3f).

## 4. Regra anti-pop (zero escala/opacidade do vazio)

- Toda revelação é **oclusão**: o conteúdo é renderizado desde antes,
  100% coberto pela carapaça fechada, e aparece pela abertura animada.
- A carapaça fechada é **opaca por construção**: metades com feather
  unilateral (`cut_halves_opaco`) — o fecho reconstrói a silhueta sem
  emenda translúcida.
- Minipombo **não sobe de baixo** (vazaria além da silhueta da carapaça):
  fica na posição final, oculto, e a abertura o revela; sai **caminhando**
  por trás da carapaça (mesma mecânica do slide de B na F2).
- Revelações: 10 eventos, 9–18f cada (≥8 exigido).

## 5. Minipombos (tamanho e variação)

Larguras 22/21/18/22px (carapaças B/C/D/B têm 26,4/24,8/22,0/26,4px —
margem ≥2px). Limite de legibilidade imposto pela oclusão; o zoom do reel
(2,4×) mostra o detalhe. Cada minipombo tem **período, amplitude, fase e
rotação base próprios** (regra do offset de tempo — nunca a mesma pose do
irmão no mesmo frame; verificado por MAE par-a-par).

## 6. Verificação (tools/verify_fase4.py — medidas reais)

1. Estrutura: 1080 frames exatos, S1/S2, corte 1080 ✓
2. Revelações ≥8f (10 eventos) ✓
3. MAE mínimo entre cópias simultâneas ≥2 (cópia congelada ≈0) ✓
4. Sync: 6 bicadas vs **onsets reais** do `fase3_track.wav`, Δ≤1f ✓
5. Anti-pop: Δ alfa-núcleo <1 nos frames ainda cobertos ✓
6. Oclusão: núcleo do bird 100% atrás da carapaça fechada em r0 ✓
7. Sombra de contato: Δlum mediano — A≥6 (faixa aprovada), demais ≥3
   (sombra difusa proporcional; mínimos reportados pois o baseline do
   plate varia com o frame-fonte) ✓
8. Zero retas estáticas espúrias (composto vs plate) ✓
9. Artefatos: mp4s, reel, evento.json, layers ✓

## 7. Decisões desta reconstrução (sandbox resetado; commit 17aa59f perdido)

- Todo o código/docs da F4 foi reescrito a partir do gate da F3 (2988df4);
  sprites re-gerados (mesmos prompts → novos canvases: migalha 379×268,
  minipombo 966×487) e tune de oclusão refeito (0,75→0,66 p/ cobertura 1,0
  contra o frange AA).
- Diferença vs. o take perdido: a subida do minipombo de dentro da
  carapaça foi **removida** (vazava além da silhueta); a revelação é
  100% pela abertura — mais fiel à regra anti-pop.
