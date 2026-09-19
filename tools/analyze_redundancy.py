#!/usr/bin/env python3
"""Detecta redundancia entre/dentro dos clipes (loop, subrange, stutter).

Pergunta que precisa de resposta numerica antes de escolher o material da FASE 1:
- o clipe B e um sub-trecho do clipe A?
- os clipes tem loop interno (mesmo conteudo repetido em lags grandes)?
- existem "stutters" (frames repetidos por geracao por IA)?

Uso: tools/venv/bin/python tools/analyze_redundancy.py
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "analysis")
CLIPS = {
    "A": os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4"),
    "B": os.path.join(ROOT, "consegue_criar_um_gid_deste_po.mp4"),
}
SCALE = 0.35  # comparacoes em resolucao baixa; alinhamento fino depois


def load(path: str) -> np.ndarray:
    cap = cv2.VideoCapture(path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * SCALE)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * SCALE)
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        fr.append(g.astype(np.float32))
    cap.release()
    return np.stack(fr)


def mae_aligned(a: np.ndarray, b: np.ndarray, search: int = 6) -> tuple[float, tuple[int, int]]:
    """MAE minimo entre b e a em janela de deslocamento (compensa deriva de camera)."""
    h, w = a.shape
    best, bestd = 1e9, (0, 0)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            y0, y1 = max(0, dy), min(h, h + dy)
            x0, x1 = max(0, dx), min(w, w + dx)
            bb = b[y0 - dy : y1 - dy, x0 - dx : x1 - dx]
            aa = a[y0:y1, x0:x1]
            d = float(np.abs(aa - bb).mean())
            if d < best:
                best, bestd = d, (dy, dx)
    return best, bestd


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    A, B = load(CLIPS["A"]), load(CLIPS["B"])
    print(f"A: {A.shape[0]} frames | B: {B.shape[0]} frames")

    # 1) B e subrange de A? para cada frame de B (passo 8) acha melhor frame em A
    print("\n[1] B dentro de A? (melhor match de cada frame de B em A)")
    hits = []
    for i in range(0, B.shape[0], 8):
        best_j, best_d = -1, 1e9
        for j in range(0, A.shape[0], 4):
            d, _ = mae_aligned(A[j], B[i], search=8)
            if d < best_d:
                best_d, best_j = d, j
        hits.append((i, best_j, round(best_d, 2)))
    for i, j, d in hits[:15]:
        print(f"   B[{i:3d}] ~ A[{j:3d}]  MAE={d}")
    matched = [h for h in hits if h[2] < 3.0]
    print(f"   frames de B com match forte em A: {len(matched)}/{len(hits)}")

    # 2) consistencia do offset (se subrange, j - i constante)
    offs = [j - i for i, j, d in matched if j >= 0]
    if offs:
        print(f"   offsets (j-i): min={min(offs)} max={max(offs)} mediana={int(np.median(offs))}")

    # 3) loop interno em A: para cada i, melhor j > i+48
    print("\n[3] loop/repeticao interna em A (melhor j > i+48)")
    lags = []
    for i in range(0, A.shape[0], 16):
        best_j, best_d = -1, 1e9
        for j in range(i + 48, A.shape[0], 4):
            d, _ = mae_aligned(A[i], A[j], search=8)
            if d < best_d:
                best_d, best_j = d, j
        lags.append((i, best_j, round(best_d, 2), best_j - i if best_j > 0 else None))
    for i, j, d, lag in lags:
        flag = "  <== quase identico" if d < 3 else ""
        print(f"   A[{i:3d}] -> A[{j:3d}] MAE={d}{flag}")
    strong = [l for l in lags if l[2] < 3 and l[3]]
    if strong:
        print(f"   provaveis repeticao: {len(strong)} pares, lag mediano={int(np.median([s[3] for s in strong]))} frames")

    # 4) stutter: frames consecutivos quase identicos (em A, com compensacao)
    print("\n[4] stutter (pares consecutivos com MAE alinhado < 1.0)")
    st = []
    for i in range(1, A.shape[0]):
        d, sh = mae_aligned(A[i - 1], A[i], search=4)
        if d < 1.0:
            st.append((i - 1, i, round(d, 2), sh))
    print(f"   pares quase-identicos consecutivos: {len(st)} de {A.shape[0]-1}")
    for s in st[:10]:
        print(f"   {s}")

    json.dump(
        {
            "A_frames": int(A.shape[0]),
            "B_frames": int(B.shape[0]),
            "B_em_A": [{"B": i, "A": j, "mae": d} for i, j, d in hits],
            "B_em_A_matches_fortes": len(matched),
            "offsets_se_constante": [min(offs), max(offs), int(np.median(offs))] if offs else None,
            "A_repeticao_interna": [{"i": i, "j": j, "mae": d, "lag": lag} for i, j, d, lag in lags],
            "stutters": len(st),
        },
        open(os.path.join(OUT, "redundancy.json"), "w"),
        indent=2,
    )
    print("\n[ok] assets/analysis/redundancy.json")


if __name__ == "__main__":
    main()
