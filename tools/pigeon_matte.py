#!/usr/bin/env python3
"""FASE 1 — matting por frame do pombo (pipeline classico, CPU-only, sem download).

Tecnica obrigatoria nº 1 do roteiro: "matting do pombo e das migalhas por frame".

RESTRICAO DE AMBIENTE (documentada em docs/fase1-assets.md): este sandbox nao tem
acesso a GitHub releases / HuggingFace / pytorch.org / storage.googleapis, entao
nao existe caminho para baixar pesos de u2net/SAM. O matting aqui e um pipeline
CLASSICO de producao, sem modelo:

  1. leitura em meia-resolucao e alinhamento do chao por correlacao de fase
     validada (rejeita saltos/erros grossos);
  2. deteccao de CORTES do plano (mudanca global) para nunca doar pixel de um
     plano para outro;
  3. activity_mask: o que se move entre frames vizinhos alinhados = pombo + sombra
     (nao precisa de plate);
  4. PLATE por doacao espaco-temporal: para cada pixel, pega o valor real do chao
     de um frame em que aquela regiao NAO esta ocluida; onde o chao nunca aparece
     (pombo parado sobre ele, ex.: bicando) preenche por vizinho mais proximo
     (distance transform), preservando a textura da propria cena;
  5. separacao SOMBRA vs CORPO: sombra de contato escurece o chao mas PRESERVA a
     textura (gradientes acompanham o plate dentro da mancha); corpo quebra isso;
  6. trimap + matting alfa (pymatting, closed-form) para borda suave real.

Saida: alpha 8-bit em resolucao CHEIA, recortado na bbox, + JSON de metadados.

Uso:
  tools/venv/bin/python tools/pigeon_matte.py --probe 60,400,470
  tools/venv/bin/python tools/pigeon_matte.py --demo 380,460
  tools/venv/bin/python tools/pigeon_matte.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motion import apply_field, fit_field, maps_in_box  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIP_A = os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4")
OUT_DIR = os.path.join(ROOT, "assets", "mattes", "A")
PROBE_DIR = os.path.join(ROOT, "assets", "probe")
CACHE_DIR = os.path.join(ROOT, "assets", "cache")

HALF_W = 640          # largura de trabalho (0.5x)
DIFF_THR = 20         # limiar de diferenca vs. plate
MIN_AREA = 250        # area minima do pombo (px em meia-resolucao)
SHADOW_CORR = 0.55    # correlacao de gradiente p/ classificar sombra
SHADOW_RATIO = 0.90   # razao de luminancia (sombra escurece, nao pinta)
TRIMAP_ERODE = 3
TRIMAP_DILATE = 5
CROP_PAD = 20
CUT_THR = 0.22        # fracao de pixels em movimento = corte de plano


# ---------------------------------------------------------------------------
def open_clip(path: str):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"nao consegui abrir {path}")
    return cap


def frame_count(path: str) -> int:
    cap = open_clip(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def read_frame(path: str, idx: int) -> np.ndarray:
    cap = open_clip(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"frame {idx} ilegivel")
    return f


def fill_holes(binary: np.ndarray) -> np.ndarray:
    """Preenche buracos internos de uma mascara binaria (robusto a tocar a borda)."""
    inv = (binary == 0).astype(np.uint8)
    n, lab = cv2.connectedComponents(inv, connectivity=4)
    if n <= 1:
        return binary
    border = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    border.discard(0)
    holes = np.isin(lab, list(border), invert=True) & (inv == 1)
    return np.clip(binary.astype(np.uint8) + holes.astype(np.uint8), 0, 1)


def gray_small(bgr: np.ndarray, w: int = HALF_W) -> np.ndarray:
    h = int(round(bgr.shape[0] * w / bgr.shape[1]))
    return cv2.cvtColor(cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)


class Clip:
    """Alinhamento de chao, plate por doacao espaco-temporal e matting."""

    def __init__(self, path: str, cache_dir: str = CACHE_DIR):
        self.path = path
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        cap = open_clip(path)
        self.W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.n = frame_count(path)
        self._grays: np.ndarray | None = None
        self._shifts: np.ndarray | None = None
        self._shots: list[tuple[int, int]] | None = None
        self._act: dict[int, np.ndarray] = {}
        self._plates: dict[int, np.ndarray] = {}
        self._fields: dict[tuple[int, int], dict | None] = {}
        self._plate_used = 0
        self.ground_frac = 0.5  # faixa inferior usada para medir o movimento do chao

    # --- dados base --------------------------------------------------------
    def grays(self) -> np.ndarray:
        if self._grays is None:
            f = os.path.join(self.cache_dir, "grays.npy")
            if os.path.exists(f):
                self._grays = np.load(f)
            else:
                print(f"[leitura] {self.n} frames a {HALF_W}px...", flush=True)
                cap = open_clip(self.path)
                fr = []
                while True:
                    ok, fr_ = cap.read()
                    if not ok:
                        break
                    fr.append(gray_small(fr_))
                cap.release()
                self._grays = np.stack(fr)
                np.save(f, self._grays)
        return self._grays

    def ground_roi(self):
        g = self.grays()
        h = g.shape[1]
        return slice(int(h * (1 - self.ground_frac)), h), slice(0, g.shape[2])

    # --- 1. campo de movimento (paralaxe) ----------------------------------
    def field(self, i: int, j: int) -> dict | None:
        """Campo que leva o frame j para o referencial do frame i (meia-resolucao)."""
        key = (i, j)
        if key in self._fields:
            return self._fields[key]
        f = os.path.join(self.cache_dir, f"field_{i:03d}_{j:03d}.npz")
        if os.path.exists(f):
            d = np.load(f)
            field = {
                "coef_dx": d["dx"], "coef_dy": d["dy"], "deg": int(d["deg"]),
                "n_in": int(d["nin"]), "n_total": int(d["ntot"]),
                "resid_med": float(d["resid"]), "shape": tuple(int(v) for v in d["shape"]),
            }
        else:
            g = self.grays()
            field = fit_field(np.float32(g[i]), np.float32(g[j]))
            if field is not None:
                np.savez_compressed(
                    f, dx=field["coef_dx"], dy=field["coef_dy"], deg=field["deg"],
                    nin=field["n_in"], ntot=field["n_total"], resid=field["resid_med"],
                    shape=np.array(field["shape"]),
                )
        self._fields[key] = field
        return field

    def aligned_half(self, i: int, j: int, img: np.ndarray | None = None) -> np.ndarray:
        g = self.grays() if img is None else img
        if i == j:
            return g[j]
        f = self.field(i, j)
        if f is None:
            return g[j]
        return apply_field(g[j], f, scale=1.0)

    # --- 3. mascara de atividade (pombo + sombra), sem plate ---------------
    def activity_mask(self, i: int, lag: int = 2, thr: int = 16, fast: bool = False) -> np.ndarray:
        if i in self._act and not fast:
            return self._act[i]
        a = self.grays()[i]
        b = self.aligned_half(i, max(0, i - lag))
        c = self.aligned_half(i, min(self.n - 1, i + lag))
        d = np.maximum(cv2.absdiff(a, b), cv2.absdiff(a, c)).astype(np.float32)
        # PASSA-ALTA: o pombo (e sua sombra) sao compactos; o erro de paralaxe nas
        # bordas do quadro e de larga escala. Subtrair o nivel local suprime o fundo.
        d = np.clip(d - cv2.blur(d, (101, 101)), 0, 255)
        m = (d > thr).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), iterations=2)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        if n > 1:
            h, w = m.shape
            lim = 0.15 * h * w
            comps = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] <= lim]
            if not comps:
                comps = list(range(1, n))
            k = max(comps, key=lambda kk: stats[kk, cv2.CC_STAT_AREA])
            keep = (lab == k).astype(np.uint8)
            keep = fill_holes(keep)
            m = keep
        if not fast:
            m = cv2.dilate(m, np.ones((9, 9), np.uint8), iterations=1)
            self._act[i] = m
        return m

    def bird_box_half(self, i: int) -> tuple[int, int, int, int]:
        """bbox (x0,y0,x1,y1) do pombo em meia-resolucao, com folga."""
        m = self.activity_mask(i)
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            h, w = m.shape
            return 0, 0, w, h
        pad = 24
        h, w = m.shape
        return max(0, xs.min() - pad), max(0, ys.min() - pad), min(w, xs.max() + pad), min(h, ys.max() + pad)

    # --- 4. plate por doacao espaco-temporal -------------------------------
    def plate(self, i: int, half_window: int = 20, stride: int = 4) -> np.ndarray:
        """Chao limpo no referencial do frame i (meia-resolucao, float32).

        Fora da caixa do pombo: mediana temporal dos doadores alinhados (rapido e
        correto). Dentro da caixa: media dos doadores apenas onde NAO ha atividade
        (pombo/sombra), ou seja, textura real do chao; onde o chao nunca aparece,
        copia o vizinho valido mais proximo.
        """
        if i in self._plates:
            return self._plates[i]
        cache = os.path.join(self.cache_dir, f"plateH_{i:03d}.png")
        if os.path.exists(cache):
            p = cv2.imread(cache, cv2.IMREAD_GRAYSCALE).astype(np.float32)
            self._plates[i] = p
            return p
        g = self.grays()
        H, W = g.shape[1], g.shape[2]
        x0, y0, x1, y1 = self.bird_box_half(i)
        idxs = [j for j in range(max(0, i - half_window), min(self.n, i + half_window + 1))]
        idxs = [j for j in idxs if (j - i) % stride == 0]
        if i not in idxs:
            idxs.append(i)
        idxs.sort(key=lambda j: abs(j - i))
        stack = []
        act = []
        for j in idxs:
            f = self.field(i, j) if j != i else None
            if j != i and f is None:
                continue
            gj = g[j] if f is None else apply_field(g[j], f, scale=1.0)
            aj = self.activity_mask(j)
            if f is not None:
                aj = apply_field((aj * 255).astype(np.uint8), f, scale=1.0) > 127
            else:
                aj = aj.astype(bool)
            stack.append(gj)
            act.append(aj)
        if not stack:
            return g[i].astype(np.float32)
        plate = np.median(np.stack(stack).astype(np.float32), axis=0)
        # dentro da caixa: doacao com exclusao de atividade
        A = np.stack(act)[:, y0:y1, x0:x1]
        S = np.stack(stack)[:, y0:y1, x0:x1].astype(np.float32)
        valid = ~A
        cnt = valid.sum(axis=0)
        acc = np.where(valid, S, 0.0).sum(axis=0)
        box = np.zeros_like(plate)
        have = cnt > 0
        box[y0:y1, x0:x1] = np.where(have, acc / np.maximum(cnt, 1), 0.0)
        if (~have).any():
            filled = box[y0:y1, x0:x1].copy()
            m = have.astype(np.uint8)
            if m.any():
                inv = 1 - m
                _, labels = cv2.distanceTransformWithLabels(inv, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
                ys, xs = np.nonzero(have)
                lid = labels[have]
                order = np.argsort(lid)
                lid_s = lid[order]
                uniq, first = np.unique(lid_s, return_index=True)
                rep_y = ys[order][first]
                rep_x = xs[order][first]
                lut = np.zeros(int(labels.max()) + 1, np.int32)
                lut[uniq] = np.arange(len(uniq))
                sel = labels > 0
                j2 = lut[labels[sel]]
                src_y = np.zeros_like(labels)
                src_x = np.zeros_like(labels)
                src_y[sel] = rep_y[j2]
                src_x[sel] = rep_x[j2]
                ys2, xs2 = np.nonzero(~have)
                filled[ys2, xs2] = filled[src_y[ys2, xs2], src_x[ys2, xs2]]
            box[y0:y1, x0:x1] = filled
        plate[y0:y1, x0:x1] = box[y0:y1, x0:x1]
        plate = np.clip(plate, 0, 255).astype(np.uint8).astype(np.float32)
        cv2.imwrite(cache, plate.astype(np.uint8))
        self._plates[i] = plate
        self._plate_used = len(stack)
        return plate

    def plate_full(self, i: int) -> np.ndarray:
        return cv2.resize(self.plate(i), (self.W, self.H), interpolation=cv2.INTER_LINEAR)

    # --- 5. sombra vs corpo ------------------------------------------------
    def shadow_mask(self, g: np.ndarray, p: np.ndarray) -> np.ndarray:
        """1 = escurecimento que preserva textura (sombra de contato)."""
        k = np.ones((5, 5), np.float32) / 25.0
        f = g.astype(np.float32)
        p = p.astype(np.float32)

        def grads(img):
            return cv2.Sobel(img, cv2.CV_32F, 1, 0, 3), cv2.Sobel(img, cv2.CV_32F, 0, 1, 3)

        fx, fy = grads(f)
        px, py = grads(p)
        fx2, px2 = cv2.filter2D(fx * fx, -1, k), cv2.filter2D(px * px, -1, k)
        fy2, py2 = cv2.filter2D(fy * fy, -1, k), cv2.filter2D(py * py, -1, k)
        cov = cv2.filter2D(fx * px + fy * py, -1, k) - (
            cv2.filter2D(fx, -1, k) * cv2.filter2D(px, -1, k) + cv2.filter2D(fy, -1, k) * cv2.filter2D(py, -1, k)
        )
        den = np.sqrt(np.maximum(fx2 + fy2, 1e-6) * np.maximum(px2 + py2, 1e-6))
        corr = cov / den
        ratio = f / np.maximum(p, 1e-3)
        return ((corr > SHADOW_CORR) & (ratio < SHADOW_RATIO) & (ratio > 0.4)).astype(np.uint8)

    # --- 6. matting --------------------------------------------------------
    def body_mask(self, i: int, prev_c=None):
        """Mascara do corpo (1) do pombo em MEIA-resolucao + frame full-res."""
        bgr = read_frame(self.path, i)
        g_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        g = gray_small(bgr)
        p = self.plate(i)
        d = cv2.absdiff(g, p.astype(np.uint8))
        d = cv2.GaussianBlur(d, (5, 5), 0)
        m = (d > DIFF_THR).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), 2)
        m = (m & (1 - self.shadow_mask(g, p))).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), 1)
        n, lab, stats, cents = cv2.connectedComponentsWithStats(m, 8)
        best, best_score = None, -1e18
        for k in range(1, n):
            area = stats[k, cv2.CC_STAT_AREA]
            if area < MIN_AREA:
                continue
            cx, cy = cents[k]
            pen = 0.0 if prev_c is None else 6.0 * float(np.hypot(cx - prev_c[0], cy - prev_c[1]))
            sc = float(area) - pen
            if sc > best_score:
                best, best_score = k, sc
        if best is None:
            return np.zeros_like(m), bgr, p
        comp = (lab == best).astype(np.uint8)
        comp = fill_holes(comp)
        # sanidade: mascara absurda (fundo inteiro entrando) -> invalida
        h, w = comp.shape
        bx, by, bw, bh = cv2.boundingRect(comp)
        if comp.sum() > 0.22 * h * w or (bw > 0.95 * w and bh > 0.90 * h):
            comp = np.zeros_like(comp)
        return comp, bgr, g_full, p

    def matte(self, bgr: np.ndarray, mask_half: np.ndarray, method: str = "cf"):
        """Matting alfa em resolucao CHEIA a partir da mascara (meia-resolucao)."""
        import pymatting

        H, W = bgr.shape[:2]
        mask_full = cv2.resize(mask_half * 255, (W, H), interpolation=cv2.INTER_NEAREST)
        ys, xs = np.nonzero(mask_full)
        if len(ys) == 0:
            return None
        y0, y1 = max(0, ys.min() - CROP_PAD), min(H, ys.max() + CROP_PAD + 1)
        x0, x1 = max(0, xs.min() - CROP_PAD), min(W, xs.max() + CROP_PAD + 1)
        crop, mk = bgr[y0:y1, x0:x1].copy(), (mask_full[y0:y1, x0:x1] > 127).astype(np.uint8)
        # suaviza a borda da mascara (vem de meia-resolucao) antes do trimap
        mk = cv2.resize(cv2.resize(mk * 255, (mk.shape[1] // 2, mk.shape[0] // 2), interpolation=cv2.INTER_AREA), (mk.shape[1], mk.shape[0]), interpolation=cv2.INTER_LINEAR)
        mk = (mk > 127).astype(np.uint8)
        ke = np.ones((TRIMAP_ERODE * 2 + 1,) * 2, np.uint8)
        kd = np.ones((TRIMAP_DILATE * 2 + 1,) * 2, np.uint8)
        fg = cv2.erode(mk, ke, 1)
        bgd = 1 - cv2.dilate(mk, kd, 1)
        trimap = np.full(mk.shape, 0.5, np.float32)
        trimap[bgd.astype(bool)] = 0.0
        trimap[fg.astype(bool)] = 1.0
        if not (trimap == 1.0).any():
            trimap[mk.astype(bool)] = 1.0
        if not (trimap == 0.0).any():
            return None
        img = crop.astype(np.float64) / 255.0
        est = {
            "cf": pymatting.estimate_alpha_cf,
            "knn": pymatting.estimate_alpha_knn,
            "lbdm": pymatting.estimate_alpha_lbdm,
        }[method]
        alpha = np.clip(est(img, trimap), 0, 1)
        return crop, (alpha * 255).astype(np.uint8), (x0, y0, x1, y1), trimap


# ---------------------------------------------------------------------------
def probe(frames: list[int], method: str = "cf", tag: str = "matte") -> None:
    clip = Clip(CLIP_A)
    os.makedirs(PROBE_DIR, exist_ok=True)
    for i in frames:
        t0 = time.time()
        mask, bgr, _gfull, _p = clip.body_mask(i)
        t_mask = time.time() - t0
        res = clip.matte(bgr, mask, method)
        if res is None:
            print(f"f{i}: sem mascara")
            continue
        crop, alpha, bbox, _ = res
        x0, y0, x1, y1 = bbox
        soft = int(((alpha > 10) & (alpha < 245)).sum())
        solid = int((alpha > 128).sum())
        print(
            f"f{i}: mask {t_mask:.2f}s | bbox={bbox} | corpo={solid}px | borda_suave={soft}px "
            f"({soft/max(solid,1)*100:.1f}%) | doadores={clip._plate_used}",
            flush=True,
        )
        comp = crop.copy()
        comp[alpha < 128] = (comp[alpha < 128] * 0.15 + np.array([200, 0, 200]) * 0.85).astype(np.uint8)
        vis = np.hstack([crop, cv2.cvtColor(alpha, cv2.COLOR_GRAY2BGR), comp])
        cv2.imwrite(os.path.join(PROBE_DIR, f"{tag}_f{i:03d}.png"), vis)


def run_all(method: str = "cf", out_dir: str = OUT_DIR, rng: tuple[int, int] | None = None) -> None:
    clip = Clip(CLIP_A)
    os.makedirs(out_dir, exist_ok=True)
    a, b = rng if rng else (0, clip.n)
    meta, t0 = [], time.time()
    for i in range(a, b):
        mask, bgr, _gfull, _p = clip.body_mask(i)
        res = clip.matte(bgr, mask, method)
        if res is None:
            meta.append({"frame": i, "ok": False})
            continue
        _, alpha, bbox, _ = res
        cv2.imwrite(os.path.join(out_dir, f"a{i:03d}.png"), alpha)
        meta.append(
            {
                "frame": i,
                "ok": True,
                "bbox": [int(v) for v in bbox],
                "cov_pct": round(float((alpha > 128).mean() * 100), 2),
                "soft_px": int(((alpha > 10) & (alpha < 245)).sum()),
                "doadores": clip._plate_used,
            }
        )
        if (i - a) % 10 == 0:
            el = time.time() - t0
            done = i - a + 1
            print(f"  f{i}/{b} {el:.0f}s eta {el/done*(b-a-done):.0f}s", flush=True)
    json.dump(
        {"clip": os.path.basename(CLIP_A), "method": method, "range": [a, b], "frames": meta},
        open(os.path.join(out_dir, "mattes.json"), "w"),
        indent=2,
    )
    ok = sum(1 for m in meta if m["ok"])
    print(f"[ok] {ok}/{b-a} mattes em {time.time()-t0:.0f}s -> {os.path.relpath(out_dir, ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=str, help="frames separados por virgula")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--range", type=str, help="a,b (meia-aberto)")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--method", default="cf", choices=["cf", "knn", "lbdm"])
    ap.add_argument("--tag", default="matte")
    a = ap.parse_args()
    if a.probe:
        probe([int(x) for x in a.probe.split(",")], method=a.method, tag=a.tag)
    elif a.all:
        run_all(method=a.method)
    elif a.range:
        x, y = (int(v) for v in a.range.split(","))
        run_all(method=a.method, rng=(x, y))
    elif a.shots:
        Clip(CLIP_A).shots()
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
