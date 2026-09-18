# VÍDEO 3 — FASE 0 · Brief de Conceito

**Título de trabalho:** *“raposas & raposas & raposas”*
**Formato:** animação surreal em loop · 60s · 1080p · 30fps
**Protagonista:** RAPOSA · **Cenário:** CAMPO VERDE ABERTO

---

## 1. Protagonista — a raposa
Uma única raposa filmada de lado em ciclo de caminhada claro e repetível
(patada → passada → patada, cauda balançando). É ela quem carrega a
assinatura do estilo: **proliferação progressiva dentro do próprio frame** —
cópias entram *andando* ou são *reveladas por oclusão*, cada uma em uma
**fase diferente do ciclo de marcha** (offsets de tempo não uniformes).
Nunca clones congelados idênticos, nunca “pop” a partir do vazio.

## 2. Cenário — campo verde
Pasto aberto com horizonte alto e limpo, céu com poucas nuvens, luz de
golden hour suave (direção de luz fixa → sombras de contato consistentes).
**Câmera 100% fixa** — condição para o tracking de ancoragem no chão.
A profundidade é resolvida por escala: raposas mais ao fundo (Y menor no
horizonte) proporcionalmente menores, nunca todas do mesmo tamanho.

## 3. Arco narrativo — 60s (elemento único → multiplicação → retorno/loop)
| Tempo | Fase | O que acontece |
|---|---|---|
| 0–8s | **Elemento único** | Uma raposa entra andando pela borda esquerda e se estabelece no centro do quadro. Trilha quieta, 1 instância. |
| 8–46s | **Multiplicação** | Eventos de duplicação disparam **nos onsets da trilha**; a contagem de cópias simultâneas segue a curva de **energia RMS** (macro). Pico de instâncias perto do pico de energia — campo coalhado de raposas em profundidades e fases de marcha distintas. Reveals de 8–12+ frames, por entrada em movimento ou oclusão animada. |
| 46–60s | **Retorno/loop** | Energia cai → cópias saem na ordem inversa (andando para fora do quadro ou ocluídas por outras). Fica a última raposa; o frame final volta ao MESMO trecho de origem do frame inicial → **loop perfeito**, sem cópias extras nas pontas. |

## 4. Trilha sonora (referência)
- **Gênero:** eletrônica excêntrica/quirky estilo Cyriak (ele compõe as
  próprias trilhas — toy-synths, samples vocais, pegada cômica).
- **BPM:** ~110–120.
- Como as trilhas do Cyriak são protegidas, o build final usará uma faixa
  **royalty-free equivalente** (ou faixa fornecida por você antes da Fase 3).
- **Sincronia programática:** contagem-alvo por segundo derivada do
  `librosa.feature.rms` real da faixa (macro); início de cada evento de
  duplicação travado a ≤ 1 frame (33ms) de um `librosa.onset.onset_detect`
  (micro). Nada estimado “no olho”.

## 5. Referências Cyriak mais próximas do resultado
1. **cows & cows & cows** (2010) — <https://www.youtube.com/watch?v=FavUpD_IjVY>
   Proliferação pastoral com coreografia surreal; é o DNA direto do projeto.
2. **Baaa** (2011) — <https://www.youtube.com/watch?v=WQO-aOdJLiw>
   Ovelhas que se autorreplicam/subdividem no ritmo; referência da
   multiplicação atrelada à música.
3. **Welcome to Kitty City** (2011) — <https://youtu.be/jX3iLfcMDCw>
   Proliferação em cadeia com musicalidade forte; referência de ritmo de
   entradas/saídas de personagens.

## 6. Material de origem (decisão da Fase 1)
1–3 clipes de raposa (5–10s cada), ciclo de caminhada claro, câmera fixa,
bom contraste sujeito/fundo para o matting. Origem: stock royalty-free
(ex.: Pexels) ou clipe fornecido por você. Máscaras alpha geradas em Fase 1
(rembg/u2net ou equivalente).

## 7. Regras inegociáveis (resumo do gate)
- Reveal de cada cópia nova: **≥ 8 frames**, por movimento real ou máscara
  animada (oclusão) — proibido scale/opacidade a partir do vazio.
- **Zero** cópias com pose idêntica simultâneas.
- Casamento de cor + sombra de contato em toda cópia.
- Escala por profundidade (função de perspectiva simples).
- Sem filtros glitch/VHS como técnica central; sem retângulos/blocos colados.
- Primeiro = último trecho de origem (loop fecha).

---

**Status:** aguardando aprovação por escrito para iniciar a FASE 1
(aquisição/preparação de assets: clipes + máscaras alpha).
