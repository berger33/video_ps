# VÍDEO 3 — FASE 1 · Assets + Matting (entrega p/ review)

Rebuild determinístico de tudo: `python3 scripts/build_clips.py`

## O que foi entregue
| Asset | Descrição | Matting |
|---|---|---|
| **clipA_vetor** | Walk cycle de 10 poses reais (GIF stop-motion), fundo verde sólido → chroma key (filmagem controlada). 180f @30fps = 6.0s, ciclo de 30f. | Chroma key + maior componente + feather |
| **clipB_foto** | Raposa REAL (foto fotográfica), ciclo de caminhada procedural (gate diagonal, bob, sway de cauda/cabeça), pegada stop-motion (poses seguradas 3f). 180f @30fps = 6.0s, ciclo de 60f. | rembg/u2net SE pesos disponíveis; neste sandbox: **GrabCut (OpenCV)** + feather |
| **campo_plate.jpg** | Plate de campo VAZIO (raposa removida por inpainting) — fundo de câmera fixa p/ composição. | — |
| **masks/** | Máscara alpha por frame de cada clipe (PNG 8-bit). | — |

## Números (report_fase1.json)
| Métrica | clipA_vetor | clipB_foto |
|---|---|---|
| frames / fps | 180 / 30 | 180 / 30 |
| resolução (crop) | 392×189 | 688×446 |
| ciclo (frames) | 30 | 60 |
| cobertura da máscara | 37.9% | 38.3% |
| std da linha do chão (pés) | **0.46 px** | **3.69 px** (~0.8% da altura) |
| loop fecha (180 % ciclo == 0 e frame[ciclo]==frame[0]) | ✅ | ✅ |

## Arquivos de review (abrir no viewer)
- `assets/build/clipB_foto/preview_plate.mp4` — raposa real andando no lugar sobre o campo vazio.
- `assets/build/clipB_foto/review_cycle.gif` — 1 ciclo (2.4s) p/ inspeção rápida.
- `assets/build/clipB_foto/preview_checker.mp4` — alpha sobre tabuleiro (qualidade das bordas).
- `assets/build/clipA_vetor/preview_plate.mp4` / `review_cycle.gif` / `preview_checker.mp4` — idem p/ o clipe vetor.
- Máscaras: `assets/build/<clip>/masks/m000.png … m179.png`.

## Transparência (importante)
1. Este sandbox **não tem rota de rede para bancos de footage** (Pexels/Mixkit/
   Wikimedia bloqueados; só PyPI/GitHub API). Por isso os clipes foram
   *construídos*: (A) a partir de um GIF de walk cycle real de raposa
   (stop-motion, 10 poses únicas — movimento é footage real, arte é vetor);
   (B) a partir de foto real de raposa com ciclo procedural de caminhada.
2. O pipeline **já suporta footage real**: se você enviar/uploadar um clipe
   de raposa (5–10s, câmera fixa, ciclo claro), basta colocá-lo em
   `assets/src/` e o matting passa para **rembg/u2net** automaticamente quando
   os pesos estiverem disponíveis (o download dos pesos está bloqueado por SSL
   neste sandbox; GrabCut é o fallback ativo).
3. clipB é raposa fotográfica com andar sintetizado — o "jank" stop-motion é
   intencional (assinatura Cyriak). clipA é arte plana com andar 100% real.

## Decisão p/ você
- Aprovar ambos e seguir (FASE 2 usa os dois: clipB como sujeito principal
  fotográfico, clipA como variante estilizada opcional);
- ou aprovar só um deles; ou pedir ajuste (amplitude do passo, bob, etc.).

**Gate FASE 1:** clipes + máscaras revisados e aprovados por escrito.
