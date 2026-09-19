#!/usr/bin/env python3
"""FASE 5 — checklist da entrega final (medidas reais).

 1 master aprovado   verify_fase4.json aprovado == true (9/9 no 720p)
 2 polimento S1      5 blocos de fases distintas (cortes f54/108/141/162/216;
                     nenhum par de poses repetido entre cortes)
 3 container 1080p   1920x1080, 24 fps, 1080 frames, duracao 45,000s (+-0,05),
                     h264 + aac 48k, faststart
 4 fidelidade        3 frames do mp4 1080p rebaixados a 720p vs master:
                     PSNR >= 30 dB (so ruido de encode)
 5 audio             trilha presente, duracao 45,000s, pico ~0,71 (nao alterada)
 6 artefatos         fase5_final_1080p.mp4, fase5_final_720p.mp4, poster

Uso: tools/venv/bin/python tools/verify_fase5.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import wave

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose_fase2 as C  # noqa: E402
import compose_fase4 as F  # noqa: E402

OUT4 = F.OUT
OUT5 = os.path.join(C.ROOT, "assets", "out", "fase5")
MP4_1080 = os.path.join(OUT5, "fase5_final_1080p.mp4")
MP4_720 = os.path.join(OUT5, "fase5_final_720p.mp4")
TRACK = os.path.join(C.ROOT, "assets", "audio", "fase3_track.wav")
FF = C.FFMPEG
FPS = 24.0
S1_CUTS = [54, 108, 141, 162, 216]


def ffprobe(path: str) -> dict:
    """Static ffprobe limitado — parse do ffmpeg -i + decode p/ contar frames."""
    import re as _re
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True)
    err = r.stderr
    dur = float(_re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
                .group(3)) + 60 * int(_re.search(
                    r"Duration: (\d+):(\d+):(\d+\.\d+)", err).group(2))
    vs = next(l for l in err.splitlines() if ": Video: " in l)
    as_ = next(l for l in err.splitlines() if ": Audio: " in l)
    fps = _re.search(r"(\d+(?:\.\d+)?) fps", vs).group(1)
    wh = _re.search(r"(\d{3,4})x(\d{3,4})", vs).groups()
    sr = _re.search(r"(\d+) Hz", as_).group(1)
    r2 = subprocess.run([FF, "-i", path, "-map", "0:v:0", "-f", "null", "-"],
                        capture_output=True, text=True)
    m = _re.findall(r"frame=\s*(\d+)", r2.stderr)
    nframes = m[-1] if m else "0"
    with open(path, "rb") as fh:
        head = fh.read(262144)
    faststart = head.find(b"moov") != -1 and (
        head.find(b"moov") < head.find(b"mdat") or head.find(b"mdat") == -1)
    return {"width": int(wh[0]), "height": int(wh[1]), "fps": fps,
            "nb_frames": nframes, "duration": dur, "sample_rate": sr,
            "vcodec": _re.search(r"Video: (\w+)", vs).group(1),
            "acodec": _re.search(r"Audio: (\w+)", as_).group(1),
            "faststart": faststart}


def decode_frame(mp4: str, idx: int) -> np.ndarray:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    subprocess.run([FF, "-y", "-i", mp4, "-vf", f"select=eq(n\\,{idx})",
                    "-vsync", "0", "-frames:v", "1", tmp.name],
                   check=True, capture_output=True)
    im = cv2.imread(tmp.name)
    os.unlink(tmp.name)
    return im


def audio_stats(mp4: str) -> tuple[float, float]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run([FF, "-y", "-i", mp4, "-vn", "-acodec", "pcm_s16le",
                    tmp.name], check=True, capture_output=True)
    with wave.open(tmp.name, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2") / 32768.0
    os.unlink(tmp.name)
    return len(x) / sr, float(np.abs(x).max())


def main() -> int:
    res: dict[str, dict] = {}

    # ---------------- 1. master aprovado ------------------------------------
    v4 = json.load(open(os.path.join(OUT4, "verify_fase4.json")))
    res["1_master_aprovado"] = {
        "verify_fase4": "aprovado" if v4["aprovado"] else "REPROVADO",
        "ok": bool(v4["aprovado"]),
    }

    # ---------------- 2. polimento S1 ---------------------------------------
    lut = F.build_lut()
    s1 = [lut[f][1] for f in range(F.S1_END + 1)]   # 0..257 (sem o corte de cena f258)
    cuts = [f for f in range(1, F.S1_END + 1) if abs(s1[f] - s1[f - 1]) > 2]
    # pares de poses nos cortes (offset dentro da janela 0..74)
    pairs = [(int(s1[f - 1] - 160), int(s1[f] - 160)) for f in cuts]
    uniq = len(set(pairs)) == len(pairs)
    ok2 = cuts == S1_CUTS and uniq
    res["2_polimento_S1"] = {
        "cortes": cuts,
        "par_de_poses_(saida,entrada)_por_corte": pairs,
        "criterio": f"cortes {S1_CUTS}; nenhum par repetido (nao-loop)", "ok": ok2,
    }

    # ---------------- 3. container 1080p ------------------------------------
    pr = ffprobe(MP4_1080)
    dur = pr["duration"]
    ok3 = (pr["width"] == 1920 and pr["height"] == 1080
           and abs(float(pr["fps"]) - 24.0) < 0.01
           and pr["nb_frames"] == "1080" and abs(dur - 45.0) <= 0.05
           and pr["sample_rate"] == "48000"
           and pr["vcodec"] == "h264" and pr["acodec"] == "aac"
           and pr["faststart"])
    res["3_container_1080p"] = {
        "resolucao": f'{pr["width"]}x{pr["height"]}', "fps": pr["fps"],
        "frames": pr["nb_frames"], "duracao_s": round(dur, 3),
        "video": pr["vcodec"], "audio": f'{pr["acodec"]} {pr["sample_rate"]}Hz',
        "moov_antes_do_mdat": pr["faststart"],
        "tamanho_MB": round(os.path.getsize(MP4_1080) / 1e6, 1),
        "criterio": "1920x1080, 24fps, 1080 frames, 45,000s, h264+aac, faststart",
        "ok": ok3,
    }

    # ---------------- 4. fidelidade do upscale ------------------------------
    psnrs = {}
    for idx in (400, 760, 1068):
        hi = decode_frame(MP4_1080, idx)
        lo = cv2.imread(os.path.join(OUT4, "frames_1280x720", f"f{idx:04d}.png"))
        down = cv2.resize(hi, (1280, 720), interpolation=cv2.INTER_AREA)
        mse = float(np.mean((down.astype(np.float64) - lo.astype(np.float64)) ** 2))
        psnrs[idx] = round(float(10 * np.log10(255 ** 2 / max(mse, 1e-9))), 1)
    ok4 = min(psnrs.values()) >= 30.0
    res["4_fidelidade_upscale"] = {
        "psnr_1080p_rebaixado_vs_master": psnrs,
        "criterio": ">= 30 dB (lanczos + unsharp leve; sem conteudo alterado)",
        "ok": ok4,
    }

    # ---------------- 5. audio ----------------------------------------------
    dur_a, peak = audio_stats(MP4_1080)
    ok5 = abs(dur_a - 45.0) <= 0.05 and 0.60 <= peak <= 0.80
    res["5_audio"] = {
        "duracao_s": round(dur_a, 3), "pico": round(peak, 3),
        "criterio": "45,000s; pico ~0,71 (trilha aprovada, sem alteracao)",
        "ok": ok5,
    }

    # ---------------- 6. artefatos ------------------------------------------
    arts = [MP4_1080, MP4_720, os.path.join(OUT5, "poster_1080p.png")]
    ok6 = all(os.path.exists(p) for p in arts)
    res["6_artefatos"] = {
        "arquivos": [os.path.basename(p) for p in arts],
        "tamanhos_MB": [round(os.path.getsize(p) / 1e6, 1) for p in arts],
        "ok": ok6,
    }

    ok = all(v["ok"] for v in res.values())
    print("=" * 62)
    print("FASE 5 — CHECKLIST DA ENTREGA FINAL (medidas reais)")
    print("=" * 62)
    for k, v in res.items():
        print(f"\n[{'OK ' if v['ok'] else 'FALHOU'}] {k}")
        for kk, vv in v.items():
            if kk != "ok":
                print(f"    {kk}: {vv}")
    print("\nRESULTADO:", "APROVADO (todos os critérios)" if ok else "HÁ ITEM FORA")
    with open(os.path.join(OUT5, "verify_fase5.json"), "w") as fh:
        json.dump({"itens": res, "aprovado": ok}, fh, indent=1, ensure_ascii=False)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
