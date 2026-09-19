#!/usr/bin/env python3
"""FASE 1 — medicao objetiva do material de origem.

Objetivo: responder com numeros, antes de qualquer asset:
  1. o material tem evento de BICADA (bico indo ao chao)?
  2. quantos eventos, em que frames, com que duracao?
  3. o material tem ciclo de CAMINHADA utilizavel?
  4. onde esta o ponto de contato das patas (para estabilizacao, tecnica 2)?

Metodo (sem inventar): compensa a deriva de camera alinhando todos os frames por
translacao subpixel; constroi fundo por mediana temporal; segmenta a silhueta do
pombo por diferenca; extrai altura/centroide/linha de contato por frame; detecta
minimos locais de altura (cabeca baixa = bicada) com proeminencia minima.

Uso: tools/venv/bin/python tools/analyze_pecking.py
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIP = os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4")
OUT = os.path.join(ROOT, "assets", "analysis")

FPS = 24.0
WORK_W = 640  # resolucao de trabalho da analise


def load_gray(path: str, w: int = WORK_W) -> tuple[list[np.ndarray], float]:
    cap = cv2.VideoCapture(path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    scale = w / W
    H = int(round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * scale))
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (w, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        fr.append(g)
    cap.release()
    return fr, scale


def align_translations(frames: list[np.ndarray], ref_idx: int = 0) -> np.ndarray:
    """Translacao acumulada de cada frame em relacao ao frame de referencia."""
    ref = np.float32(frames[ref_idx])
    shifts = np.zeros((len(frames), 2), np.float64)
    prev = ref
    acc = np.zeros(2)
    for i, f in enumerate(frames):
        cur = np.float32(f)
        (dx, dy), _ = cv2.phaseCorrelate(prev, cur)
        acc = acc + np.array([dx, dy])
        shifts[i] = acc
        prev = cur
    return shifts - shifts[ref_idx]


def warp_to_ref(img: np.ndarray, shift: np.ndarray) -> np.ndarray:
    M = np.float32([[1, 0, -shift[0]], [0, 1, -shift[1]]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def segment_bird(aligned: list[np.ndarray], shifts: np.ndarray) -> tuple[list[np.ndarray], np.ndarray]:
    """Silhueta do pombo por mediana temporal + diferenca, com componente conexa rastreada."""
    stack = np.stack(aligned).astype(np.float32)
    bg = np.median(stack, axis=0)
    birds = []
    prev_c = None
    for i, a in enumerate(aligned):
        d = np.abs(a.astype(np.float32) - bg)
        m = (d > 22).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
        n, lab, stats, cents = cv2.connectedComponentsWithStats(m, 8)
        if n <= 1:
            birds.append(np.zeros_like(m))
            continue
        # escolhe componente: maior area, com preferencia pela proximidade do centroide anterior
        idx = list(range(1, n))
        def score(k):
            area = stats[k, cv2.CC_STAT_AREA]
            if prev_c is None:
                return area
            cx, cy = cents[k]
            dist = np.hypot(cx - prev_c[0], cy - prev_c[1])
            return area - 6.0 * dist
        best = max(idx, key=score)
        comp = (lab == best).astype(np.uint8)
        if stats[best, cv2.CC_STAT_AREA] < 150:
            comp = np.zeros_like(m)
        birds.append(comp)
        if comp.any():
            prev_c = cents[best]
    return birds, bg


def silhouette_metrics(mask: np.ndarray, min_area: int = 150) -> dict | None:
    ys, xs = np.nonzero(mask)
    if len(ys) < min_area:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h = y1 - y0 + 1
    w = x1 - x0 + 1
    # altura relativa da "massa alta" (cabeca/pescoco): centroide da faixa superior
    band = mask[y0 : y0 + max(1, h // 4), :]
    bys, bxs = np.nonzero(band)
    head_y = float(bys.mean() + y0) if len(bys) else float("nan")
    return {
        "bbox": [int(x0), int(y0), int(w), int(h)],
        "area": int(len(ys)),
        "altura": int(h),
        "largura": int(w),
        "topo": int(y0),
        "base": int(y1),
        "centroide_y": float(ys.mean()),
        "cabeca_y": head_y,
        "razao_aspecto": round(w / h, 3),
    }


def movavg(x: np.ndarray, k: int) -> np.ndarray:
    if k % 2 == 0:
        k += 1
    pad = k // 2
    xp = np.pad(x, pad, mode="edge")
    ker = np.ones(k) / k
    return np.convolve(xp, ker, mode="valid")


def find_minima(v: np.ndarray, prominence: float, min_dist: int = 8) -> list[int]:
    """Minimos locais com proeminencia minima e distancia minima."""
    idx = []
    order = np.argsort(v)
    taken = np.zeros(len(v), bool)
    for i in order:
        if taken[max(0, i - min_dist) : i + min_dist + 1].any():
            continue
        # proeminencia: diferenca para o maior pico entre vizinhos
        left = v[max(0, i - 60) : i + 1].max()
        right = v[i : i + 61].max()
        prom = min(left, right) - v[i]
        if prom >= prominence and 0 < i < len(v) - 1:
            taken[i] = True
            idx.append(int(i))
    return sorted(idx)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    print(f"[1] lendo {os.path.basename(CLIP)} em {WORK_W}px de largura...")
    frames, scale = load_gray(CLIP)
    print(f"    {len(frames)} frames @ {scale:.3f} de escala")

    print("[2] alinhando (compensacao de deriva de camera)...")
    shifts = align_translations(frames)
    drift = shifts[-1] - shifts[0]
    print(f"    deriva total: dx={drift[0]:.1f}px dy={drift[1]:.1f}px ({drift[0]/scale:.0f}px em 1280)")

    print("[3] segmentando silhueta do pombo...")
    aligned = [warp_to_ref(f, s) for f, s in zip(frames, shifts)]
    birds, bg = segment_bird(aligned, shifts)
    cv2.imwrite(os.path.join(OUT, "bg_mediana.png"), bg.astype(np.uint8))

    mets = []
    for i, m in enumerate(birds):
        d = silhouette_metrics(m)
        mets.append(d)
    valid = [i for i, d in enumerate(mets) if d]
    print(f"    frames com silhueta valida: {len(valid)}/{len(mets)}")

    h = np.array([mets[i]["altura"] if mets[i] else np.nan for i in range(len(mets))], float)
    hd = np.array([mets[i]["cabeca_y"] if mets[i] else np.nan for i in range(len(mets))], float)
    base = np.array([mets[i]["base"] if mets[i] else np.nan for i in range(len(mets))], float)

    # interpola nan
    for arr in (h, hd, base):
        ok = ~np.isnan(arr)
        arr[:] = np.interp(np.arange(len(arr)), np.nonzero(ok)[0], arr[ok])

    # DETREND: o pombo muda de escala (aproxima) -> normaliza altura pelo trend
    trend = movavg(h, 61)
    h_n = h / trend
    trend_hd = movavg(hd, 61)
    hd_n = hd - trend_hd  # deslocamento da cabeca em relacao ao proprio trend
    trend_b = movavg(base, 61)

    # bicada = cabeca muito abaixo do trend E base (chao) estavel
    peaks = find_minima(hd_n, prominence=6.0, min_dist=10)
    print(f"\n[4] candidatos a BICADA (cabeca descendo >=6px do trend): {len(peaks)}")
    events = []
    for i in peaks:
        # duracao: quanto tempo fica abaixo de metade da proeminencia
        depth = hd_n[i]
        thr = depth / 2
        a = i
        while a > 0 and hd_n[a] < thr:
            a -= 1
        b = i
        while b < len(hd_n) - 1 and hd_n[b] < thr:
            b += 1
        events.append(
            {
                "frame": int(i),
                "t_s": round(i / FPS, 3),
                "profundidade_px": round(float(-depth), 1),
                "duracao_frames": int(b - a + 1),
                "inicio": int(a),
                "fim": int(b),
                "altura_relativa": round(float(h_n[i]), 3),
            }
        )
    for e in events:
        print(
            f"    f{e['frame']:3d} ({e['t_s']:5.2f}s)  prof={e['profundidade_px']:4.1f}px  "
            f"dur={e['duracao_frames']:2d}f  altura_rel={e['altura_relativa']:.3f}"
        )

    # CAMINHADA: variacao de largura/aspecto indica passada; conta oscilacoes
    w_arr = np.array([mets[i]["largura"] if mets[i] else np.nan for i in range(len(mets))], float)
    ok = ~np.isnan(w_arr)
    w_arr[:] = np.interp(np.arange(len(w_arr)), np.nonzero(ok)[0], w_arr[ok])
    w_n = w_arr / movavg(w_arr, 61)
    # picos locais de comprimento = passada
    steps = find_minima(-w_n, prominence=0.02, min_dist=8)
    print(f"\n[5] picos de 'alongamento' (passada/ciclo): {len(steps)}")
    if steps:
        diffs = np.diff(steps)
        print(f"    intervalo entre picos: mediana={np.median(diffs):.0f}f  min={diffs.min()}  max={diffs.max()}")
        print(f"    => ciclo de caminhada de ~{np.median(diffs)/FPS:.2f}s" if len(diffs) else "")

    # ponto de contato das patas: linha da base em frames de pata plantada
    print("\n[6] linha de contato (base da silhueta) — medicao para estabilizacao:")
    print(f"    base media={base.mean():.1f}px  desvio={base.std():.1f}px  (resolucao {WORK_W}px)")
    q = np.percentile(base, [10, 50, 90])
    print(f"    percentis 10/50/90 = {q[0]:.1f} / {q[1]:.1f} / {q[2]:.1f}")

    json.dump(
        {
            "fps": FPS,
            "frames": len(frames),
            "escala_analise": round(scale, 4),
            "deriva_total_px": [round(float(drift[0]), 1), round(float(drift[1]), 1)],
            "frames_silhueta_valida": len(valid),
            "bicadas": events,
            "n_bicadas": len(events),
            "picos_passada": [int(s) for s in steps],
            "ciclo_mediano_frames": float(np.median(np.diff(steps))) if len(steps) > 1 else None,
            "base_contato": {"media": round(float(base.mean()), 1), "desvio": round(float(base.std()), 1)},
            "series": {
                "altura": [round(float(v), 2) for v in h],
                "cabeca_detrend": [round(float(v), 2) for v in hd_n],
                "largura_norm": [round(float(v), 4) for v in w_n],
            },
        },
        open(os.path.join(OUT, "pecking.json"), "w"),
        indent=2,
    )

    # grafico simples (sem matplotlib): curva de cabeca + marcas de bicada
    Hc, Wc = 240, 1200
    chart = np.full((Hc, Wc, 3), 255, np.uint8)
    lo, hi = float(np.nanmin(hd_n)), float(np.nanmax(hd_n))
    rng = hi - lo or 1
    pts = [(int(i / len(hd_n) * (Wc - 1)), int((v - lo) / rng * (Hc - 30)) + 15) for i, v in enumerate(hd_n)]
    for a, b in zip(pts, pts[1:]):
        cv2.line(chart, a, b, (40, 40, 200), 1)
    for e in events:
        x = int(e["frame"] / len(hd_n) * (Wc - 1))
        cv2.line(chart, (x, 0), (x, Hc), (0, 160, 0), 1)
        cv2.putText(chart, str(e["frame"]), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 100, 0), 1)
    cv2.imwrite(os.path.join(OUT, "curva_cabeca.png"), chart)
    print("\n[ok] assets/analysis/{pecking.json, curva_cabeca.png, bg_mediana.png}")


if __name__ == "__main__":
    main()
