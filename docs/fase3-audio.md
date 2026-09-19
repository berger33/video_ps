# Fase 3 — Trilha sonora (45,000s)

**Status:** trilha + timestamps + verify entregues para aprovação (gate F3).
O áudio entra no vídeo na Fase 4 (conformedo) — aqui ele é aprovado sozinho.

## 1. Caminho decidido (documentação obrigatória do roteiro)

**Caminho diegético** — percussão 100% construída de samples do próprio clipe
`assets/audio/A_ambiente.wav` (48 kHz, 20,01s). O caminho alternativo ("faixa
eletrônica pronta sincronizada só por onset") **não foi necessário**.

| Papel sonoro | Sample real do clipe | Instante |
|---|---|---|
| KICK (bicada) | clique real da bicada + thump ~+20ms | 16,7656s |
| WOODBLOCK (passos) | tiques de unhas no concreto | 6,353 / 9,266 / 7,758 / 13,134s |
| HI-HAT (unha) | cliques isolados curtos | 1,509 / 10,955 / 4,275 / 2,869s |
| CRACK (rachadura/revelação) | tique de unha esticado 5× + bandpass 1,8–5,2 kHz | 7,758s |
| SNAP (coletiva) | tique de unha sem esticar + fade 10ms | 7,758s |
| CAMA | ambiente inteiro lowpass 900 Hz, em loop com crossfade 400ms (clipe é 20,01s; a trilha é 45s) | — |

### Única desviação (registrada)
O **arrulho grave (baixo) é sintetizado** (fundamental 228 Hz, padrão
"hoo-hoo" de 2 humps, 2ª/3ª harmônicas, queda de pitch no fim do 2º hump,
vibrato 4,5 Hz, ar de bico). Verificação que motivou: varredura tonal
(peakiness > 12 nas bandas 80–300 / 200–450 / 450–800 Hz) não encontra
**nenhum** segmento de arrulho no material — não há sample para extrair. O
elemento é desenhado para casar com a banda grave dominante do ambiente.
Tudo o que existe no clipe, o clipe faz.

## 2. O que a análise do material mediu

- **Bicada real:** clique de 1 sample (máx. 0,433) em **16,7656s** = f402 do
  field, ~2 frames após o contato visual f400 (latência real do material).
  Essa latência afeta o *timbre* (o sub sintetizado é disparado pelo envelope
  do clique, atrasado 2ms — "o clique abre, o corpo fecha"), **não** o
  *timing*: no corte, o onset é quantizado ao frame da bicada.
- **Tiques de unhas (clusters):** 1,38–1,87 / 2,87–3,44 / 4,27–4,89 /
  6,27–6,55 / 7,60–7,83 / 9,18–9,64 / 11,00–11,25 / 12,38–13,61 /
  14,54–15,04s.
- **Ritmo real dos passos (janela de caminhada f160–235 = 6,67–9,80s):**
  3 steps/ciclo, offsets em ms — c1 [0,42,88,134,185,240], c2 [0,65,137],
  c3 [0,90,177,249,289,350,376,432]; gaps entre ciclos 1,382 / 1,483s.
  Usado no Bloco A **sem quantizar** (leitura documental: passos reais com
  deriva ±2%).
- **Arrulho:** 0 segmentos tonais (ver seção 1) → sintetizado.

## 3. Grade rítmica

120 BPM ⇒ **12 frames/beat, 48 frames/compasso (2,000s)**, fase 288
(beats em f0, 12, 24, …, 288, 300, …). O grid casa 1:1 com a grade de frames
@24fps — a Fase 4 encaixa as bicadas *novas* do filme em beats do grid.

### Regra de sincronia aplicada (aprovada na F2)
> "Se o kick real não cair no frame da bicada, **ajustar o kick, não o frame
> da bicada** — a imagem é a mestra."

A bicada do vídeo aprovado (F2) está em **f400** (contato) e a revelação em
**f412–421**. f400 não é beat da fase 288 (o mais próximo é f396). Decisão:
**KICK #2 foi movido de f384 para f400** e o crack para **f412** (+12f,
mesmo intervalo do protótipo F2). Consequência documentada: o kick fica 4f
(167 ms) após o beat 396 — um *drag* diegético em um único kick, aceito
porque a imagem é a mestra. O restante do grid segue a fase 288.

## 4. Estrutura e eventos (frames @24fps; 1080 = 45,000s)

**Bloco A (f0–359, 0:00–0:15)** — câmera achando a cena:
cama fina (−19 dB) + woodblock no ritmo **real** dos passos (não
quantizado). **Nenhum evento forte antes de f288.**
- `f288` (12,000s) — **KICK #1** (deep): a 1ª bicada do filme, 1º evento
  forte (razão de pico vs tudo que vem antes: **8,9×**).

**Bloco B (f360–719, 0:15–0:30)** — a música toma o ritmo real
(quantização), a massa grave (coo) entra com a duplicação:
- coo a cada compasso (f360, 408, 456, …)
- hats em colcheias (6f) até f600, semicolcheias (3f) até f720
- woodblock quantizado em colcheias
- `f400` — **KICK #2: A BICADA DA IMAGEM (F2, mestra)** — duplicação 1→2
- `f412` — **CRACK**: migalha abre (revelação F2 f412–421, oclusão)
- `f480/f483` — **KICK #3 duplo**: duplicação 2→4 (+cracks f492/f495)
- `f576` — **KICK #4**: preparação (sem duplicação)

**Bloco C (f720–1079, 0:30–0:45)** — revelação das patas, build, coletiva:
- `f744` — **KICK #5** + `f756` **CRACK**: pata #1 (minipombo) — oclusão
- camada de **minibicadas** (mini woodblock, 1 oitava acima): 1/beat a
  partir de f768 → 2/beat f864 → 4/beat f960 (build)
- coo: 1/compasso até f912, 1/beat f912–960, drive f960–1056
  (para antes do hit = respiro de 12f)
- `f1068` (44,500s) — **BICADA COLETIVA (máximo do filme)**: kick (corpo
  65/130 Hz) + thump 48 Hz curto + snap de migalha + 4 minibicadas em
  0/2/4/6f (o bando peica junto) + burst de ruído
- **hold de 12 frames no pico → CORTE seco em f1080 (45,000s)**

### O hit da coletiva (medido no áudio final)
Pico máximo do filme (**0,71**, em f1068) — 14% acima do maior pico de C
(0,62). Cauda: corpo do kick decaí por ~150–180 ms; os dois últimos
minipecks da pata (f+4, f+6 = 166/250 ms) ficam a 14% e 8% do pico;
corte em cauda < 10% (quase silêncio). Nada compete com o hit.

## 5. Master

Normalização para −1 dBFS (pico 0,89) + `tanh(1,15·x)·0,92` (limite suave).
Mono 48 kHz, exatamente 45,000s = 1080 frames.

## 6. Verificação (medida no áudio final, não na intenção)

`tools/verify_audio_fase3.py` → `assets/audio/verify_fase3.json` — **5/5 OK**:

| # | Item | Medida | Critério |
|---|---|---|---|
| 1 | Onsets vs frames de eventos | Δmáx **0,1 frame** (7 eventos fortes: f288, f400, f480, f576, f744, f756, f1068) | ≤ 1 frame |
| 2 | 1º evento forte | pico do KICK#1 = 0,32 vs 0,036 máx. antes de f288 → **8,9×** | ≥ 4× |
| 3 | Crescendo + pico máximo | RMS A 0,008 < B 0,032 < C 0,042; pico do filme 0,71 **dentro** de f1068–1080; RMS do ataque do hit (4f) 0,127 ≥ RMS de C | A<B<C; máximo no hit |
| 4 | Duração + hold | 1080,0 frames; pico nos primeiros 10 ms do hold; após 100 ms nada > 20% do pico; último 100 ms < 10% | corte seco na cauda |
| 5 | Preview | `assets/audio/fase3_preview.png` (waveform + blocos + marcadores) | — |

O mesmo verify roda **de novo na Fase 4**, contra os frames reais das
bicadas no vídeo cortado (a bicada f400 da imagem deve receber o kick no
frame 0,0 — delta alvo 0).

## 7. Arquivos

- `assets/audio/fase3_track.wav` — trilha (45,000s, mono 48k)
- `assets/audio/fase3_timestamps.json` — eventos, grade, samples, caminho
- `assets/audio/verify_fase3.json` — checklist medido
- `assets/audio/fase3_preview.png` — waveform com marcadores
- `tools/audio_fase3.py` — compositor (reproduzível)
- `tools/verify_audio_fase3.py` — verificação

## 8. Decisões abertas p/ a aprovação

1. **Coo sintetizado** (seção 1): única desviação do caminho diegético —
   aceitável? (alternativa: remover o baixo e deixar o grave só de cama +
   kick, mais seco).
2. **Drag de 4f do KICK#2** (f400 vs beat 396): consequência direta da regra
   "imagem é a mestra" — aceitável? (alternativa: reafasar o grid inteiro
   para f400, que moveria todos os demais eventos e o hit da coletiva).
3. **Hold de 12f** (coletiva em f1068 = 44,500s, corte em 45,000s): a
   alternativa (corte seco exatamente no hit, 44,5s) violaria a duração de
   45s da spec.
