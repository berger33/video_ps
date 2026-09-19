# FASE 2 — Protótipo do mecanismo (1 bicada → 1 duplicação de migalha)

Status: **entregue — aguardando aprovação.** Critério: reveal ≥ 8 frames, sem
pose duplicada idêntica simultânea, sombra e cor coerentes. "Pop" do vazio
reprova automaticamente. Todos os números abaixo foram medidos pelo
`tools/verify_fase2.py`, não estimados.

---

## 1. O que o protótipo faz

Um único evento, na janela da bicada estabilizada (`assets/plates/w370_442`,
referencial f406, 24 fps). A migalha **A** já está no chão, sob a ponta do
bico. A cadeia causal, frame a frame:

| frame | evento |
|---|---|
| f400 | **bicada visual** (bico toca o chão, vídeo real) → migalha A leva o hit (squash) |
| f400–409 | salto curto de A (arco 14 px, apex f404) |
| f409 | pouso + squash de impacto + quique de 4 px até f412 |
| **f412–421** | **OCLUSÃO**: A racha (duas metades se abrem 8 px, rot ±6° em torno da ancora no chão) e a migalha **B** emerge de **dentro** de A por trás das metades, deslizando 40 px para a direita. **Reveal = 10 frames** |
| f421–441 | as duas migalhas em repouso, cada uma com wobble em fase própria, sombra de contato própria |

### Decisão de design: a migalha é a CARAPAÇA

No arco, a duplicação acontece por oclusão — a migalha "abre" e revela o que
está **atrás** de uma máscara animada. Implementei a leitura mais forte: **B
nasce dentro de A** (A é a carapaça de B). Consequências práticas que
resolvei:

- B **não pode existir visível** antes da abertura → B vive 100% ocluída por A
  do início do clipe até f412. Verificado: cobertura mínima = **1.0** em 43
  frames medidos (qualquer vazamento < 1 px seria reprovado).
- Enquanto A salta (f400–409), **B sobe junto** (mesma `dy`). Se B ficasse
  parada no chão, A subindo deixaria B exposta no ar — vazamento. Modelar B
  como conteúdo da carapaça elimina o problema e é fisicamente coerente.
- O parâmetro de B (escala/desloc/rotação) foi **buscado numericamente**
  (`tools/tune_occlusion.py`) sobre o pior caso de A (wobble ±1,8° × squash de
  hit/pouso, rachadura fechada) até leak = 0.0000: `escala 0,62·A`, `dx −4`,
  `dy −4`, `rot 8°`.

## 2. Como cada técnica obrigatória foi cumprida (e medida)

1. **Matting por frame / alfa limpo** — a migalha é sprite com alfa contínuo
   (chave de fundo branco da Fase 1). As duas metades são cortadas por uma
   **máscara de rachadura serrilhada** com rampa de 2 px (transição suave, sem
   aresta reta). B reusa o mesmo sprite → alfa idêntico ao de A.
2. **Estabilização** — o evento compõe sobre a janela f370–442 **estabilizada**
   (residual 0,53 px mediano, Fase 1). O chão não derrapa sob as cópias.
3. **Offset de tempo entre cópias** — A e B usam o **mesmo** sprite (clipe de
   origem), mas: B tem escala 0,62 (mais distante → menor, técnica nº 6),
   rotação constante 8° (A ~0°), e o **wobble** (oscilação de rotação de 1,8°)
   de B está **defasado 9 frames** (meio período) em relação a A. Resultado
   medido: **MAE mínimo entre as poses simultâneas = 45,1** (corte ≥ 2) —
   jamais pose idêntica congelada ao mesmo tempo.
4. **Oclusão, nunca pop** — a revelação é feita por **trás da máscara das duas
   metades** de A. B **nunca** anima escala/opacidade: alfa do núcleo de B
   constante em todo o clipe (Δ = **0,1** em 13 frames amostrados). A
   silhueta de A vai de **1 componente** (fechada) a **2 componentes**
   (aberta) — a rachadura é o que revela, não um scale do vazio.
5. **Cor + sombra de contato** — cor casada por **ganho por canal medido do
   plate** (ponto branco da cena ×0,958 B / ×1,004 G / ×1,038 R, exposição
   0,97, saturação 0,93 — luz difusa de dia nublado). Sombra = **darkening
   multiplicativo do chão real** (não um blob cinza), duas camadas: núcleo de
   contato (k 0,38) + difusa (k 0,22), direcionada pela luz (offset 3,5 px).
   Delta medido sob cada migalha: **A 8,2 / B 11,7** lum, coerente com a
   sombra do próprio pombo na cena (~16).
6. **Profundidade** — B nasce 4 px mais alta no quadro e sai 40 px à direita
   **mais distante** → escala 0,62 (proporcionalmente menor).
7. **Profundidade de campo** — o fundo real (janela estabilizada) já carrega o
   desfoco do material.

## 3. Anti-padrões — como garantem o NÃO

| anti-padrão | proteção |
|---|---|
| glitch/VHS como técnica central | nenhum filtro aplicado; a técnica é oclusão real por máscara |
| elemento novo por scale/opacidade do vazio | alfa núcleo de B constante (Δ 0,1); B 100% ocluída antes de f412 |
| duas cópias com pose idêntica simultânea | offset de fase de 9 frames + escala/rotação próprias; MAE mín 45,1 |
| elemento sem sombra de contato / cor destoante | darkening multiplicativo do chão + ganho de cor medido do plate |

## 4. Checklist de autoverificação (saída real do `verify_fase2.py`)

| # | item | medida | critério | status |
|---|---|---|---|---|
| 1 | frames por revelação | **10** | ≥ 8 | ✅ |
| 1b | silhueta A fechada→aberta | 1 → 2 componentes | rachadura real | ✅ |
| 2 | pose idêntica simultânea (MAE mín) | **45,1** | ≥ 2 | ✅ |
| 3 | bicada visual ↔ som | ancorada em **f400** | Fase 3, Δ alvo 0 | ✅ (ancora) |
| 4 | artefato de bloco (fill bbox máx) | **0,613** | < 0,93 | ✅ |
| 5 | anti-pop (Δ alfa núcleo de B) | **0,1** | < 1 | ✅ |
| 6 | sombra de contato (Δ lum) | **A 8,2 / B 11,7** | ≥ 6 | ✅ |
| 7 | oclusão (cobertura mín B por A) | **1,000** (43 frames) | 1,0 | ✅ |

## 5. Artefatos

- `tools/compose_fase2.py` — compositor do evento (timeline, carapaça, oclusão,
  sombra, cor). É o núcleo que a Fase 4 escala.
- `tools/tune_occlusion.py` — busca numérica dos parâmetros de B (pior caso).
- `tools/verify_fase2.py` — autoverificação com os números da seção 4.
- `assets/out/fase2/fase2_full.mp4` — 72 frames @ 24 fps, 1280×720.
- `assets/out/fase2/fase2_zoom.mp4` — crop 2,4× da região do evento.
- `assets/out/fase2/reel_fase2.png` — contact sheet do evento.
- `assets/out/fase2/evento.json` — timeline + cobertura + parâmetros
  (alimento da Fase 3 e da escalação na Fase 4).

## 6. Limitações honestas (para a Fase 4)

- **Uma** duplicação. A escalação 1→2→4 e o clímax coletivo são Fase 4; o
  compositor já parametrize "objeto" (posição/escala/rotação/wobble/sombra),
  então adicionar cópias é instanciar mais objetos com offsets próprios.
- A migalha é **sprite único** animado por wobble/squash — não é um cycle de
  multiple poses. Para o minipombo (bloco C) precisaremos de poses de
  caminhada/pata; isso entra no escopo da Fase 4.
- O "chão" onde a migalha pousa ainda tem o **fantasma do plate** (0,13% da
  área, Fase 1). Não interfere neste recorte (a migalha fica fora da região do
  fantasma), mas a Fase 4 deve resolver antes de escalar.
- Sombra/cor calibradas para **esta** janela de luz (dia nublado, luz difusa).
  Se a Fase 4 usar outro trecho com sol mais direto, o `GRADE`/`SHADOW` são
  reconstruídos a partir das mesmas medições.

## 7. O que eu preciso de você para fechar a FASE 2

1. **Aprovar o mecanismo**: reveal por oclusão (carapaça), 10 frames, sem pop,
   com sombra/cor coerentes. Assista `fase2_zoom.mp4` com atenção ao f412–f421.
2. **Leitura da carapaça**: confirme que B nascendo **dentro** de A (A racha e
   permanece) é a direção certa — é a leitura mais forte de "oclusão".
3. **Força da sombra**: está calibrada para ~Δ 8–12 lum (coerente com a cena).
   Aprova esse nível ou quer mais/menos?
