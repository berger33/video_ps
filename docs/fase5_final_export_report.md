# Fase 5 — Polimento e exportação final

- Arquivo final: `outputs/capybara_surreal_final_1080p.mp4`
- Entrada: `outputs/fase4_capybara_60s.mp4`
- Resolução: **1920 × 1080**
- Frame rate: **30 fps**
- Duração: **60 s**
- Áudio: **AAC mono**, preservado do corte aprovado (aproximadamente 93 kbps efetivos devido à fonte mono de 22,05 kHz)
- Exportação: H.264, CRF 18, `faststart`
- Ajuste de cor: contraste 1,035, brilho +0,005 e saturação 1,04
- Upscale: Lanczos

## Checklist final

- Eventos de duplicação alterados no polimento: **0**
- Eventos com reveal menor que 8 frames: **0**
- Reveal aplicado às novas instâncias: **12 frames**
- Cópias simultâneas com pose/diff de pixel idêntico: **0**
- Distância máxima evento → onset: **0 frames**
- Correlação RMS × contagem: **0,992975**
- Primeiro frame e último frame com uma instância: **sim**
- Primeiro e último frame do mesmo trecho de origem: **sim**
- Artefato de bloco/retângulo estático: **não**
- Resolução final 1080p: **sim**
- Áudio presente no MP4 final: **sim**

O polimento foi deliberadamente leve para preservar as máscaras, sombras, offsets temporais, entradas em movimento e a sincronização já aprovada.
