#!/usr/bin/env python3
"""FASE 2 — busca os parametros de B (escala/desloc/rot) para que B fique
100% ocluida pela carapaca de A em TODOS os estados do periodo fechado.

Modela (pior caso, seguro):
  - A: wobble ±amp em 5 angulos x squash {(1,1), hit, pouso}, fechada
  - B: rot0 + wobble em 5 angulos (o periodo fechado cobre o ciclo inteiro)
Escolhe o menor pior-leak; em empate, a maior escala (legibilidade).

Uso: tools/venv/bin/python tools/tune_occlusion.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose_fase2 as C  # noqa: E402


def a_plane_at(wob: float, squash, gap: float) -> np.ndarray:
    c_L, pv_L = C.render_object(C.HALF_L, C.SCALE_A, wob, squash)
    c_R, pv_R = C.render_object(C.HALF_R, C.SCALE_A, wob, squash)
    p = np.zeros((C.FH, C.FW), np.float32)
    C.paste_canvas(p, c_L, pv_L, (C.POS_A[0] - gap / 2, C.POS_A[1]), 0.0,
                   alpha_only=True)
    C.paste_canvas(p, c_R, pv_R, (C.POS_A[0] + gap / 2, C.POS_A[1]), 0.0,
                   alpha_only=True)
    return p


def b_plane(scale: float, dx: float, dy: float, rot: float) -> np.ndarray:
    c_B, pv_B = C.render_object(C.MIG, scale, rot, (1, 1))
    p = np.zeros((C.FH, C.FW), np.float32)
    C.paste_canvas(p, c_B, pv_B, (C.POS_A[0] + dx, C.POS_A[1] + dy), 0.0,
                   alpha_only=True)
    return p


def main() -> int:
    C.MIG = C.grade(C.load_rgba(os.path.join(C.SPR, "migalha_rgba.png")),
                    C.GRADE)
    C.HALF_L, C.HALF_R = C.cut_halves(C.MIG)

    a_states = []
    for wob in (-C.WOB_AMP, -C.WOB_AMP / 2, 0.0, C.WOB_AMP / 2, C.WOB_AMP):
        for sq in ((1.0, 1.0), (1.06, 0.90), (1.09, 0.86)):
            a_states.append(a_plane_at(wob, sq, 0.0))
    a_worst = np.min(a_states, axis=0)  # carapaca mais "estreita" possivel
    thr = 20 / 255.0

    best = None
    for scale in (0.80, 0.78, 0.75, 0.72, 0.70, 0.68, 0.65, 0.62, 0.60, 0.58):
        for dx in range(-8, 9, 2):
            for dy in range(-10, -1, 1):
                for rot0 in (8.0, 10.0, 12.0):
                    worst = 0.0
                    for wob_b in (-C.WOB_AMP, -C.WOB_AMP / 2, 0.0,
                                  C.WOB_AMP / 2, C.WOB_AMP):
                        b = b_plane(scale * C.SCALE_A, float(dx), float(dy),
                                    rot0 + wob_b)
                        vis = b > thr
                        if vis.sum() == 0:
                            continue
                        leak = float((vis & ~(a_worst > thr)).sum() / vis.sum())
                        worst = max(worst, leak)
                    if best is None or worst < best[0]:
                        best = (worst, scale, dx, dy, rot0)
    leak, scale, dx, dy, rot0 = best
    print(f"[tune] pior caso: leak={leak:.4f} escala={scale:.2f} "
          f"dx={dx} dy={dy} rot0={rot0}")
    print(f"[tune] ->  SCALE_B = SCALE_A * {scale:.2f};  "
          f"POS_B = (POS_A[0]+{dx}, POS_A[1]+{dy});  ROT_B = {rot0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
