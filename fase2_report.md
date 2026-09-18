# VÍDEO 3 — FASE 2 · Protótipo do mecanismo central (1→2 cópias)

Script: `scripts/fase2_proto.py` · Rebuild: `python3 scripts/fase2_proto.py`
Preview: `assets/build/fase2/preview_fase2.mp4` e `review_fase2.gif`

## Técnicas 1–6 no protótipo
1. **Matting** — frames RGBA do clipB_foto (Fase 1).
2. **Ancoragem/chão** — foot-anchor por frame (linha dos pés) alinha cada
   cópia ao plano de chão; fonte std 3.69px (Fase 1), erro de alinhamento 0
   por construção.
3. **Offset de tempo** — cópia 2 = mesmo clipe em loop com fase +12 frames.
4. **Reveal por oclusão + máscara animada** — cópia 2 desenhada SOB a cópia 1,
   desliza p/ fora; wipe com feather 8px keyframado em 16 frames. Sem
   scale/opacity a partir do vazio.
5. **Cor + sombra** — casamento por ambiente local (ganho = amb_local/
   amb_origem); sombra de contato elíptica blur σ=9 (strength 0.28/0.24),
   direção de luz consistente.
6. **Profundidade** — escala linear por Y do chão: cópia 1 0.813 (gy 640),
   cópia 2 0.747 (gy 600).

## CHECKLIST (números, sem impressões)
| Item | Resultado | Gate |
|---|---|---|
| Frames do reveal (2%→98% da fração visível relativa ao fim do gate) | **16** | ≥8 ✅ |
| 2+ cópias simultâneas com pose idêntica? | **NÃO** — diff médio-abs mínimo entre instâncias = 16.2 (escala 0–255) | ✅ |
| Distância início-evento → onset de áudio | **N/A** (áudio entra na FASE 3) | — |
| Contagem de instâncias × curva RMS | **N/A** (FASE 3) | — |
| Primeiro/último frame sem cópias extras (loop) | **N/A** — protótipo não fecha loop; obrigação da FASE 4 | — |
| Artefato de bloco/retângulo estático? | **NÃO** (composição com bordas suaves; verificado no sheet de frames) | ✅ |
| Casamento de cor (delta de ambiente local antes→depois) | 20.97 → **0.27** | ✅ |
| Sombras de contato | presentes em ambas as cópias | ✅ |

## Observações
- O reveal é medido relativo ao fim do gate porque, depois do evento, as
  cópias seguem se sobrepondo como multidão (oclusão permanente é legítima e
  desejada no estilo Cyriak).
- Próximo passo (FASE 3): derivação de timestamps por RMS + onsets da trilha.

**Gate FASE 2:** aprovado por escrito → FASE 3.
