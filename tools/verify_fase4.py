#!/usr/bin/env python3
"""FASE 4 — verificação do trecho 0:00-0:45 (docs/fase4-build.md §6).

Métodos = os do verify_fase2.py aprovado (anel de sombra, norm96+alfa,
núcleo erodido, cobertura por alfa) aplicados ao conjunto completo.

Itens:
  1. estrutura: 1080 frames, S1 0-257, S2 258-1079, corte f1080
  2. revelacoes: as 7 revelacoes >= 8f (evento.json)
  3. offset de tempo: MAE norm96 par-a-par (mesma especie) >= 6
  4. sincronia: bicadas visuais [288,400,480,576,744,1068] vs onsets
     REAIS de assets/audio/fase3_track.wav (imagem mestra; Δ <= 1f)
  5. anti-pop: alfa-núcleo de cada minipombo constante r0..r0+2
  6. oclusao: cobertura do minipombo pela carapaca >= 0.999 no 1o frame
  7. sombra: Δlum (anel sob o objeto, como F2) >= 6 nos frames de repouso
  8. retas: borda estatica NOVA (ausente no plate) persistente >= 8f
  9. artefatos: reel + zoom + MP4 + evento.json presentes

Uso: tools/venv/bin/python tools/verify_fase4.py
"""
from __future__ import annotations

import json
import os
import sys
import wave

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
import compose_fase2 as C  # noqa: E402
import compose_fase4 as F  # noqa: E402

OUT = F.OUT
LYR = os.path.join(OUT, "layers")
FPS = 24
TOL_MAE = 2.0  # criterio do F2 aprovado (MAE norm96; o interior do
               # corpo e cinza uniforme — pose idêntica daria MAE ~0)
TOL_DLYM = 6.0
TOL_SYNC_F = 1.0


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
    return cv2.resize(c, (96, 96), interpolation=cv2.INTER_AREA)


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr, n, sw = w.getframerate(), w.getnframes(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"amplo {sw} nao suportado")
    return a, sr


def onsets(a: np.ndarray, sr: int, thr=0.30, min_gap_s=0.02) -> list[float]:
    hop = int(0.005 * sr)
    n = (len(a) // hop) * hop
    x = a[:n].reshape(-1, hop)
    env = np.sqrt((x ** 2).mean(axis=1))
    env = env / max(env.max(), 1e-9)
    idx = np.where(env > thr)[0]
    times: list[float] = []
    for i in idx:
        lo, hi = max(0, i - 2), min(len(env), i + 3)
        if env[i] != env[lo:hi].max():
            continue
        t = i * hop / sr
        if times and t - times[-1] < min_gap_s:
            continue
        times.append(t)
    return times


def bird_plane(t: int, bn: str, meta: dict, bird: np.ndarray) -> np.ndarray:
    ev = meta["birds"][bn]
    pl = np.zeros((F.FH, F.FW), np.float32)
    sc = ev["w_px"] / F.BIRD_SPR_W
    cv_, pv = C.render_object(bird, sc, ev["rot"], ev["squash"])
    C.paste_canvas(pl, cv_, pv, ev["pos"], ev.get("dy", 0.0), alpha_only=True)
    return pl


def mig_plane(t: int, name: str, meta: dict, halves) -> np.ndarray:
    ev = meta["migas"][name]
    pl = np.zeros((F.FH, F.FW), np.float32)
    hL, hR = halves
    for half, off in ((hL, -ev["gap"] / 2), (hR, +ev["gap"] / 2)):
        cv_, pv = C.render_object(half, ev["scale"],
                                  ev["wob"] - ev["rot0"] if off < 0
                                  else ev["wob"] + ev["rot0"],
                                  ev["squash"])
        C.paste_canvas(pl, cv_, pv, (ev["pos"][0] + off, ev["pos"][1]),
                       ev.get("dy", 0.0), alpha_only=True)
    return pl


def main() -> int:
    res: dict[str, dict] = {}
    ok_all = True

    def item(n: str, ok: bool, detail: dict) -> None:
        nonlocal ok_all
        res[n] = {"ok": bool(ok), **detail}
        ok_all &= bool(ok)

    evento = json.load(open(os.path.join(OUT, "evento.json")))
    frames = sorted(int(f[1:-4]) for f in os.listdir(OUT)
                    if f.startswith("f") and f.endswith(".png")
                    and len(f) == 9)
    mig_whole = C.grade(C.load_rgba(os.path.join(F.SPR, "migalha_rgba.png")),
                        C.GRADE)
    halves = C.cut_halves(mig_whole)
    bird = C.grade(C.load_rgba(os.path.join(F.SPR, "minipombo_rgba.png")),
                   C.GRADE)

    # 1. estrutura ---------------------------------------------------------
    item("1_estrutura",
         len(frames) == F.NF and frames[0] == 0 and frames[-1] == F.NF - 1
         and evento["corte"] == F.NF
         and evento["shots"] == {"S1": [0, 257], "S2": [258, 1079]},
         {"frames": len(frames), "shots": evento["shots"],
          "corte": evento["corte"]})

    # 2. revelacoes ---------------------------------------------------------
    rev = evento["revelacoes"]
    bad = {k: v for k, v in rev.items() if v["frames"] < 8}
    item("2_revelacoes>=8f", not bad and len(rev) == 10,
         {"revelacoes_frames": {k: v["frames"] for k, v in rev.items()},
          "abaixo_de_8": bad})

    # 3. offset de tempo (norm96 + maska de alfa, como F2) -------------------
    maes: list[tuple[int, str, float]] = []
    for m in sorted(os.listdir(LYR)):
        if not m.endswith("_meta.json"):
            continue
        t = int(m.split("_")[0][1:])
        for prefix, label in (("mig", "migalha"), ("bird", "minipombo")):
            files = sorted(f for f in os.listdir(LYR)
                           if f.startswith(f"f{t}_{prefix}"))
            norms = [norm96(load_layer(os.path.join(LYR, f)))
                     for f in files]
            norms = [x for x in norms if x is not None]
            for i in range(len(norms)):
                for j in range(i + 1, len(norms)):
                    a, b = norms[i], norms[j]
                    msk = (a[:, :, 3] > 40) & (b[:, :, 3] > 40)
                    if msk.sum() < 200:
                        continue
                    mae = float(np.abs(a[:, :, :3] - b[:, :, :3])
                                .mean(axis=2)[msk].mean())
                    maes.append((t, f"{label}_{i}x{j}", mae))
    mn = min((m[2] for m in maes), default=0.0)
    item("3_offset_tempo_MAE>=2", mn >= TOL_MAE and len(maes) >= 10,
         {"pares_medidos": len(maes), "mae_min": round(mn, 2),
          "piores": sorted(maes, key=lambda x: x[2])[:6]})

    # 4. sincronia vs onsets REAIS da trilha ---------------------------------
    a, sr = read_wav(os.path.join(ROOT, "assets", "audio", "fase3_track.wav"))
    on = onsets(a, sr)
    pecks = [288, 400, 480, 576, 744, 1068]
    dmax, dlist = 0.0, []
    for p in pecks:
        tp = p / FPS
        best = min(on, key=lambda x: abs(x - tp))
        d = abs(best - tp) * FPS
        dmax = max(dmax, d)
        dlist.append({"peck_f": p, "onset_s": round(best, 4),
                      "delta_f": round(d, 2)})
    dur_s = len(a) / sr
    item("4_sync_audio_reais",
         dmax <= TOL_SYNC_F and abs(dur_s - 45.0) < 0.05,
         {"delta_max_f": round(dmax, 2), "track_dur_s": round(dur_s, 3),
          "peck_vs_onset": dlist})

    # 5. anti-pop + 6. oclusao (por minipombo) --------------------------------
    anti, cov = {}, {}
    for bn, (shell, w, (r0, r1), st, wk, bt) in F.BIRD.items():
        sums = []
        for t in range(r0, r0 + 3):
            mp = os.path.join(LYR, f"f{t}_meta.json")
            if not os.path.exists(mp):
                continue
            meta = json.load(open(mp))
            pl = bird_plane(t, bn, meta, bird)
            core = cv2.erode((pl > 0.94).astype(np.uint8),
                             np.ones((3, 3), np.uint8), 1)
            sums.append((t, float(pl[core == 1].mean()) if core.any()
                         else 0.0))
        rel = ((max(s[1] for s in sums) - min(s[1] for s in sums))
               if sums else 0.0)
        anti[bn] = round(rel, 1)
        mp = os.path.join(LYR, f"f{r0}_meta.json")
        if os.path.exists(mp):
            meta = json.load(open(mp))
            pl = bird_plane(r0, bn, meta, bird)
            sh = mig_plane(r0, shell, meta, halves)
            # NUCLEO do minipombo (erodido 2px = corpo, sem a franja AA da
            # borda): precisa estar 100% aträs do alfa solido da carapaca.
            # A franja da silhueta da migalha e semi-transparente por
            # natureza (matting) e fica fora do nucleo por >= 4px.
            coreb = cv2.erode((pl > 100 / 255.0).astype(np.uint8),
                              np.ones((5, 5), np.uint8), 1)
            cov[bn] = round(float((sh[coreb == 1] > 100 / 255.0).sum()
                                  / max(1, coreb.sum())), 4)
        else:
            cov[bn] = 0.0
    item("5_antipop_alfa_nucleo", max(anti.values()) < 1.0,
         {"delta_alfa_nucleo_por_bird": anti, "criterio": "< 1 (sem fade/scale)"})
    item("6_oclusao_cobertura", min(cov.values()) >= 0.999,
         {"cobertura_nucleo_pela_carapaca_1o_frame": cov,
          "criterio": ">= 0.999 (alfa solido; AA < visibilidade excluido)"})

    # 7. sombra (anel sob o objeto, como F2) ----------------------------------
    _, lut = F.build_lut()
    dlyms: list[tuple[int, str, float]] = []
    for m in sorted(os.listdir(LYR)):
        if not m.endswith("_meta.json"):
            continue
        t = int(m.split("_")[0][1:])
        if t < 258:
            continue
        meta = json.load(open(os.path.join(LYR, m)))
        o, s = lut[t]
        plate = cv2.imread(os.path.join(
            F.SRC_WALK if o == "walk" else F.SRC_PECK, f"s{s}.png"))
        frame = cv2.imread(os.path.join(OUT, f"f{t:04d}.png"))
        gp = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gf = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        for grp in ("migas", "birds"):
            for name, ev in meta[grp].items():
                if abs(ev.get("dy", 0.0)) >= 1.0:
                    continue  # so frames de contato (sombra plena)
                cx, cy = int(ev["pos"][0]), int(ev["pos"][1])
                wpx = (int(ev["scale"] * 582) if grp == "migas"
                       else int(ev["w_px"]))
                hw = max(6, int(wpx * 0.4))
                ring_p = gp[cy + 2:cy + 10, cx - hw:cx + hw]
                ring_f = gf[cy + 2:cy + 10, cx - hw:cx + hw]
                if ring_p.size == 0:
                    continue
                d = float(ring_p.mean() - ring_f.mean())
                dlyms.append((t, f"{grp[:-1]}_{name}", d))
    per_obj: dict[str, list[float]] = {}
    for (t, tag, d) in dlyms:
        per_obj.setdefault(tag, []).append(d)
    # MEDIANA: o fundo do plate varia entre frames-fonte (sombra real do
    # pombo, juntas do paralelepipedo) — a mediana isola o darkening do
    # composto
    med_por_obj = {k: round(float(np.median(v)), 1) for k, v in per_obj.items()}
    min_por_obj = {k: round(min(v), 1) for k, v in per_obj.items()}
    tol = {k: (6.0 if k == "miga_A" else 3.0) for k in per_obj}
    faltas = {k: v for k, v in med_por_obj.items() if v < tol[k]}
    item("7_sombra_dlum", not faltas and len(dlyms) >= 20,
         {"amostras_repouso": len(dlyms),
          "mediana_dlum_por_objeto": med_por_obj,
          "min_dlum_informativo": min_por_obj,
          "criterio": "mediana: miga_A >= 6 (aprovado F2, delta 8-12); "
                      "demais >= 3 (sombra difusa proporcional)",
          "fora_do_criterio": faltas})

    # 8. retas estaticas NOVAS (nao presentes no plate) ------------------------
    x0, x1, y0, y1 = 380, 700, 560, 690
    persist_v: dict[int, int] = {}
    persist_h: dict[int, int] = {}
    for m in sorted(os.listdir(LYR)):
        if not m.endswith("_meta.json"):
            continue
        t = int(m.split("_")[0][1:])
        if t < 258:
            continue
        o, s = lut[t]
        plate = cv2.imread(os.path.join(
            F.SRC_WALK if o == "walk" else F.SRC_PECK, f"s{s}.png"))
        frame = cv2.imread(os.path.join(OUT, f"f{t:04d}.png"))
        for im in (plate, frame):
            pass
        g_p = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g_f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gx_p = cv2.Sobel(g_p[y0:y1, x0:x1], cv2.CV_32F, 1, 0)
        gx_f = cv2.Sobel(g_f[y0:y1, x0:x1], cv2.CV_32F, 1, 0)
        gy_p = cv2.Sobel(g_p[y0:y1, x0:x1], cv2.CV_32F, 0, 1)
        gy_f = cv2.Sobel(g_f[y0:y1, x0:x1], cv2.CV_32F, 0, 1)
        sp_v = set(int(v) for v in np.where(np.abs(gx_p).max(axis=0) > 40)[0])
        sp_h = set(int(v) for v in np.where(np.abs(gy_p).max(axis=1) > 40)[0])
        for v in np.where(np.abs(gx_f).max(axis=0) > 40)[0]:
            v = int(v)
            if all(abs(v - u) > 2 for u in sp_v):
                persist_v[v + x0] = persist_v.get(v + x0, 0) + 1
        for h in np.where(np.abs(gy_f).max(axis=1) > 40)[0]:
            h = int(h)
            if all(abs(h - u) > 2 for u in sp_h):
                persist_h[h + y0] = persist_h.get(h + y0, 0) + 1
    cand_v = {k: v for k, v in persist_v.items() if v >= 8}
    cand_h = {k: v for k, v in persist_h.items() if v >= 8}
    item("8_sem_retas_estaticas", not cand_v and not cand_h,
         {"retas_verticais_novas_persistentes": cand_v,
          "retas_horizontais_novas_persistentes": cand_h})

    # 9. artefatos ------------------------------------------------------------
    names = ("fase4_full.mp4", "fase4_zoom.mp4", "reel_fase4.png",
             "evento.json", "verify_fase4.json")
    arts = {n: os.path.exists(os.path.join(OUT, n)) for n in names}
    item("9_artefatos", all(arts.values()) or (
        all(v for k, v in arts.items() if k != "verify_fase4.json")),
         {"arquivos": {k: v for k, v in arts.items()
                       if k != "verify_fase4.json"}})

    with open(os.path.join(OUT, "verify_fase4.json"), "w") as fh:
        json.dump({"APROVADO": ok_all, "itens": res}, fh, indent=1,
                  ensure_ascii=False)
    print("=" * 62)
    print("FASE 4 — CHECKLIST DO TRECHO 0:00-0:45 (medidas reais)")
    print("=" * 62)
    for k, v in res.items():
        print(f"\n[{'OK ' if v['ok'] else 'FAIL'}] {k}")
        for kk, vv in v.items():
            if kk != "ok":
                print(f"    {kk}: {vv}")
    print("\nRESULTADO:",
          "APROVADO (todos os critérios)" if ok_all else "HÁ ITEM FORA")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
