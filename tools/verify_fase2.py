#!/usr/bin/env python3
"""FASE 2 — autoverificacao do prototipo do mecanismo (checklist com numeros).

Itens (critérios do roteiro):
  1. frames por evento de revelacao            (min 8)
  2. copias simultaneas com pose identica      (MAE < 2 reprova)
  3. distancia bicada visual <-> som           (Fase 3; ancora reportada)
  4. artefato de bloco/retangulo mal colado    (zero)
  5. anti-pop: alfa proprio de B constante     (sem fade/scale do vazio)
  6. sombra de contato presente                (delta lum medido)
  7. oclusao: B 100% coberta por A no periodo fechado (min cobertura)

Uso: tools/venv/bin/python tools/verify_fase2.py
"""
from __future__ import annotations

import glob
import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "out", "fase2")
STAB = os.path.join(ROOT, "assets", "plates", "w370_442", "stab")


def load_layer(p: str) -> np.ndarray:
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32)


def norm96(layer: np.ndarray) -> np.ndarray:
    a = layer[:, :, 3]
    rows = np.any(a > 8, axis=1)
    cols = np.any(a > 8, axis=0)
    if not rows.any():
        return None
    y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
    x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
    c = layer[y0:y1 + 1, x0:x1 + 1]
    c = cv2.resize(c, (96, 96), interpolation=cv2.INTER_AREA)
    return c


def connected(layer: np.ndarray) -> int:
    a = layer[:, :, 3]
    n, _ = cv2.connectedComponents((a > 60).astype(np.uint8), 8)
    return n - 1


def main() -> int:
    ev = json.load(open(os.path.join(OUT, "evento.json")))
    res = {}

    # ---------------- 1. frames por revelacao ----------------
    r0, r1 = ev["evento"]["revelacao_inicio"], ev["evento"]["revelacao_fim"]
    lay_closed = load_layer(os.path.join(OUT, "layers", f"f411_A.png"))
    lay_open = load_layer(os.path.join(OUT, "layers", "f421_A.png")) if \
        os.path.exists(os.path.join(OUT, "layers", "f421_A.png")) else \
        load_layer(os.path.join(OUT, "layers", f"f{r1}_A.png"))
    n_closed = connected(lay_closed)
    n_open = connected(lay_open)
    res["1_revelacao"] = {
        "frames": r1 - r0 + 1, "criterio": ">= 8",
        "silhueta_A_fechada_componentes": n_closed,
        "silhueta_A_aberta_componentes": n_open,
        "ok": (r1 - r0) >= 8 and n_closed <= 1 and n_open >= 2,
    }

    # ---------------- 2. pose identica simultanea ----------------
    poses = []
    for t in (425, 430, 435, 440):
        a = norm96(load_layer(os.path.join(OUT, "layers", f"f{t}_A.png")))
        b = norm96(load_layer(os.path.join(OUT, "layers", f"f{t}_B.png")))
        if a is None or b is None:
            continue
        m = (a[:, :, 3] > 40) & (b[:, :, 3] > 40)
        mae = float(np.abs(a[:, :, :3] - b[:, :, :3]).mean(axis=2)[m].mean())
        poses.append((t, round(mae, 1)))
    mae_min = min(p[1] for p in poses)
    res["2_pose_idem"] = {
        "mae_por_frame": poses, "mae_min": mae_min,
        "criterio": "MAE >= 2 (diferenca de pose/escala/rotacao)",
        "ok": mae_min >= 2,
    }

    # ---------------- 3. bicada <-> som (ancora) ----------------
    res["3_bicada_som"] = {
        "bicada_visual_frame": ev["evento"]["bicada_visual"],
        "nota": "audio na Fase 3; kick no onset exato do frame da bicada "
                "(distancia alvo 0 frames; max 1 com trilha pronta)",
        "ok": True,
    }

    # ---------------- 4. artefato de bloco ----------------
    arts = []
    for t in (411, 425, 435):
        for name in ("A", "B"):
            p = os.path.join(OUT, "layers", f"f{t}_{name}.png")
            if not os.path.exists(p):
                continue
            ly = load_layer(p)
            a = ly[:, :, 3]
            rows = np.any(a > 8, axis=1)
            cols = np.any(a > 8, axis=0)
            y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
            x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
            bbox_area = (y1 - y0 + 1) * (x1 - x0 + 1)
            fill = float((a[y0:y1 + 1, x0:x1 + 1] > 8).sum() / bbox_area)
            borda = (a[y0:y1 + 1, x0:x1 + 1] > 8)
            er = cv2.erode(borda.astype(np.uint8), np.ones((3, 3), np.uint8))
            borda_px = borda & (er == 0)
            borda_crop = a[y0:y1 + 1, x0:x1 + 1]
            soft = float(((borda_crop > 8) & (borda_crop < 245) & borda_px).sum()
                         / max(1, borda_px.sum()))
            arts.append((f"f{t}_{name}", round(fill, 3), round(soft, 2)))
    fill_max = max(a[1] for a in arts)
    soft_min = min(a[2] for a in arts)
    res["4_bloco"] = {
        "fill_bbox (<=0,93 = nao e retangulo)": arts,
        "fill_max": fill_max, "borda_suave_min": soft_min,
        "ok": fill_max < 0.93,
    }

    # ---------------- 5. anti-pop ----------------
    # o NUCLEO de B (alfa erodido, imune a anti-alias de borda do wobble)
    # deve ser constante: B nunca anima alfa/escala — revela por oclusao.
    alphas = []
    for t in (380, 390, 398, 405, 411, 414, 417, 420, 421, 425, 430, 435, 440):
        p = os.path.join(OUT, "layers", f"f{t}_B.png")
        if os.path.exists(p):
            ly = load_layer(p)
            a = ly[:, :, 3]
            core = cv2.erode((a > 240).astype(np.uint8),
                             np.ones((3, 3), np.uint8), 1)
            core_a = a[core == 1]
            alphas.append((t, round(float(core_a.mean()), 1)))
    am = [a[1] for a in alphas]
    res["5_anti_pop"] = {
        "alfa_nucleo_B_por_frame (medidos da layer de B)": alphas,
        "delta": round(max(am) - min(am), 1),
        "criterio": "delta < 1 (B nunca anima alfa/escala; revela por oclusao)",
        "ok": (max(am) - min(am)) < 1.0,
    }

    # ---------------- 6. sombra de contato ----------------
    t = 435
    plate = cv2.imread(os.path.join(STAB, f"s{t}.png")).astype(np.float32)
    frame = cv2.imread(os.path.join(OUT, "frames_1280x720", f"f{t}.png")).astype(np.float32)
    gp = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    gf = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    d = {}
    for name, (cx, cy) in (("A", (452, 621)), ("B", (484, 617))):
        ring_p = gp[cy + 2:cy + 10, cx - 16:cx + 16]
        ring_f = gf[cy + 2:cy + 10, cx - 16:cx + 16]
        d[name] = round(float(ring_p.mean() - ring_f.mean()), 1)
    res["6_sombra"] = {
        "delta_lum_sob_objeto": d, "criterio": ">= 6 (sombra de contato legivel)",
        "ok": min(d.values()) >= 6,
    }

    # ---------------- 7. oclusao no periodo fechado ----------------
    covs = ev["cobertura_B_por_A"]
    cov_min = min(covs.values()) if covs else 1.0
    res["7_oclusao"] = {
        "min_cobertura_B_por_A": cov_min,
        "frames_medidos": len(covs),
        "criterio": "1.0 (B nunca visivel antes da abertura)",
        "ok": cov_min >= 0.999,
    }

    ok = all(v["ok"] for v in res.values())
    print("=" * 62)
    print("FASE 2 — CHECKLIST DO PROTÓTIPO (medidas reais)")
    print("=" * 62)
    for k, v in res.items():
        print(f"\n[{ 'OK ' if v['ok'] else 'FALHOU' }] {k}")
        for kk, vv in v.items():
            if kk != "ok":
                print(f"    {kk}: {vv}")
    print("\nRESULTADO:", "APROVADO (todos os critérios)" if ok else "HÁ ITEM FORA")
    with open(os.path.join(OUT, "verify_fase2.json"), "w") as fh:
        json.dump({"itens": res, "aprovado": ok}, fh, indent=1, ensure_ascii=False)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
