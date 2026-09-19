#!/usr/bin/env python3
"""FASE 1 — construcao do plate/base estabilizado.

Gera, para uma janela de frames do clipe de origem:
  1. a sequencia ESTABILIZADA no referencial do frame-alvo (o chao para de
     derrapar — tecnica nº 2, tracking do ponto de contato);
  2. um PLATE LIMPO (chao sem o pombo) por mediana temporal com exclusao de
     atividade, no mesmo referencial — e a base para as oclusoes/revelacoes;
  3. um JSON com a qualidade medida (residuo do alinhamento, % de frames ok,
     cobertura de recorte).

Uso:
  tools/venv/bin/python tools/build_plate.py --window 370,442
  tools/venv/bin/python tools/build_plate.py --window 200,260 --out assets/plates/walk
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motion import apply_field, fit_field  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIP = os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4")


def read_window(path: str, a: int, b: int) -> tuple[list[np.ndarray], list[np.ndarray]]:
    cap = cv2.VideoCapture(path)
    full, half = [], []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if a <= i < b:
            full.append(f)
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            half.append(cv2.resize(g, (g.shape[1] // 2, g.shape[0] // 2), interpolation=cv2.INTER_AREA))
        i += 1
    cap.release()
    return full, half


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", required=True, help="a,b")
    ap.add_argument("--out", default=None)
    ap.add_argument("--ref", type=int, default=None, help="frame de referencia (default: meio da janela)")
    ap.add_argument("--clip", default=CLIP)
    args = ap.parse_args()

    a, b = (int(v) for v in args.window.split(","))
    ref = args.ref if args.ref is not None else (a + b) // 2
    out = args.out or os.path.join(ROOT, "assets", "plates", f"w{a}_{b}")
    os.makedirs(out, exist_ok=True)

    print(f"[janela] {a}-{b} ({b-a} frames), referencia f{ref}")
    full, half = read_window(args.clip, a, b)
    print(f"[leitura] {len(full)} frames @ {full[0].shape[1]}x{full[0].shape[0]}")

    # 1) campos de movimento em meia-resolucao (fit em 640x360)
    fields = []
    ref_h = half[ref - a]
    for k, h in enumerate(half):
        if abs((k + a) - ref) == 0:
            fields.append(None)
            continue
        f = fit_field(np.float32(ref_h), np.float32(h))
        fields.append(f)
    resid = [0.0 if f is None else f["resid_med"] for f in fields]
    ok = [f is not None or fields[k] is None for k, f in enumerate(fields)]
    print(f"[campos] residuo mediano={np.median(resid):.2f}px  p90={np.percentile(resid,90):.2f}px  falhas={sum(1 for f in fields if f is None)}")

    # 2) estabilizacao em resolucao CHEIA (campo avaliado com escala 2x)
    stab_dir = os.path.join(out, "stab")
    os.makedirs(stab_dir, exist_ok=True)
    scale = full[0].shape[1] / half[0].shape[1]
    prev_c = None
    for k, (fr_full, f) in enumerate(zip(full, fields)):
        idx = a + k
        if f is None:
            st = fr_full
        else:
            st = apply_field(fr_full, f, scale=scale)
        cv2.imwrite(os.path.join(stab_dir, f"s{idx:03d}.png"), st)

    # 3) plate limpo: mediana temporal no referencial do ref, com exclusao de atividade
    stack = []
    for k, f in enumerate(fields):
        st = cv2.imread(os.path.join(stab_dir, f"s{a+k:03d}.png"), cv2.IMREAD_COLOR)
        g = cv2.cvtColor(st, cv2.COLOR_BGR2GRAY)
        stack.append(g)
    S = np.stack(stack).astype(np.float32)
    # atividade local = desvio em relacao a mediana (pombo/sombra)
    med = np.median(S, axis=0)
    dev = np.abs(S - med)
    thr = max(6.0, float(np.median(dev)) * 3.0)
    valid = dev < thr
    cnt = valid.sum(axis=0)
    plate = np.where(cnt > 0, np.where(valid, S, np.nan).astype(np.float32), med)
    with np.errstate(all="ignore"):
        plate = np.nanmedian(np.where(valid, S, np.nan), axis=0)
    plate = np.nan_to_num(plate, nan=0.0)
    if (~(cnt > 0)).any():
        pass
    # onde a cobertura e baixa, usa a mediana simples
    valid_any = cnt >= 3
    plate = np.where(valid_any, plate, med)
    # regiao fantasma (nunca vista): copia o vizinho valido mais proximo —
    # preserva textura real do chao em vez de inventar gradiente
    if (~valid_any).any():
        dist, labels = cv2.distanceTransformWithLabels((~valid_any).astype(np.uint8), cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(valid_any)
        lid = labels[valid_any]
        order = np.argsort(lid)
        lid_s, ys_s, xs_s = lid[order], ys[order], xs[order]
        uniq, first = np.unique(lid_s, return_index=True)
        rep_y, rep_x = ys_s[first], xs_s[first]
        lut = np.zeros(int(labels.max()) + 1, np.int32)
        lut[uniq] = np.arange(len(uniq))
        sel = labels > 0
        j = lut[labels[sel]]
        src_y = np.zeros_like(labels); src_x = np.zeros_like(labels)
        src_y[sel] = rep_y[j]; src_x[sel] = rep_x[j]
        ys2, xs2 = np.nonzero(~valid_any)
        plate[ys2, xs2] = plate[src_y[ys2, xs2], src_x[ys2, xs2]]
        # suaviza somente a regiao preenchida (evita blocos de textura duplicada dura)
        filled = cv2.GaussianBlur(plate.astype(np.float32), (0, 0), 2.5)
        m = np.zeros_like(plate, np.uint8); m[ys2, xs2] = 255
        m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        plate = np.where(m > 0, filled, plate)
    plate_u8 = np.clip(plate, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(out, "plate_clean.png"), plate_u8)
    # mapa de confiabilidade: quantos doadores validos por pixel
    conf = np.clip(cnt / max(1, len(stack)) * 255, 0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(out, "plate_confianca.png"), conf)

    # 4) cor de fundo de plate na base do pombo (para casar cor depois)
    meta = {
        "janela": [a, b],
        "referencia": ref,
        "n_frames": len(full),
        "resolucao": [int(full[0].shape[1]), int(full[0].shape[0])],
        "escala_campo": scale,
        "resid_med_px": round(float(np.median(resid)), 3),
        "resid_p90_px": round(float(np.percentile(resid, 90)), 3),
        "campos_falhos": int(sum(1 for f in fields if f is None)),
        "cobertura_plate_pct": round(float(valid_any.mean() * 100), 2),
        "fantasma_preenchido_pct": round(float((~valid_any).mean() * 100), 2),
        "plate_mediana": float(np.median(plate)),
    }
    json.dump(meta, open(os.path.join(out, "plate.json"), "w"), indent=2, ensure_ascii=False)
    print(f"[plate] cobertura valida={meta['cobertura_plate_pct']}% | mediana={meta['plate_mediana']:.1f}")
    print(f"[ok] {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
