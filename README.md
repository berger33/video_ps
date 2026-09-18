# COO — video_ps

Animação surreal curta (75 s, loop) inspirada na técnica de **proliferação por composição** de Cyriak Harris. Um pombo urbano se duplica dentro do próprio frame até o colapso, e volta.

Este repositório segue um pipeline em 6 fases com **aprovação humana obrigatória** entre cada uma. Não avançar de fase sem a frase `aprovado, prossiga para fase X`.

| Fase | Entrega | Status |
|------|---------|--------|
| 0 | [Brief de conceito](docs/FASE0_BRIEF.md) | aprovada |
| 1 | [Assets brutos + índice](assets/INDEX.md) | aprovada |
| 2 | [Protótipo da proliferação](assets/FASE2.md) (≥ 8 cópias no frame final) | aprovada |
| 3 | [Corte bruto 75 s, mudo, loop](assets/FASE3.md) | **em revisão** |
| 4 | Trilha 128 BPM sincronizada aos picos de `N(t)` | bloqueada |
| 5 | MP4 final 1080p | bloqueada |

## Contrato (não negociável)

A característica que define o estilo é **composição**: recortar o sujeito e colar N cópias no mesmo frame, com Δposição / Δescala / Δrotação. Filtro glitch/VHS/aberração sobre o clipe inteiro é rejeição automática.

## Stack

Python 3.11 · OpenCV · Pillow · NumPy · imageio-ffmpeg  
(MoviePy / librosa entram na Fase 2–4.)

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare_assets.py
```
