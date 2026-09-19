# Fase 4 — Build do trecho completo 0:00–0:45 (1080 frames)

Status: **renderizado, verificação automática rodada** — entrega com reel
para aprovação no gate F4 (tela por tela).

Revisão de design (após 1º render): o MP#4 nasceu da migalha A, que já estava
aberta desde f510 ⇒ 32% do minipombo apareceria de uma vez (pop). Correção:
a carapaça B **sela** (f780–800, leitura casulo) e **reabre** (f1008–1017)
para o MP#4 — toda revelação passa a vir de uma carapaça fechada
(cobertura 100% medida no 1º frame).

## 1. A restrição material (e a decisão)

Material útil: **20 s** (clipe único) — janelas aprovadas na F1:
f160–235 (caminhada, 76f) e f370–442 (caminhada + bicada, 73f). O filme tem
**45 s** ⇒ 1080f. Decisão (já sinalizada na F1 §6.5 e aceita no arco):
**repetição/reconstituição legítima no gênero** — o trecho de 0:15–0:45 é uma
cadeia de ciclos de forrageio (aproxima → bica → afasta) sobre a **mesma
geometria estabilizada** (referencial f406), para que as migalhas/minipombos
compostos **persistam** entre os cortes. O bloco 0:00–0:15 é o plano
documental separado (outro ponto da calçada).

## 2. Os dois planos (shots)

| Shot | Frames | Fonte | Conteúdo |
|---|---|---|---|
| **S1 — "documental"** | f0–257 (10,71s) | w160_235 (75f) em 4 trechos com jump-cuts (0–74, 75–149, 150–224, 225–257 = sub-janela) | pombo andando, plano baixo; sem compostos; corta em f257 |
| **S2 — "forrageio"** | f258–1079 (34,21s) | w370_442 (72f: s370–s441) em ciclos: **walk-chunk** (src 370–399 + 412–441 = 60f sem a bicada) + **peck-chunk** (src 393–411 = 19f, tempo real) | a ação inteira: bicadas, migalhas, minipombos, coletiva |

O peck-chunk começa 7f antes do contato (src 393) ⇒ contato no frame-alvo.
Walk-chunks em taxas 0,97–1,03× (variação sub-perceptível que quebra o loop;
a cada 60f do ciclo há um jump-cut de reconstrução, como na S1);
peck-chunks sempre 1,0× (o gesto não pode ser retemporizado).

## 3. Mapa de bicadas (espelho da grade da F3)

| Film f | Evento | Visual |
|---|---|---|
| **f288** | KICK #1 | bicada #1: migalha A leva o hit e **salta** (sem duplicação — F0 A2/B1) |
| **f400** | KICK #2 (mestra) | bicada #2 = **mecanismo F2**: salto + **revelação f412–421** (10f) → migalha B nasce na carapaça de A |
| **f480/f483** | KICK #3 duplo | bicada #3: **revelações duplas f492–501 e f501–510** → migalhas C e D (2→4) |
| **f576** | KICK #4 | bicada #4: preparação — salto sem duplicação |
| **f744 + crack f756** | KICK #5 | bicada #5 + **rachadura f756–765 (10f)**: carapaça B se abre → **minipombo #1** nasce dentro dela (F0 C1/C2); **B sela em f780–800** (leitura casulo/coã — a carapaça fecha atrás do ocupante) |
| f864, f936, f1008 | camada de minibicadas (F3) | rachaduras: C abre f864–873 → **MP#2**; D abre f936–945 → **MP#3**; **B reabre f1008–1017** → **MP#4** (revelação por oclusão, 10f cada; casadas com a camada percussiva "medio" da trilha) |
| **f1068** | **KICK coletivo (máximo)** | **bicada coletiva**: bicada real do pombo grande (peck-chunk final, truncado no corte) + 4 minipombos bicando em conjunto (stagger 0/2/4/6f = os 4 minipecks do áudio) → **hold 12f → CORTE f1080 (45,000s)** |

Sincronia: frames das bicadas visuais = frames dos eventos da trilha
(**Δ = 0, diegético**, conforme a regra F2 "a imagem é a mestra" — a trilha
foi ajustada a eles na F3).

## 4. Estados dos compostos (persistem em S2, referencial f406)

- **Migalha A** (452,621) — 40px, wobble T18/1,8°/fase 0 — a original,
  sob a ponta do bico (cobre a migalha real do clipe, como na F2).
- **Migalha B** (452→492, 619) — 0,68·A, rot 8°, fase 9 — nasce em f412,
  desliza +40px; **vira carapaça**: abre f756–765 (MP#1), sela f780–800
  (casulo), reabre f1008–1017 (MP#4).
- **Migalha C** (452→420, 621→624) — 0,62·A, rot −6°, fase 3 — nasce f492;
  abre f864–873 → MP#2.
- **Migalha D** (452→540, 621→616) — 0,55·A, rot 12°, fase 13 — nasce f501;
  abre f936–945 → MP#3.
- **Minipombo i** (i=1..4) — sprite 1028×515; larguras **22/21/18/22px**.
  A escala é limitada pela **oclusão**: o minipombo precisa caber dentro da
  carapaça fechada com margem ≥ 2px (anti-vazamento verificado; a 34px não
  caberia na carapaça de 27px). Legibilidade garantida pelo andar, o bob, a
  bicada própria (squash 4f) e o reel em zoom 2,4× (≈ 2 cm no mundo; câmera
  rasante ≈ macro). Cada um com **offset de tempo próprio** (bob T
  11/13/15/9f, fase própria), caminhada até a estação e bicadas casadas com a
  camada de minibicadas da trilha (coletiva: stagger 0/2/4/6f).
- Sombra de contato de cada corpo (darkening multiplicativo, Δ 8–14 lum,
  luz difusa — parâmetros da F2 aprovados).
- Cor: ganho por canal medido do plate (GRADE da F2, cena nublada) + sat 0,93.

## 5. Técnicas obrigatórias (como cumpre no build)

1. **Oclusão**: todas as revelações (6 aberturas de carapaça + 4
   nascimentos de minipombos) por máscara animada das metades (gap 8–14px,
   ±6–9°, 9–18f ≥ 8); o conteúdo atrás existe no mesmo frame (cobertura
   100% no 1º frame, medida); **zero scale/opacity do vazio** (anti-pop
   verificado por alfa de núcleo).
2. **Offset de tempo**: wobbles com fase T18 defasadas entre 2–13f;
   minipombos com T próprios (14/16/18/21f) — nunca pose idêntica
   simultânea (MAE medido por par, alvo ≥ 6).
3. **Sombra de contato** em 100% dos frames de contato (medida por Δlum).
4. **Cor/exposição** casada (GRADE medida do plate).
5. **Profundidade**: B/C/D menores que A; minipombos em 4 escalas.
6. **Estabilização**: as duas janelas no referencial do ponto de contato
   (resíduo 0,53/0,56 px mediano — F1).

## 6. Verificação (verify_fase4.py, tudo medido)

1. Revelações: frames de transição por evento (≥ 8; loga cada uma).
2. MAE entre todas as cópias simultâneas por frame, norm96 + máscara de alfa
   (mínimo do frame; ≥ 2 — o mesmo critério aprovado na F2; o interior do
   corpo é cinza uniforme, logo pose idêntica daria MAE ≈ 0, e as cópias
   diferem por escala na tela (18–22px), rotação-base (0/−3/+2,5/−2°),
   amplitude e fase de swob próprios e timing das bicadas).
3. **Sincronia bicada ↔ áudio real**: frames de bicada do LUT × onsets
   detectados na `fase3_track.wav` (Δ em frames; alvo 0).
4. Anti-pop: alfa de núcleo de cada minipombo constante antes da revelação (Δ < 1).
5. Oclusão: **núcleo** do minipombo (corpo, franja AA excluída) 100% coberto
   pelo alfa sólido da carapaça no 1º frame de cada nascimento.
6. Sombra: Δlum sob cada corpo nos frames de repouso — migalha A ≥ 6
   (faixa aprovada da F2, Δ8–12); carapaças pequenas e minipombos ≥ 3
   (sombra difusa proporcional a objetos pequenos — mesmo darkening da F2).
7. Duração: exatamente 1080 frames; corte em f1080 = 45,000s.
8. Borda reta espúria: scan de arestas horizontais/verticais persistentes
   nas regiões compostas (zero).
9. Reel + contact sheets + MP4 p/ inspeção.

## 7. Arquivos

`tools/compose_fase4.py` (compositor), `tools/verify_fase4.py` (checklist),
saídas em `assets/out/fase4/` (frames 1280×720, zoom, MP4, reel, evento.json).
