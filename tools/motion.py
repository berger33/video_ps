#!/usr/bin/env python3
"""Campo de movimento suave (paralaxe) por blocos + ajuste polinomial robusto.

Por que existe: o clipe de origem e uma camera panoramica sobre uma cena 3D
(chao proximo + fundo distante). Uma translacao GLOBAL nao alinha os frames
(medido: MAE piora depois de alinhar). A paralaxe faz o chao proximo andar mais
que o fundo. Aqui medimos o deslocamento em blocos, rejeitamos outliers (blocos
com o pombo, blocos sem textura) e ajustamos um modelo suave
    dx(x,y) = a0 + a1*x + a2*y (+ a3*x^2 + a4*y^2 + a5*x*y)
por minimos quadrados com rejeicao iterativa. Alinhar = remap com esse campo.

Uso (diagnostico):
  tools/venv/bin/python tools/motion.py
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLOCK = 96      # tamanho do bloco (px, na resolucao de trabalho)
STEP = 48       # passo da grade
RESP_MIN = 0.10  # resposta minima da correlacao de fase para aceitar o bloco
DEG = 2         # grau do polinomio (2 = quadratico)


def _blocks(h: int, w: int, block: int = BLOCK, step: int = STEP) -> list[tuple[int, int]]:
    out = []
    for y in range(0, max(1, h - block + 1), step):
        for x in range(0, max(1, w - block + 1), step):
            out.append((x, y))
    if not out:
        out = [(0, 0)]
    return out


def _design(xs: np.ndarray, ys: np.ndarray, deg: int, w: int, h: int) -> np.ndarray:
    xn = xs / w
    yn = ys / h
    cols = [np.ones_like(xn), xn, yn]
    if deg >= 2:
        cols += [xn * xn, yn * yn, xn * yn]
    if deg >= 3:
        cols += [xn**3, yn**3, xn * xn * yn, xn * yn * yn]
    return np.stack(cols, axis=1)


def fit_field(ref: np.ndarray, mov: np.ndarray, deg: int = DEG, iters: int = 3) -> dict | None:
    """Ajusta o campo que leva `mov` para o referencial de `ref`.

    Retorna {'coef_dx','coef_dy','n_in','resid'} ou None se nao houver dados.
    """
    h, w = ref.shape
    pts, dxs, dys, ws = [], [], [], []
    for (x, y) in _blocks(h, w):
        a = np.float32(ref[y : y + BLOCK, x : x + BLOCK])
        b = np.float32(mov[y : y + BLOCK, x : x + BLOCK])
        if a.std() < 6 or b.std() < 6:  # bloco sem textura
            continue
        try:
            (dx, dy), resp = cv2.phaseCorrelate(a, b)
        except cv2.error:
            continue
        if not np.isfinite(dx) or abs(dx) > BLOCK / 2 or abs(dy) > BLOCK / 2:
            continue
        pts.append((x + BLOCK / 2, y + BLOCK / 2))
        dxs.append(dx)
        dys.append(dy)
        ws.append(resp)
    if len(pts) < 6:
        return None
    pts = np.array(pts, float)
    dxs = np.array(dxs, float)
    dys = np.array(dys, float)
    ws = np.array(ws, float)
    keep = np.ones(len(pts), bool)

    coef_dx = coef_dy = None
    for _ in range(iters):
        A = _design(pts[keep, 0], pts[keep, 1], deg, w, h)
        wgt = np.sqrt(np.clip(ws[keep], 0.05, None))
        Aw = A * wgt[:, None]
        coef_dx, *_ = np.linalg.lstsq(Aw, dxs[keep] * wgt, rcond=None)
        coef_dy, *_ = np.linalg.lstsq(Aw, dys[keep] * wgt, rcond=None)
        A_all = _design(pts[:, 0], pts[:, 1], deg, w, h)
        px = A_all @ coef_dx
        py = A_all @ coef_dy
        res = np.hypot(px - dxs, py - dys)
        thr = max(1.0, float(np.median(res[keep])) * 2.5)
        new = res < thr
        if new.sum() < 5 or (new == keep).all():
            keep = new if new.sum() >= 5 else keep
            break
        keep = new
    if coef_dx is None:
        return None
    A_all = _design(pts[:, 0], pts[:, 1], deg, w, h)
    res = np.hypot(A_all @ coef_dx - dxs, A_all @ coef_dy - dys)
    return {
        "coef_dx": coef_dx,
        "coef_dy": coef_dy,
        "deg": deg,
        "n_in": int(keep.sum()),
        "n_total": int(len(pts)),
        "resid_med": float(np.median(res[keep])),
        "shape": (h, w),
    }


def field_maps(field: dict, shape: tuple[int, int] | None = None, scale: float = 1.0):
    """Mapas de remap (x,y) para alinhar `mov` ao referencial de `ref`.

    `shape` permite avaliar o mesmo campo em outra resolucao (as coordenadas sao
    normalizadas por w/h, entao o campo e invariante a escala); `scale` converte
    o deslocamento (medido na resolucao do ajuste) para a resolucao alvo.
    """
    fh, fw = field["shape"]
    if shape is None:
        shape = (fh, fw)
        scale = 1.0
    h, w = shape
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    if xs.size > 4_000_000:  # limita custo de memoria
        raise MemoryError("frame grande demais para remap denso")
    # normalizacao pela resolucao ALVO: o campo e um polinomio em coords [0,1]
    A = _design(xs.ravel(), ys.ravel(), field["deg"], w, h)
    dx = (A @ field["coef_dx"]).reshape(h, w).astype(np.float32) * scale
    dy = (A @ field["coef_dy"]).reshape(h, w).astype(np.float32) * scale
    return xs + dx, ys + dy


def apply_field(img: np.ndarray, field: dict, scale: float = 1.0, border: int = cv2.BORDER_REPLICATE) -> np.ndarray:
    mx, my = field_maps(field, shape=img.shape[:2], scale=scale)
    return cv2.remap(img, mx, my, interpolation=cv2.INTER_LINEAR, borderMode=border)


def maps_in_box(field: dict, box: tuple[int, int, int, int], scale: float = 1.0):
    """Mapas de remap apenas dentro de (x0,y0,x1,y1) — economiza memoria/tempo."""
    x0, y0, x1, y1 = box
    fh, fw = field["shape"]
    xs, ys = np.meshgrid(np.arange(x0, x1, dtype=np.float32), np.arange(y0, y1, dtype=np.float32))
    A = _design(xs.ravel(), ys.ravel(), field["deg"], fw, fh)
    dx = (A @ field["coef_dx"]).reshape(xs.shape).astype(np.float32) * scale
    dy = (A @ field["coef_dy"]).reshape(xs.shape).astype(np.float32) * scale
    return xs + dx, ys + dy


def _selftest() -> None:
    cap = cv2.VideoCapture(os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4"))
    want = {100, 102, 110, 400, 402, 410, 460, 470}
    frames = {}
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            frames[i] = cv2.resize(g, (g.shape[1] // 2, g.shape[0] // 2), interpolation=cv2.INTER_AREA)
        i += 1
    cap.release()

    for (i, j) in [(100, 102), (100, 110), (400, 402), (400, 410), (460, 470)]:
        ref, mov = frames[i].astype(np.float32), frames[j].astype(np.float32)
        base = float(np.abs(ref - mov).mean())
        f = fit_field(ref, mov)
        if f is None:
            print(f"f{j}->f{i}: campo NAO estimado")
            continue
        aligned = apply_field(mov, f)
        mae = float(np.abs(ref - aligned).mean())
        # mede apenas na faixa do chao (onde o alinhamento importa mais)
        h = ref.shape[0]
        g = slice(int(h * 0.55), h)
        base_g = float(np.abs(ref[g] - mov[g]).mean())
        mae_g = float(np.abs(ref[g] - aligned[g]).mean())
        print(
            f"f{j}->f{i}: blocos {f['n_in']}/{f['n_total']} resid={f['resid_med']:.2f}px | "
            f"MAE global {base:.2f}->{mae:.2f} | chao {base_g:.2f}->{mae_g:.2f}"
        )


if __name__ == "__main__":
    sys.exit(_selftest())
