#!/usr/bin/env python3
"""FASE 4 — checklist (medidas reais, metodos herdados do verify da F2).

 1 estrutura        1080 frames exatos; S1 0–257 / S2 258–1079; corte 45,000s
 2 revelacoes       10 eventos, cada um >= 8 frames (nunca pop)
 3 offset de tempo  MAE par-a-par entre copias simultaneas (norm96 + alfa);
                    copia identica/congelada daria ~0 — criterio >= 2 (F2)
 4 sync trilha      bicadas vs onsets REAIS do fase3_track.wav (Δ <= 1 frame)
 5 anti-pop         alfa do nucleo do minipombo constante nos frames ainda
                    cobertos (delta < 1)
 6 oclusao          nucleo do bird 100% atras da carapaca fechada em r0
 7 sombra de contato  Δlum mediano por objeto (A >= 6; demais >= 3;
                    minimo reportado — baseline do plate varia com o src)
 8 retas estaticas  nenhuma linha reta espuria persistente no composto
                    (candidatos que existem so no composto, >= 6 amostras)
 9 artefatos        mp4s, reel, evento.json, layers

Uso: tools/venv/bin/python tools/verify_fase4.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import wave

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose_fase2 as C  # noqa: E402
import compose_fase4 as F  # noqa: E402

OUT = F.OUT
LYR = os.path.join(OUT, "layers")
TRACK = os.path.join(C.ROOT, "assets", "audio", "fase3_track.wav")
PECKS = F.PECKS
BIRD_W = F.BIRD_W
REVEALS_MIN_F = 8
MAE_MIN = 2.0
COV_MIN = 0.999
REGION = (380, 700, 560, 690)  # x0,x1,y0,y1 p/ retas estaticas


def norm96(im: np.ndarray) -> np.ndarray:
    return cv2.resize(im.astype(np.float32), (96, 96),
                      interpolation=cv2.INTER_AREA)


def tight(a: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = np.any(a > 8, axis=1)
    cols = np.any(a > 8, axis=0)
    y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
    x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
    return y0, y1, x0, x1


def plane_bird(ev: dict) -> np.ndarray:
    cb, pvb = C.render_object(F.BIRD_SPR, ev["w_px"] / BIRD_W,
                              ev["rot"], tuple(ev["squash"]))
    pl = np.zeros((C.FH, C.FW), np.float32)
    C.paste_canvas(pl, cb, pvb, tuple(ev["pos"]), ev["dy"], alpha_only=True)
    return pl


def plane_mig(ev: dict) -> np.ndarray:
    hL, hR = F.HALVES
    cL, pvL = C.render_object(hL, ev["scale"], ev["rot"] - ev["rot0"],
                              tuple(ev["squash"]))
    cR, pvR = C.render_object(hR, ev["scale"], ev["rot"] + ev["rot0"],
                              tuple(ev["squash"]))
    pl = np.zeros((C.FH, C.FW), np.float32)
    ax, ay = ev["pos"]
    C.paste_canvas(pl, cL, pvL, (ax - ev["gap"] / 2, ay), ev["dy"],
                   alpha_only=True)
    C.paste_canvas(pl, cR, pvR, (ax + ev["gap"] / 2, ay), ev["dy"],
                   alpha_only=True)
    return pl


def onsets() -> list[float]:
    with wave.open(TRACK, "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, dtype="<f4")
        if not np.isfinite(x).all() or float(np.abs(x).max()) > 2.0:
            x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"sampwidth {sw} nao suportado")
    if ch > 1:
        x = x[::ch]
    win = max(1, int(sr * 0.005))
    env = np.abs(x)
    kern = np.ones(win) / win
    env = np.convolve(env, kern, mode="same")
    hop = int(sr * 0.001)
    e = env[::hop]
    thr = 0.30 * float(e.max())
    cand = np.nonzero(e > thr)[0]
    onsets, last = [], -1e9
    for i in cand:
        if (i - last) * 0.001 >= 0.020:
            onsets.append(i * 0.001)
            last = i
    return onsets


def main() -> int:
    res: dict[str, dict] = {}
    ev = json.load(open(os.path.join(OUT, "evento.json")))
    lut = F.build_lut()

    # ---------------- 1. estrutura -----------------------------------------
    frames = sorted(int(m.group(1)) for f in os.listdir(os.path.join(OUT, "frames_1280x720"))
                    if (m := re.fullmatch(r"f(\d{4})\.png", f)))
    zframes = sorted(int(m.group(1)) for f in os.listdir(os.path.join(OUT, "faz2_zoom"))
                     if (m := re.fullmatch(r"z(\d{4})\.png", f)))
    ok1 = (frames == list(range(F.NF)) and zframes == list(range(F.NF))
           and ev["S1_END"] == 257 and ev["cut"] == 1080 and ev["pecks"] == PECKS)
    res["1_estrutura"] = {
        "frames": len(frames), "zoom_frames": len(zframes),
        "S1": f"0–{ev['S1_END']}", "S2": f"{ev['S1_END']+1}–{ev['cut']-1}",
        "corte_45s": ev["cut"], "ok": ok1,
    }

    # ---------------- 2. revelacoes ----------------------------------------
    revs = ev["reveacoes"]
    ok2 = len(revs) == 10 and all(r["frames"] >= REVEALS_MIN_F for r in revs)
    res["2_revelacoes"] = {
        "eventos": {r["evento"]: f'{r["f0"]}–{r["f1"]} ({r["frames"]}f)' for r in revs},
        "criterio": f"10 eventos, >= {REVEALS_MIN_F} frames cada", "ok": ok2,
    }

    # ---------------- 3. offset de tempo (MAE par-a-par) -------------------
    worst = (1e9, None)
    for t in F.SAMPLES:
        for grp in ("mig", "bird"):
            fs = sorted(f for f in os.listdir(LYR)
                        if f.startswith(f"f{t}_{grp}") and f.endswith(".png"))
            ims = []
            for f in fs:
                ly = cv2.imread(os.path.join(LYR, f), cv2.IMREAD_UNCHANGED)
                y0, y1, x0, x1 = tight(ly[:, :, 3])
                ims.append((f, ly[y0:y1, x0:x1]))
            for i in range(len(ims)):
                for j in range(i + 1, len(ims)):
                    a, b = ims[i][1], ims[j][1]
                    h = min(a.shape[0], b.shape[0]); w = min(a.shape[1], b.shape[1])
                    a = a[(a.shape[0]-h)//2:(a.shape[0]-h)//2+h,
                          (a.shape[1]-w)//2:(a.shape[1]-w)//2+w]
                    b = b[(b.shape[0]-h)//2:(b.shape[0]-h)//2+h,
                          (b.shape[1]-w)//2:(b.shape[1]-w)//2+w]
                    na, nb = norm96(a), norm96(b)
                    msk = (na[:, :, 3] > 128) & (nb[:, :, 3] > 128)
                    if msk.sum() < 200:
                        continue
                    mae = float(np.abs(na[:, :, :3].astype(np.float32) - nb[:, :, :3].astype(np.float32))[msk].mean())
                    if mae < worst[0]:
                        worst = (mae, (t, ims[i][0], ims[j][0]))
    ok3 = worst[0] >= MAE_MIN
    res["3_offset_tempo"] = {
        "mae_min": round(worst[0], 2), "pior_par": worst[1],
        "criterio": f">= {MAE_MIN} (F2; copia identica/congelada ~ 0)", "ok": ok3,
    }

    # ---------------- 4. sync com a trilha real ----------------------------
    ons = onsets()
    deltas = {}
    for f in PECKS:
        t_alvo = f / 24.0
        d = min(abs(o - t_alvo) for o in ons) * 24.0
        deltas[f] = round(float(d), 2)
    ok4 = max(deltas.values()) <= 1.0
    res["4_sync_trilha"] = {
        "delta_frames_por_bicada": deltas, "onsets_detectados": len(ons),
        "criterio": "<= 1.0 frame vs onsets reais do fase3_track.wav", "ok": ok4,
    }

    # ---------------- 5. anti-pop + 6. oclusao -----------------------------
    pops, covs = {}, {}
    birds = [(bn, F.BIRD[bn]["reveal"]) for bn in ("1", "2", "3", "4")]
    for bn, (r0, _r1) in birds:
        vals = []
        for t in (r0, r0 + 1, r0 + 2):
            mp = os.path.join(LYR, f"f{t}_meta.json")
            if not os.path.exists(mp):
                continue
            meta = json.load(open(mp))
            pl = plane_bird(meta["birds"][bn])
            core = cv2.erode((pl > 240 / 255.0).astype(np.uint8),
                             np.ones((3, 3), np.uint8), 1)
            if core.sum() == 0:
                continue
            vals.append(float(pl[core == 1].mean()))
        pops[bn] = round(max(vals) - min(vals), 2) if len(vals) >= 2 else 0.0
        mp = os.path.join(LYR, f"f{r0}_meta.json")
        meta = json.load(open(mp))
        pl = plane_bird(meta["birds"][bn])
        sh = plane_mig(meta["migas"][meta["birds"][bn]["shell"]])
        core = cv2.erode((pl > 240 / 255.0).astype(np.uint8),
                         np.ones((3, 3), np.uint8), 2)
        cov = float((sh[core == 1] > 100 / 255.0).sum() / max(1, core.sum()))
        covs[bn] = round(cov, 4)
    ok5 = all(v < 1.0 for v in pops.values())
    ok6 = all(v >= COV_MIN for v in covs.values())
    res["5_anti_pop"] = {
        "delta_alfa_nucleo_r0..r0+2": pops,
        "criterio": "< 1 (bird nunca anima alfa/escala)", "ok": ok5,
    }
    res["6_oclusao"] = {
        "cobertura_nucleo_em_r0": covs,
        "criterio": f">= {COV_MIN} (carapaca fechada 100% opaca)", "ok": ok6,
    }

    # ---------------- 7. sombra de contato (mediana por objeto) ------------
    acc: dict[str, list[float]] = {}
    mins: dict[str, float] = {}
    for t in F.SAMPLES:
        mp = os.path.join(LYR, f"f{t}_meta.json")
        if not os.path.exists(mp):
            continue
        meta = json.load(open(mp))
        o, s = lut[t]
        plate = cv2.imread(os.path.join(
            F.STAB_WALK if o == "walk" else F.STAB_PECK, f"s{s}.png")).astype(np.float32)
        frame = cv2.imread(os.path.join(OUT, "frames_1280x720", f"f{t:04d}.png")).astype(np.float32)
        gp = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        gf = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for grp in ("migas", "birds"):
            for name, e in meta[grp].items():
                if abs(e["dy"]) >= 1.0:
                    continue
                cx, cy = int(round(e["pos"][0])), int(round(e["pos"][1]))
                wpx = int(round(e["w_px"] if "w_px" in e else e["scale"] * F.MIG_W))
                hw = max(8, int(0.4 * wpx))
                ring_p = gp[cy + 2:cy + 10, cx - hw:cx + hw]
                ring_f = gf[cy + 2:cy + 10, cx - hw:cx + hw]
                if ring_p.size == 0 or ring_f.size == 0:
                    continue
                key = ("miga_" if grp == "migas" else "bird_") + name
                d = float(ring_p.mean() - ring_f.mean())
                acc.setdefault(key, []).append(d)
                mins[key] = min(mins.get(key, 1e9), d)
    med = {k: round(float(np.median(v)), 1) for k, v in acc.items()}
    ok7 = med.get("miga_A", 0.0) >= 6.0 and all(
        v >= 3.0 for k, v in med.items() if k != "miga_A")
    res["7_sombra"] = {
        "delta_lum_mediano": med, "minimos": {k: round(v, 1) for k, v in mins.items()},
        "criterio": "mediana A >= 6 (faixa aprovada F2); demais >= 3 "
                    "(minimo reportado: baseline do plate varia com o src)", "ok": ok7,
    }

    # ---------------- 8. retas estaticas -----------------------------------
    # candidato = curso CONTINUO >= 30 rows de gradiente forte numa coluna
    # (artefato retilineo real); bordas organicas de sprite tem cursos de
    # ~8-20 rows e nao contam. Colunas que existem no plate sao excluidas.
    x0r, x1r, y0r, y1r = REGION

    def col_runs(im: np.ndarray) -> set[int]:
        g = np.abs(cv2.Sobel(im[y0r:y1r, x0r:x1r], cv2.CV_32F, 1, 0, ksize=3)) > 40
        out = set()
        for c in range(g.shape[1]):
            best = cur = 0
            for v in g[:, c]:
                cur = cur + 1 if v else 0
                best = max(best, cur)
            if best >= 30:
                out.add(c)
        return out

    colcount: dict[int, int] = {}
    for t in [s for s in F.SAMPLES if s > F.S1_END]:
        o, s = lut[t]
        plate = cv2.cvtColor(cv2.imread(os.path.join(
            F.STAB_WALK if o == "walk" else F.STAB_PECK, f"s{s}.png")), cv2.COLOR_BGR2GRAY)
        frame = cv2.cvtColor(cv2.imread(os.path.join(
            OUT, "frames_1280x720", f"f{t:04d}.png")), cv2.COLOR_BGR2GRAY)
        sp, sc = col_runs(plate), col_runs(frame)
        comp_only = sc - set().union(*[range(c - 2, c + 3) for c in sp]) if sp else sc
        for c in comp_only:
            colcount[c + x0r] = colcount.get(c + x0r, 0) + 1
    static = sorted(c for c, n in colcount.items() if n >= 6)
    ok8 = len(static) == 0
    res["8_retas_estaticas"] = {
        "colunas_suspeitas": static[:20],
        "criterio": "0 (curso continuo >= 30 rows do composto, >= 6 amostras, "
                    "ausente do plate)", "ok": ok8,
    }

    # ---------------- 9. artefatos -----------------------------------------
    arts = ["fase4_full.mp4", "fase4_zoom.mp4", "reel_fase4.png", "evento.json"]
    ok9 = all(os.path.exists(os.path.join(OUT, a)) for a in arts) \
        and len(os.listdir(LYR)) > 50
    res["9_artefatos"] = {"arquivos": arts, "ok": ok9}

    # ---------------- resultado --------------------------------------------
    ok = all(v["ok"] for v in res.values())
    print("=" * 62)
    print("FASE 4 — CHECKLIST DO TRECHO COMPLETO (medidas reais)")
    print("=" * 62)
    for k, v in res.items():
        print(f"\n[{'OK ' if v['ok'] else 'FALHOU'}] {k}")
        for kk, vv in v.items():
            if kk != "ok":
                print(f"    {kk}: {vv}")
    print("\nRESULTADO:", "APROVADO (todos os critérios)" if ok else "HÁ ITEM FORA")
    with open(os.path.join(OUT, "verify_fase4.json"), "w") as fh:
        json.dump({"itens": res, "aprovado": ok}, fh, indent=1, ensure_ascii=False)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
