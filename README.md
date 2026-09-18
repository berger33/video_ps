# COO — video_ps

Animação surreal curta (75 s, loop) inspirada na técnica de **proliferação por composição** de Cyriak Harris. Um pombo urbano se duplica dentro do próprio frame até o colapso, e volta.

Este repositório segue um pipeline em 6 fases com **aprovação humana obrigatória** entre cada uma. Não avançar de fase sem a frase `aprovado, prossiga para fase X`.

| Fase | Entrega | Status |
|------|---------|--------|
| 0 | [Brief de conceito](docs/FASE0_BRIEF.md) | aprovada |
| 1 | [Assets brutos + índice](assets/INDEX.md) | aprovada |
| 2 | [Protótipo da proliferação](assets/FASE2.md) (≥ 8 cópias no frame final) | aprovada |
| 3 | [Corte bruto 75 s, mudo, loop](assets/FASE3.md) | aprovada (revisada) |
| 4 | [Trilha 128 BPM sincronizada aos picos de `N(t)`](assets/FASE4.md) | entregue |
| 5 | [MP4 final 1080p](assets/FASE5.md) | **em revisão** |

## Contrato (não negociável)

A característica que define o estilo é **composição**: recortar o sujeito e colar N cópias no mesmo frame, com Δposição / Δescala / Δrotação. Filtro glitch/VHS/aberração sobre o clipe inteiro é rejeição automática.

## Entrega

- vídeo: `assets/final/coo_final_1080p.mp4` (1920×1080, 30 fps, 75 s, com trilha)
- previews: `assets/final/coo_preview_climax.gif`, `coo_preview_abertura_480p.mp4`
- revisão de conformidade com o pedido original: [docs/REVISAO.md](docs/REVISAO.md)

## Stack

Python 3.11 · OpenCV · Pillow · NumPy · SciPy · imageio-ffmpeg ·
soundfile · librosa · matplotlib (trilha e análise)

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/prepare_assets.py
```
