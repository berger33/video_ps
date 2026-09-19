# FASE 0 — Entendimento do roteiro (piloto "Pombo//Protocolo", 0:00–0:45)

Status: **aguardando aprovação humana.** Nenhum código, asset ou download foi feito.
Objetivo desta fase: provar que eu entendi o arco e a regra causal antes de tocar em qualquer mídia.

---

## 1. A regra causal (lei do filme, não negociável)

**BICADA = DUPLICAÇÃO.**

Toda vez que o pombo dá uma bicada no chão, *algo* se duplica. Não é efeito decorativo nem
"poderzinho" pontual: é o motor mecânico do filme. A bicada é um operador, não um gesto.

Ordem de propagação no trecho:

1. No começo, o que se duplica é a **migalha**.
2. As migalhas duplicadas **não são migalhas**: revelam pernas e viram **minipombos** (~2 cm).
3. O poder **muda de sujeito**: quem bica agora é o minipombo. Trato isso como lei
   (a bicada do minipombo também duplica) — se você quiser que o minipombo bique sem
   duplicar, me diga, porque isso muda o clímax.

Consequência de montagem que eu extraio disso: cada bicada precisa ser **legível** e
**individualizável** — imagem e som casados, com o resultado da duplicação visível no quadro.
Se o espectador não consegue contar "bicou → virou dois", a regra morre.

---

## 2. Arco 0:00–0:45, em três blocos

### Bloco A — 0:00–0:15 · "documentário"
- **Imagem:** pombo comum de São Paulo andando em calçada do Centro. Plano baixo, quase
  documental — câmera perto do chão (ordem de 15–25 cm de altura, na altura do bico/peito),
  olhar rasante. Fundo (carros, pessoas) desfocado: profundidade de campo curta e/ou distância
  longa, com motion blur natural no que passa.
- **Ação:** ciclo de caminhada legível — **passo, passo, cabeça, passo, BICADA**.
  O comportamento é o do pombo real: cabeça projetando à frente a cada passo, e a bicada como
  clímax rítmico do ciclo.
- **Som:** ambiente de rua paulistana, textura fina — sem massa grave ainda. A **primeira
  bicada é o primeiro evento sonoro forte do filme** (impacto seco, corpo, transiente).
  Tudo antes disso é cama sonora: nada compete com ela.
- **Composição:** o enquadramento **já precisa nascer com espaço** para 1 → 2 → 4 cópias.
  Não é só um pombo bonito no quadro; é um palco com área de calçada limpa para as cópias
  brotarem sem sair de campo nem colidir com o fundo.

### Bloco B — 0:15–0:30 · "1 → 2 → 4"
- **Imagem:** a bicada **faz a migalha saltar** — física de salto curto: a migalha sai do
  contato com o chão, descreve um arco baixo, quica uma ou duas vezes e para.
- **Crescimento:** a cada bicada seguinte, a migalha **duplica**: 1 → 2 → 4.
- **Regra de pose (crítica):** as cópias são **o mesmo clipe de origem amostrado em tempos
  diferentes** (offset de tempo), nunca o mesmo frame colado. Cada cópia tem sua própria
  respiração/rotação/posição; duas cópias simultâneas nunca repetem pose.
- **Som:** cada bicada nova casa com percussão construída de material do próprio ambiente —
  **bicada = kick**, **movimento de cabeça = woodblock**, **unha no concreto = hi-hat**,
  **arrulho grave = baixo**. A massa sonora cresce junto com o número de corpos/objetos em cena.

### Bloco C — 0:30–0:45 · "revelação e clímax"
- **Imagem:** uma das migalhas **racha / se abre** — e por trás da abertura **duas patas
  minúsculas** são reveladas: um pombo de ~2 cm.
- **Como (não negociável):** a leitura é de **oclusão**. A migalha está **na frente** e o corpo
  está **atrás**; uma máscara animada (mínimo 8–12 frames de transição) revela o que estava
  oculto. A migalha **não some** e o minipombo **não aparece no lugar dela por corte**.
  Minha leitura: a migalha **é a carapaça / continua sendo o corpo** do minipombo — ela se
  abre e permanece visível em cena (não é um objeto descartado). Confirme ou corrija.
- **Escalada:** em poucos compassos já existem vários minipombos — cada um com **offset de
  tempo próprio**, **sombra de contato própria** e **cor casada** com a cena.
- **Clímax:** todos os minipombos **bicam ao mesmo tempo**. É o evento sonoro mais forte do
  trecho (soma dos hits + reforço grave) e é o **ponto de corte do piloto**.

---

## 3. Tabela de eventos que eu vou controlar (a espinha do trecho)

| # | Evento visual | Disparo causal | Evento sonoro | Observação |
|---|---|---|---|---|
| A1 | pombo anda, cabeça projeta | — | woodblock | cama sonora fina |
| A2 | **bicada #1** (pombo real) | — | **kick forte (1º evento)** | ainda não duplica nada visível? ver bloco B |
| B1 | migalha #1 salta | bicada | kick + whoosh curto | contato com o chão visível |
| B2 | migalha → 2 | bicada | kick | cópias com offset diferente |
| B3 | migalhas → 4 | bicada | kick (talvez duplo) | 4 poses distintas no mesmo frame |
| C1 | migalha racha (≤ 12 f de reveal) | bicada precedente | transiente + atrito | oclusão, nunca pop |
| C2 | patas + minipombo #1 | reveal | hit + mini woodblock | sombra de contato obrigatória |
| C3 | minipombos múltiplos andando/bicando | — | camada percussiva densa | offsets de tempo distintos |
| C4 | **bicada coletiva** | todos ao mesmo tempo | **impacto máximo** | **CORTE** |

Números exatos de bicadas, BPM e grade rítmica: decisão da Fase 3, sobre a cadência real do
material (a grade é ditada pela bicada, não imposta a ela).

---

## 4. Técnicas obrigatórias — como pretendo cumprir cada uma

1. **Matting por frame** (pombo e migalhas): rembg/U²-Net (onnxruntime, CPU) ou SAM;
   chroma key apenas se existir material com fundo controlado. Máscaras serão **corrigidas
   à mão** nos frames onde bico/pata se fundem com o chão. A sombra **não** sai do matte:
   é sintetizada (ver item 5).
2. **Estabilização por tracking do ponto de contato** pata↔chão: o pivô de cada compósito é a
   pegada, não o centro do objeto. Se a câmera do material for instável, estabilizo o plate
   antes (homografia / RANSAC) para que a calçada não "derrape" sob as cópias.
3. **Offset de tempo entre cópias**: cada cópia lê o clipe de origem em `t − Δᵢ`, com Δᵢ
   distintos entre si e diferentes de zero (alvo mínimo ~4–6 frames de defasagem entre
   vizinhas), garantindo que nenhum par simultâneo tenha pose idêntica.
4. **Toda revelação por oclusão**: máscara animada, **mínimo 8–12 frames**, com conteúdo
   *atrás* já existindo no mesmo frame (não há vazio de onde escalar). Zero scale-a-partir-de-0,
   zero fade-in de opacidade.
5. **Cor e sombra de contato** em cada elemento novo: casamento por estatística local
   (médias/histograma da região, balanço de branco e exposição) + **sombra de contato
   sintética** (elipse suave, direção/penumbra derivadas da luz do plate), aplicada sempre
   que o objeto toca o chão.
6. **Profundidade**: escala proporcional à distância (razão com a linha de base no chão),
   com perda leve de contraste/saturação e blur gradual nos elementos mais distantes.
7. **Áudio**: decisão documentada na Fase 3. Caminho preferencial **diegético** — kick,
   woodblock, hi-hat e baixo construídos a partir de material do ambiente (bicada, unha no
   concreto, arrulho), processados por transiente/afinação. Se isso se provar inviável,
   uso faixa eletrônica pronta sincronizada por onset (**máximo 1 frame** de distância) e
   **documento explicitamente** que esse foi o caminho seguido, como na v2.

---

## 5. Anti-padrões (violação = reprovar a entrega, mesmo que bonito)

- Filtro de glitch/VHS por cima do clipe inteiro fingindo ser a técnica central.
- Qualquer coisa nova entrando por **scale** ou **opacidade** a partir do vazio.
- **Duas cópias simultâneas com pose idêntica congelada.**
- Elemento sem **sombra de contato**, ou com cor/exposição destoando da cena.
- (meu acréscimo, derivado dos anteriores) duplicação que acontece **fora de campo** ou sem
  ser legível na tela; sombra de contato "flutuando" descolada do ponto de apoio.

---

## 6. Checklist de autoverificação — métricas e como vou medir

Vou reportar **números**, não adjetivos, antes de cada entrega:

| Item | Medição | Critério |
|---|---|---|
| Frames por evento de revelação | contagem de frames entre exposição inicial e final da máscara de reveal | **≥ 8** (alvo 10–12) por evento |
| Cópias simultâneas com pose idêntica | para cada frame, extrair recortes alinhados das cópias e calcular diferença média de pixel (MAE, escala 0–255) entre **todos** os pares simultâneos; reportar o **mínimo** de cada frame | reprovar se **MAE < 2** (quase-zero); alvo ≥ 6 |
| Distância bicada visual ↔ evento sonoro | lista de frames de bicada exportada pelo próprio animatic × onsets detectados no áudio final (`Δ` em frames) | diegético: **Δ = 0**; trilha pronta: **Δ ≤ 1** |
| Artefato de bloco/retângulo mal colado | varredura de arestas retas persistentes alinhadas aos eixos nas regiões de composição + contact sheet de frames-chave para inspeção | **zero** frames com borda reta espúria na lista final |
| Sombra de contato | em cada frame em que o objeto toca o chão, existe mancha de sombra ancorada na pegada | 100% dos frames de contato |
| Cor/exposição | média e desvio na região do objeto vs. vizinhança do chão no plate, por frame de inserção | diferença dentro da tolerância definida na Fase 2 |

---

## 7. Limites reais do meu ambiente (para você decidir com informação)

- Sandbox: **2 vCPU, 3 GB RAM, sem GPU**; ffmpeg ausente (instalo na Fase 1).
- Implicação: matting por frame em CPU é o gargalo. Plano de trabalho: processar em resolução
  reduzida (ex. 960×540 ou 1280×720) durante o desenvolvimento, com render final em 1080p
  feito por streaming/segmentos e concatenação. Funciona, mas exige disciplina de pipeline
  (caches de máscara, trabalho em blocos) — não é "renderizar tudo de uma vez".
- **Eu não tenho como filmar em São Paulo.** O material do pombo tem que vir de: banco
  gratuito (Pexels/Pixabay/Coverr), arquivos que você enviar, ou geração por IA tratada
  depois. Isso afeta diretamente a autenticidade da "calçada do Centro" (pedra portuguesa,
  guia rebaixada, meio-fio) — por isso está como pergunta na Fase 1.

---

## 8. O que eu preciso decidir com você antes da Fase 1

1. **Fonte do material** (ver pergunta na conversa): banco gratuito / você envia clipes /
   IA + tratamento.
2. **Estrutura de montagem**: plano contínuo de 45 s ou plano-base com inserts.
3. **FPS base** de trabalho e entrega (isso muda o que "8 frames" significa em segundos).
4. **Clímax e corte**: cortar seco na bicada coletiva ou mostrar a consequência antes do corte.

Se você enviar material, o ideal (por clipe): 1920×1080+, 24/25/30 fps, câmera estática,
plano baixo, pombo andando **e** bicando em calçada, 10–20 s ou mais, sem pessoas/objetos
cruzando o pombo, **e** um "clean plate" da mesma calçada sem o pombo (ouro para as
revelações por oclusão e para o preenchimento atrás das cópias).

---

## 9. Registro de decisões (18/09/2026)

**D1 — Fonte do material: geração por IA + tratamento.** Decidido por você: pombo de rua
realista, gerado por IA com controle de pose e enquadramento, e depois tratado
(matting, composição, duplicação) por mim.

### 9.1 Análise das 2 referências enviadas

**Status do arquivo:** as duas imagens foram exibidas na conversa, mas **não chegaram ao
sandbox** (não existe `/home/user/uploads/`, nenhum `.jpg` recente no disco). Consequência
prática: eu **enxergo** as imagens e consigo descrevê-las, mas **não consigo usá-las como
arquivo de referência** nas ferramentas de geração de imagem (que exigem caminho local).
Precisa reenviar (ou eu gero equivalentes do zero).

**O que eu vejo:**

| | imagem 1 | imagem 2 |
|---|---|---|
| Pose | pombo **parado**, as duas patas plantadas, cabeça erguida, corpo de perfil para a direita, peito levemente virado para a câmera | pombo **em passo**: pata esquerda plantada, **pata direita erguida no ar** em balanço, cabeça e pescoço **projetados para a frente e levemente baixos**, cauda um pouco elevada |
| Câmera | plano **baixo** (altura do peito/barriga, ~15–25 cm), praticamente rente ao chão, pombo ocupando ~1/3 da altura do quadro | **idêntica** à imagem 1 (mesmo enquadramento, mesma distância focal) |
| Fundo | caminho arborizado **desfocado**: pedestres andando, árvores, poste preto, arbustos à direita, prédios de tijolo ao fundo; luz de dia nublado, suave e fria | **praticamente o mesmo fundo**, pixel a pixel na maior parte |
| Chão | lajes grandes de pedra clara, gastas, com juntas visíveis, folhas secas e musgo nas reentrâncias | idem |

**Leitura de produção (importante):** as duas imagens são **um par de keyframes do mesmo
plano** — ou seja, você me entregou, na prática, *pose parada* + *pose de meio-passo*.
Isso é ouro para a regra obrigatória nº 3 (nada de pose congelada repetida): um ciclo de
caminhada nasce daí por interpolação. Três ressalvas técnicas:

1. **A sombra de contato das patas está queimada no chão** nas duas imagens. Para recortar
   o pombo eu preciso separar corpo, patas **e** sombra — e depois **reconstruir a sombra
   sinteticamente** (é justamente o item 5 do checklist). Vou tratar isso na Fase 1.
2. **A calçada não é o Centro de São Paulo.** O cenário lê como rua arborizada de parque
   (lajes de pedra, árvores, prédios de tijolo), não como calçada de Centro paulistano
   (pedra portuguesa, guia rebaixada, meio-fio, calçamento remendado, carros/ônibus
   desfocados). Decisão pendente (pergunta na conversa).
3. **Não existe pose de bicada nem migalha em quadro.** Faltam assets obrigatórios:
   pré-bicada, bicada (bico tocando o chão), pós-bicada, e a **migalha** (que é a
   protagonista dos 0:15–0:30) com alpha limpo, além da versão "carapaça que se abre".

### 9.2 Restrição real da minha caixa de ferramentas (você precisa saber antes de decidir)

Eu **não tenho modelo de vídeo** neste ambiente: tenho geração **de imagem** (texto→imagem e
edição com referência), não vídeo. Ou seja, "gerar por IA o clipe do pombo andando" tem dois
caminhos, e a escolha é sua:

- **(a) você gera o vídeo** com Veo/Kling/etc. a partir desses stills e sobe o clipe aqui —
  é o caminho com **maior realismo de movimento**; eu faço matting, duplicações, oclusões,
  cor/sombra e som;
- **(b) eu construo o movimento** a partir de keyframes gerados por IA + interpolação por
  fluxo óptico (RIFE/FILM em CPU) + warp/rig para o balanço de cabeça e a bicada — 100%
  autônomo da minha parte, com resultado bom em poses e enquadramento, mas **movimento não
  fotorealista** (é "animação de stills", que aliás é a gramática do próprio Cyriak);
- **(c) misto**: você gera o clipe de caminhada (bloco 0:00–0:15, o mais exigente em
  realismo) e eu construo por pose-a-pose todo o resto (bicadas, migalhas, minipombos).

### 9.3 Restrições de ambiente a considerar no planejamento das fases

- Sandbox de 2 vCPU / 3 GB / **sem GPU**. pip já sinalizou PEP 668 e, além disso, diretórios
  como `.local` e `.venv` **não persistem** entre turnos: vou precisar de um
  `tools/setup_env.sh` idempotente (ffmpeg + deps Python) rodado no início de cada fase.
- Assets pesados (vídeo, máscaras, renders) ficam **fora do Git** (`.gitignore`), no
  workspace; no repositório entra só código + docs + listas de decisão.
