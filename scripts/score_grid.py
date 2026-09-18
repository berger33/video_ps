#!/usr/bin/env python3
"""Grelha musical compartilhada (Fase 4/5).

Um único lugar define o tempo da peça, os degraus de `N(t)` e os picos de
multiplicação. O compositor da trilha (`compose_score.py`) e o renderizador
de vídeo (`render_final.py`) importam daqui, para que som e imagem não
possam divergir.

    128 BPM · 4/4 · BEAT = 0.46875 s · BAR = 1.875 s · 40 compassos = 75 s

Todos os degraus caem na grelha de compassos (ou de meio-compasso no
colapso), que é o que a Fase 4 exige: os picos de multiplicação aterram
em beats fortes, nunca "a meio".
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_AUDIO = ROOT / "assets" / "audio"
OUT_FINAL = ROOT / "assets" / "final"

# ------------------------------------------------------------------ tempo ---
BPM = 128.0
BEAT = 60.0 / BPM          # 0.46875 s
BAR = 4.0 * BEAT           # 1.875 s
BARS = 40
FPS = 30
DURATION = BARS * BAR      # 75.0 s
SR = 48000                 # taxa da trilha

# ------------------------------------------------- degraus de N(t) (Fase 5) --
# Colapso alinhado à grelha (bar 32 / 34 / 35.5 / 37 / 38.5) — ajuste fino
# de timing da Fase 5 em relação ao corte mudo da Fase 3.
STEPS: list[tuple[float, int]] = [
    (0.0000, 1),
    (15.0000, 2),      # bar 8
    (22.5000, 4),      # bar 12
    (30.0000, 8),      # bar 16
    (37.5000, 16),     # bar 20
    (45.0000, 24),     # bar 24
    (52.5000, 32),     # bar 28  ← clímax
    (60.0000, 16),     # bar 32
    (63.7500, 8),      # bar 34
    (66.5625, 4),      # bar 35.5
    (69.3750, 2),      # bar 37
    (72.1875, 1),      # bar 38.5
]

PEAK_N = max(n for _, n in STEPS)
PEAK_T = next(t for t, n in STEPS if n == PEAK_N)

# Picos de multiplicação (t, N) — usados para risers/impactos na trilha.
SWITCH_TIMES = [t for t, _ in STEPS[1:]]


def n_at(t: float) -> int:
    """Contagem de cópias N(t) no instante t (degraus de `STEPS`)."""
    n = STEPS[0][1]
    for ts, nv in STEPS:
        if t + 1e-9 >= ts:
            n = nv
    return n


def bar(b: int) -> float:
    """Tempo (s) do compasso `b` (0-based)."""
    return b * BAR


def beat(k: float) -> float:
    return k * BEAT


def bar_of(t: float) -> float:
    return t / BAR


def switch_bars() -> set[float]:
    return {round(t / BAR, 4) for t in SWITCH_TIMES}


def is_strong_beat(t: float, tol: float = 1e-6) -> bool:
    """True se `t` cai num downbeat (beat 1 do compasso)."""
    r = (t / BAR) % 1.0
    return min(r, 1.0 - r) < tol


def scheduler_summary() -> list[dict]:
    return [
        {
            "t": t,
            "bar": round(t / BAR, 3),
            "beat": round(t / BEAT, 3),
            "n": n,
            "on_downbeat": is_strong_beat(t, 1e-3),
        }
        for t, n in STEPS
    ]


if __name__ == "__main__":  # inspeção rápida da grelha
    import json

    print(json.dumps(scheduler_summary(), indent=2))
    print(f"BPM={BPM} BEAT={BEAT:.5f}s BAR={BAR:.4f}s DURATION={DURATION}s frames={int(DURATION*FPS)}")
