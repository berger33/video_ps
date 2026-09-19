# Fase 5 — Polimento e entrega final

Status: **entregue — verify 6/6** — aguardando gate final.

## 1. Polimento aplicado (única intervenção de conteúdo)

**S1 (0:00–0:10,7)** — os cortes do plano documental repetiam o mesmo par de
poses (loop com leitura de GIF). Redesenhados como **5 blocos com fases
distintas** da janela de caminhada (s160–s234):

| Corte | Saída → entrada (offset na janela) |
|---|---|
| f54 | 53 → 21 |
| f108 | 74 → 42 |
| f141 (wrap interno) | 74 → 0 |
| f162 | 20 → 0 |
| f216 | 53 → 33 |

Nenhum par se repete (verificado). Nada mais foi alterado: S2, cadeia de
duplicação, áudio e grade permanecem exatamente os aprovados — o master
polido re-passou no **verify da Fase 4: 9/9**.

## 2. Export

- **`fase5_final_1080p.mp4`** (entrega): 1920×1080, 24 fps, 1080 frames,
  45,000s, h264 CRF17 preset slow + AAC 192k 48kHz, faststart, BT.709.
  Upscale lanczos + unsharp leve (0,35) sobre o master 720p — nenhum
  conteúdo re-renderizado.
- **`fase5_final_720p.mp4`**: master + trilha (mesmo container, para
  conferência 1:1).
- **`poster_1080p.png`**: f1068 (coletiva) em 1080p.

## 3. Checklist medido (tools/verify_fase5.py)

| # | Item | Medida | Critério |
|---|---|---|---|
| 1 | Master aprovado | verify_fase4 = aprovado (9/9) | obrigatório |
| 2 | Polimento S1 | cortes f54/108/141/162/216; 5 pares de poses distintos | nenhum par repetido |
| 3 | Container 1080p | 1920×1080, 24fps, 1080 frames, 45,000s, h264+aac, moov antes do mdat | todos |
| 4 | Fidelidade | PSNR (1080p rebaixado vs master) 39,7–39,8 dB em f400/f760/f1068 | ≥30 dB |
| 5 | Áudio | 45,013s, pico 0,711 (trilha aprovada intacta) | 45,000±0,05s; pico ~0,71 |
| 6 | Artefatos | mp4 1080p (45,9MB) + mp4 720p (23,2MB) + poster (2,6MB) | presentes |

## 4. Estado do projeto

F0→F5 completas. Entregável final: `assets/out/fase5/fase5_final_1080p.mp4`
(também force-add na branch para download). Toda a cadeia é regenerável:
`setup_env.sh` → `extract_sprites.py` → `build_plate.py` (2 janelas) →
`compose_fase4.py` → `verify_fase4.py` → mux/export → `verify_fase5.py`.

## 5. Notas de sandbox (3 resets nesta sessão)

- Reset 1: perdeu mídia + histórico local (recuperado do remote 2988df4).
- Reset 2: perdeu a F4 inteira (o push da época falhou por token expirado;
  17aa59f nunca chegou ao remote) — reescrita a partir do gate F3.
- Reset 3: sem perda (tudo commitado; esta reconstrução é o estado atual).
