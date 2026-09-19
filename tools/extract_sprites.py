#!/usr/bin/env python3
"""FASE 1 — extracao de sprites (migalha e minipombo) por key de fundo branco.

Tecnica obrigatoria nº 1: "matting do pombo e das migalhas por frame". Para os
assets gerados em fundo branco controlado, o matting e por key cromatica +
refinamento de borda (nao ha risco de paralaxe, ao contrario do clipe filmado).

Saida: assets/sprites/<nome>_rgba.png + <nome>_alpha.png + sprites.json com
bbox, area, cor media e estatisticas de borda.

Uso: tools/venv/bin/python tools/extract_sprites.py
"""
from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "assets", "raw")
OUT = os.path.join(ROOT, "assets", "sprites")

ASSETS = {
    "migalha": "migalha_branco.png",
    "minipombo": "minipombo_branco.png",
}


def core_mask(img: np.ndarray, lum_thr: int = 214, sat_thr: int = 12) -> np.ndarray:
    """Nucleo do sujeito: escuro OU cromatico (a sombra do fundo e clara e neutra)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mx = img.max(axis=2).astype(np.float32)
    mn = img.min(axis=2).astype(np.float32)
    sat = mx - mn
    return (((g < lum_thr) | (sat > sat_thr))).astype(np.uint8)


def key_white(img: np.ndarray, grow: int = 4, feather: float = 1.6) -> np.ndarray:
    """Alpha do objeto a partir do nucleo, com crescimento e rampa de borda.

    Evita capturar a sombra suave projetada no fundo branco: o nucleo exige
    luminancia baixa (objeto) ou saturacao (objeto colorido), e a rampa fica
    limitada a `grow` px ao redor do nucleo — a sombra difusa fica de fora
    (ela sera sintetizada, conforme a tecnica nº 5 do roteiro).
    """
    core = core_mask(img)
    core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), 2)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(core, 8)
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        core = (lab == k).astype(np.uint8)
    core = cv2.morphologyEx(core, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
    grown = cv2.dilate(core, np.ones((grow * 2 + 1,) * 2, np.uint8), 1)
    soft = cv2.GaussianBlur(grown.astype(np.float32), (0, 0), feather)
    return np.clip(soft, 0, 1)


def clean_alpha(a: np.ndarray, min_area: int = 120) -> np.ndarray:
    m = (a > 0.35).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), 2)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for k in range(1, n):
        if stats[k, cv2.CC_STAT_AREA] >= min_area:
            keep[lab == k] = 1
    # suaviza alpha apenas perto da borda (preserva interior solido)
    edge = cv2.dilate(keep, np.ones((5, 5), np.uint8)) - cv2.erode(keep, np.ones((5, 5), np.uint8))
    out = a * keep
    blur = cv2.GaussianBlur(out, (0, 0), 0.8)
    out = np.where(edge > 0, blur, out)
    return np.clip(out, 0, 1)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for name, fn in ASSETS.items():
        p = os.path.join(RAW, fn)
        img = cv2.imread(p)
        if img is None:
            print(f"[erro] nao li {p}")
            return 1
        a = clean_alpha(key_white(img))
        ys, xs = np.nonzero(a > 0.5)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        pad = 8
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(img.shape[1] - 1, x1 + pad), min(img.shape[0] - 1, y1 + pad)
        crop = img[y0 : y1 + 1, x0 : x1 + 1].copy()
        ac = a[y0 : y1 + 1, x0 : x1 + 1]

        rgba = np.dstack([crop, (ac * 255).astype(np.uint8)])
        cv2.imwrite(os.path.join(OUT, f"{name}_rgba.png"), rgba)
        cv2.imwrite(os.path.join(OUT, f"{name}_alpha.png"), (ac * 255).astype(np.uint8))

        # cor media do sujeito (para casamento de cor/exposicao com a cena)
        sel = ac > 0.8
        mean = [float(v) for v in crop[sel].mean(axis=0)] if sel.any() else [0, 0, 0]
        soft = int(((ac > 0.08) & (ac < 0.92)).sum())
        solid = int((ac > 0.5).sum())
        meta[name] = {
            "origem": fn,
            "bbox": [int(x0), int(y0), int(x1), int(y1)],
            "wh": [int(x1 - x0 + 1), int(y1 - y0 + 1)],
            "area_solida_px": solid,
            "borda_suave_px": soft,
            "borda_pct": round(soft / max(solid, 1) * 100, 2),
            "cor_media_bgr": [round(v, 1) for v in mean],
            "aspecto": round((x1 - x0 + 1) / (y1 - y0 + 1), 3),
        }
        print(
            f"[{name}] {meta[name]['wh']}px | solido={solid} borda_suave={soft} ({meta[name]['borda_pct']}%) | "
            f"cor media BGR={meta[name]['cor_media_bgr']}"
        )

    json.dump(meta, open(os.path.join(OUT, "sprites.json"), "w"), indent=2, ensure_ascii=False)
    print(f"[ok] sprites em {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
