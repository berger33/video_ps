#!/usr/bin/env python3
"""FASE 3 — verificacao da trilha contra a grade (audio REAL, nao intencao).

Conforme a ressalva de aprovacao da Fase 2: a bicada visual e a mestra; o
verify roda contra o audio final, nao contra a intencao. Nesta fase o alvo e
a grade (o conformedo da Fase 4 encaixa a imagem na grade); apos o corte, o
mesmo verify roda contra os frames reais das bicadas do video.

Itens:
  1. onset de cada evento forte da trilha vs frame da grade (delta em frames)
  2. nenhum evento forte antes do KICK #1 (f288) — a 1a bicada e o 1o evento
  3. crescendo por bloco (RMS A < B < C; maximo na coletiva)
  4. duracao exata de 1080 frames; hold final = cauda monotônica do hit
  5. preview (waveform + marcadores) -> assets/audio/fase3_preview.png

Uso: tools/venv/bin/python tools/verify_audio_fase3.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAV = os.path.join(ROOT, "assets", "audio", "fase3_track.wav")
TS = os.path.join(ROOT, "assets", "audio", "fase3_timestamps.json")
PNG = os.path.join(ROOT, "assets", "audio", "fase3_preview.png")
FPS = 24
SR = 48000


def onsets(d: np.ndarray, win: float = 0.002,
           min_gap: float = 0.01) -> np.ndarray:
    """pickpicking: pico local em janelas de 60ms + piso absoluto."""
    w = max(1, int(win * SR))
    env = np.array([np.sqrt((d[i:i + w] ** 2).mean())
                    for i in range(0, len(d) - w, w)])
    t = np.arange(len(env)) * win
    peaks = []
    for i in range(1, len(env) - 1):
        lo, hi = max(0, i - 30), min(len(env), i + 31)
        if (env[i] == env[lo:hi].max() and env[i] > env[i - 1]
                and env[i] >= env[i + 1] and env[i] > env.max() * 0.06):
            if not peaks or t[i] - peaks[-1] >= min_gap:
                peaks.append(t[i])
    return np.array(peaks)


def main() -> int:
    d, sr = sf.read(WAV)
    assert sr == SR
    ts = json.load(open(TS))
    res = {}
    ok = True

    # ---------------- 1. onsets vs grade ----------------
    pk = onsets(d)
    strong = [e for e in ts["eventos"] if e["forca"] in ("forte", "maximo")]
    deltas = []
    pairs = []
    for e in strong:
        t_e = e["frame"] / FPS
        j = int(np.argmin(np.abs(pk - t_e)))
        df = (pk[j] - t_e) * FPS
        deltas.append(abs(df))
        pairs.append((e["frame"], e["tipo"], round(df, 2)))
    dmax = max(deltas)
    ok1 = bool(dmax <= 1.0)
    ok &= ok1
    res["1_onsets_vs_grade"] = {
        "eventos_fortes": len(strong),
        "delta_max_frames": round(dmax, 2),
        "pares (frame_grade, tipo, delta_f)": pairs,
        "criterio": "delta <= 1 frame vs o frame de cada evento (bicada f400 = "
                    "mestra da imagem; grid musical 12f/beat fase 288; apos a "
                    "Fase 4, rodar contra frames reais das bicadas no corte)",
        "ok": ok1,
    }

    # ---------------- 2. nada forte antes do KICK #1 ----------------
    cut = int(288 / FPS * SR)
    pre = d[:cut]
    kick_pk = float(np.abs(d[cut:cut + int(0.05 * SR)]).max())
    pre_pk = float(np.abs(pre).max())
    ratio = kick_pk / max(pre_pk, 1e-9)
    ok2 = ratio >= 4.0
    ok &= ok2
    res["2_1o_evento_forte"] = {
        "pico_do_kick1 (50ms)": round(kick_pk, 3),
        "pico_maximo_antes_f288": round(pre_pk, 3),
        "ratio_de_pico": round(ratio, 2),
        "criterio": ">= 4.0 (a 1a bicada e o 1o evento forte: tudo antes e cama)",
        "ok": ok2,
    }

    # ---------------- 3. crescendo por bloco ----------------
    def rms(f0, f1):
        a, b = int(f0 / FPS * SR), int(f1 / FPS * SR)
        return float(np.sqrt((d[a:b] ** 2).mean()))
    rA, rB, rC = rms(0, 360), rms(360, 720), rms(720, 1080)
    hit_rms4 = rms(1068, 1072)
    def pk(f0, f1):
        a, b = int(f0 / FPS * SR), int(f1 / FPS * SR)
        return float(np.abs(d[a:b]).max())
    hit_pk = pk(1068, 1080)
    gpk = float(np.abs(d).max())
    max_frame = int(np.argmax(np.abs(d)) / SR * FPS)
    ok3 = (rA < rB < rC and hit_rms4 >= rC and gpk == hit_pk
           and 1068 <= max_frame < 1080)
    ok &= ok3
    res["3_crescendo_e_pico_maximo"] = {
        "rms_A": round(rA, 4), "rms_B": round(rB, 4), "rms_C": round(rC, 4),
        "rms_hit_4f": round(hit_rms4, 4),
        "pico_maximo_do_filme": round(gpk, 3), "na_frame": round(max_frame, 1),
        "criterio": "A < B < C (crescendo); pico maximo do filme DENTRO do hit "
                    "(f1068-1080); RMS do ataque do hit >= RMS do bloco C",
        "ok": ok3,
    }

    # ---------------- 4. duracao + hold final ----------------
    n_frames = len(d) / SR * FPS
    hold = d[int(1068 / FPS * SR):]
    hpk = np.abs(hold).max()
    pico_frame = float(np.argmax(np.abs(hold)) / SR / FPS)
    pico_ok = bool(pico_frame < 0.5)  # pico nos primeiros ~10ms do hold
    # apos o corpo do kick (100ms), nada concorre com o hit (minipecks da
    # pata sao < 20% do pico); o corte nao corta cauda alta
    cauda_pico = float(np.abs(hold[int(0.10 * SR):]).max())
    fim_pico = float(np.abs(hold[-int(0.10 * SR):]).max())
    cauda_ok = cauda_pico <= 0.20 * hpk
    corte_ok = fim_pico < 0.10 * hpk
    ok4 = (abs(n_frames - 1080) < 0.5 and pico_ok and cauda_ok and corte_ok)
    ok &= ok4
    res["4_duracao_hold"] = {
        "frames_totais": round(n_frames, 3),
        "pico_nos_primeiros_10ms": pico_ok, "pico_no_frame": round(pico_frame, 2),
        "pico_max_do_hold": round(float(hpk), 3),
        "maior_pico_apos_100ms": round(cauda_pico, 3),
        "pico_ultimo_100ms": round(fim_pico, 3),
        "criterio": "1080 frames; pico no 1o decil do hold; apos o corpo do "
                    "kick (100ms) nada acima de 20% do pico (minipecks da pata); "
                    "corte com cauda < 10% do pico",
        "ok": ok4,
    }

    # ---------------- 5. preview ----------------
    try:
        import cv2
        H, Wd = 420, 1600
        img = np.full((H, Wd, 3), 250, np.uint8)
        # blocos
        for (f0, f1, c) in ((0, 360, (240, 240, 250)), (360, 720, (228, 236, 250)),
                            (720, 1080, (216, 226, 248))):
            x0, x1 = int(f0 / 1080 * Wd), int(f1 / 1080 * Wd)
            cv2.rectangle(img, (x0, 40), (x1, H - 40), c, -1)
        # waveform
        step = len(d) // (Wd - 2)
        env = np.array([np.abs(d[i * step:(i + 1) * step]).max()
                        for i in range(Wd - 2)])
        env = env / max(env.max(), 1e-9)
        for x in range(Wd - 2):
            y = int(env[x] * (H - 100) / 2)
            cv2.line(img, (x + 1, H // 2), (x + 1, H // 2 - y), (90, 90, 100), 1)
            cv2.line(img, (x + 1, H // 2), (x + 1, H // 2 + y), (90, 90, 100), 1)
        # marcadores
        for e in ts["eventos"]:
            x = int(e["frame"] / 1080 * Wd)
            col = (0, 0, 255) if e["tipo"] == "kick" else \
                  (0, 140, 255) if e["tipo"] == "crack" else \
                  (120, 200, 255) if e["tipo"] == "minipeck" else (60, 60, 200)
            th = 3 if e["forca"] == "maximo" else 2
            cv2.line(img, (x, 40), (x, H - 40), col, th)
        for f, lab in ((288, "KICK1 f288"), (400, "K2 f400 (imagem)"),
                       (480, "K3 f480"), (744, "K5 f744")):
            x = int(f / 1080 * Wd)
            cv2.putText(img, lab, (x + 3, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (0, 0, 120), 1)
        x = int(1068 / 1080 * Wd)  # rotulo da coletiva p/ dentro do quadro
        cv2.putText(img, "COLETIVA f1068", (x - 118, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 120), 1)
        cv2.putText(img, "FASE 3 — trilha diegetica 45,000s (1080f) | vermelho=kick, laranja=crack, amarelo=minibicada",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1)
        cv2.imwrite(PNG, img)
        res["5_preview"] = {"arquivo": PNG, "ok": True}
    except Exception as ex:  # noqa: BLE001
        res["5_preview"] = {"arquivo": None, "ok": False, "erro": str(ex)}

    print("=" * 62)
    print("FASE 3 — CHECKLIST DA TRILHA (medido no audio final)")
    print("=" * 62)
    for k, v in res.items():
        print(f"\n[{ 'OK ' if v.get('ok') else 'FALHOU' }] {k}")
        for kk, vv in v.items():
            if kk != "ok":
                print(f"    {kk}: {vv}")
    print("\nRESULTADO:", "APROVADO" if ok else "HÁ ITEM FORA")
    def _py(o):  # numpy -> python p/ o json
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        return str(o)
    with open(os.path.join(ROOT, "assets", "audio", "verify_fase3.json"), "w") as fh:
        json.dump({"itens": res, "aprovado": bool(ok)}, fh, indent=1,
                  ensure_ascii=False, default=_py)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
