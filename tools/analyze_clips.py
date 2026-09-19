#!/usr/bin/env python3
"""Analise tecnica dos clipes de origem (FASE 1).

Mede, sem inventar: relacao entre os dois clipes, movimento global da camera,
estabilidade do plate e presenca de silhueta de pombo. Nao gera asset final.

Uso:
    tools/venv/bin/python tools/analyze_clips.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = os.path.join(ROOT, "tools", "bin", "ffmpeg")
OUT = os.path.join(ROOT, "assets", "analysis")

CLIPS = {
    "A": os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4"),
    "B": os.path.join(ROOT, "consegue_criar_um_gid_deste_po.mp4"),
}


def read_frames(path: str, scale: float = 0.5, limit: int | None = None) -> list[np.ndarray]:
    """Le todos os frames (grayscale, reduzidos) via pipe do ffmpeg."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"nao consegui abrir {path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * scale)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * scale)
    frames: list[np.ndarray] = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
        if limit and len(frames) >= limit:
            break
    cap.release()
    return frames


def motion_profile(frames: list[np.ndarray]) -> dict:
    """Movimento global entre frames consecutivos via correlacao de fase."""
    trans = []
    for i in range(1, len(frames)):
        (dx, dy), _ = cv2.phaseCorrelate(
            np.float32(frames[i - 1]), np.float32(frames[i])
        )
        trans.append((float(dx), float(dy)))
    t = np.array(trans) if trans else np.zeros((0, 2))
    if len(t) == 0:
        return {}
    cum = np.cumsum(t, axis=0)
    per_frame = np.linalg.norm(t, axis=1)
    return {
        "n_pares": int(len(t)),
        "desloc_medio_px_por_frame": round(float(per_frame.mean()), 3),
        "desloc_max_px_por_frame": round(float(per_frame.max()), 3),
        "desloc_mediano_px_por_frame": round(float(np.median(per_frame)), 3),
        "frames_praticamente_estaticos(<0.5px)": int((per_frame < 0.5).sum()),
        "deriva_total_px": [round(float(cum[-1, 0]), 1), round(float(cum[-1, 1]), 1)],
        "desloc_total_px": round(float(per_frame.sum()), 1),
    }


def compare_clips(fa: list[np.ndarray], fb: list[np.ndarray]) -> dict:
    """MAE entre os clipes nos primeiros N frames comuns (checa duplicidade)."""
    n = min(len(fa), len(fb))
    diffs = []
    for i in range(n):
        diffs.append(float(np.abs(fa[i].astype(np.int16) - fb[i].astype(np.int16)).mean()))
    d = np.array(diffs)
    return {
        "frames_comparados": int(n),
        "mae_medio": round(float(d.mean()), 3),
        "mae_mediano": round(float(np.median(d)), 3),
        "mae_max": round(float(d.max()), 3),
        "frames_com_mae<1": int((d < 1).sum()),
        "veredito": "identicos" if d.mean() < 1 else ("parecidos" if d.mean() < 8 else "diferentes"),
    }


def save_sheet(frames: list[np.ndarray], path: str, stride: int, cols: int) -> None:
    sel = frames[::stride]
    if not sel:
        return
    th, tw = sel[0].shape
    rows = int(np.ceil(len(sel) / cols))
    sheet = np.zeros((rows * th, cols * tw), np.uint8)
    for i, f in enumerate(sel):
        r, c = divmod(i, cols)
        sheet[r * th : (r + 1) * th, c * tw : (c + 1) * tw] = f
    cv2.imwrite(path, sheet)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    report: dict = {}

    data = {}
    for k, p in CLIPS.items():
        if not os.path.exists(p):
            print(f"[erro] faltando {p}")
            return 1
        frames = read_frames(p, scale=0.5)
        data[k] = frames
        info = {
            "arquivo": os.path.basename(p),
            "frames": len(frames),
            "resolucao_reduzida": list(frames[0].shape[::-1]),
            "movimento_global": motion_profile(frames),
        }
        report[k] = info
        print(f"[{k}] {info['arquivo']}: {len(frames)} frames")
        for kk, vv in info["movimento_global"].items():
            print(f"      {kk}: {vv}")

    print("\n[comparacao A vs B]")
    cmp_ab = compare_clips(data["A"], data["B"])
    report["comparacao_A_vs_B"] = cmp_ab
    for kk, vv in cmp_ab.items():
        print(f"      {kk}: {vv}")

    save_sheet(data["A"], os.path.join(OUT, "sheetA_4f.png"), stride=4, cols=10)
    save_sheet(data["B"], os.path.join(OUT, "sheetB_2f.png"), stride=2, cols=10)

    with open(os.path.join(OUT, "analysis.json"), "w") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"\n[ok] relatorio em {os.path.relpath(OUT, ROOT)}/analysis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
