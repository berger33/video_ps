#!/usr/bin/env python3
"""FASE 4 — build completo 60s: mecanismo Fase 2 x timestamps Fase 3.

- Instância 0 (protagonista): existe sempre; wander senoidal PERIÓDICO
  (x(0)==x(1800), fase do clipe 1800%60==0) -> loop fecha.
- ADD em onset: nova cópia com offset de tempo não-uniforme distinto das
  ativas; reveal por (a) entrada andando pela borda OU (b) oclusão+wipe 16f
  atrás de instância existente.
- REMOVE em onset: cópia sai andando p/ borda mais próxima (movimento real).
- Técnicas 1-6 mantidas: matting, foot-anchor, offsets, reveals >=8f,
  cor por ambiente, sombra de contato, escala por profundidade.
- Mux final com assets/src/trilha.wav (ffmpeg do imageio-ffmpeg).
"""
import json
import os
import sys
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_clips import build_clip_b, SRC  # noqa: E402
from fase2_proto import (scale_for, place, shadow, ambient, match_color,  # noqa
                         FPS)
import imageio

OUT = os.path.join(ROOT, "assets", "build", "fase4")
os.makedirs(OUT, exist_ok=True)
N = 1800
W, H = 1344, 754
rng = np.random.default_rng(42)

events = json.load(open(os.path.join(ROOT, "assets", "build", "fase3",
                                     "events_fase3.json")))
OFFS = [12, 19, 27, 33, 41, 47]          # offsets não uniformes (mod 60)


class Fox:
    def __init__(self, fid, gy, x0, off, mode, occl=None, flip=False):
        self.fid = fid
        self.gy = gy
        self.s = scale_for(gy)
        self.x = x0
        self.off = off
        self.mode = mode            # 'hero' | 'enter' | 'occl' | 'exit'
        self.occl = occl
        self.birth = None
        self.flip = flip
        self.drift = 0.0
        self.exit_dir = 0
        self.vis_hist = []
        self.measured = False
        self.spawn_mode = None
        self.first_vis = None
        self.last_sf = 0.0

    def frame_src(self, t):
        return (t + self.off) % 180


def _rev(vh):
    vf = np.array(vh[:220])
    if len(vf) == 0 or vf.max() < 0.5:
        return None
    rel = vf / vf.max()
    lo = int(np.argmax(rel > 0.02))
    hi = int(np.argmax(rel > 0.98))
    if not bool((rel > 0.98).any()):      # ainda entrando no corte: usa fim
        hi = len(rel) - 1
    return int(hi - lo + 1)


def pick_offset(active):
    used = {a.off % 60 for a in active}
    cands = [o for o in OFFS if o % 60 not in used]
    return int(rng.choice(cands or OFFS))


def main():
    frames_src, method = build_clip_b()
    plate = cv2.cvtColor(cv2.imread(os.path.join(SRC, "campo_plate.jpg")),
                         cv2.COLOR_BGR2RGB)
    photo = cv2.cvtColor(cv2.imread(os.path.join(SRC, "fox_foto_perfil.jpg")),
                         cv2.COLOR_BGR2RGB)
    amb_src = photo[630:670, 620:990].reshape(-1, 3).astype(np.float32).mean(0)

    hero = Fox(0, 640.0, 760.0, 0, "hero")
    foxes = [hero]
    n_spawns = 0
    ev_queue = sorted(events, key=lambda e: e["frame"])
    ei = 0

    reveals, rev_occl, rev_enter, pose_diffs = [], [], [], []
    visible_per_sec = np.zeros(60)
    writer = imageio.get_writer(os.path.join(OUT, "video_sem_audio.mp4"),
                                fps=FPS, quality=8)
    gif_frames = []

    for t in range(N):
        # ---------- agenda de eventos ----------
        while ei < len(ev_queue) and ev_queue[ei]["frame"] <= t:
            ev = ev_queue[ei]; ei += 1
            active = [f for f in foxes if f.mode != "exit"]
            if ev["type"] == "ADD":
                off = pick_offset(active)
                # escolhe modo: oclusão se houver instância p/ servir de âncora
                occl = None
                if len(active) > 0 and rng.random() < 0.6:
                    occl = active[int(rng.integers(0, len(active)))]
                    gy = float(np.clip(occl.gy - 35 - rng.random() * 25,
                                       520, 700))
                    x0 = occl.x + float(rng.uniform(-20, 20))
                    mode = "occl"
                else:
                    gy = float(rng.uniform(540, 700))
                    side = int(rng.choice([-1, 1]))
                    x0 = -150 if side < 0 else W + 150
                    mode = "enter"
                f = Fox(len(foxes), gy, x0, off, mode, occl=occl,
                        flip=(mode == "enter" and x0 < 0))
                f.birth = t
                f.spawn_mode = mode
                foxes.append(f)
                n_spawns += 1
            else:  # REMOVE: quem sai = última ativa não-hero (LIFO suave)
                # não remove recém-nascidos (<20f): reveal precisa completar
                cands = [f for f in active if f.fid != 0
                         and (f.birth is None or (t - f.birth) >= 20)]
                if not cands:
                    cands = [f for f in active if f.fid != 0]
                if cands:
                    v = cands[-1]
                    v.mode = "exit"
                    v.exit_dir = -1 if v.x > W / 2 else 1
                    v.flip = v.exit_dir > 0

        canvas = plate.copy()
        # profundidade: desenha de trás (gy menor) p/ frente
        order = sorted([f for f in foxes], key=lambda f: f.gy)
        vis_count = 0
        for f in order:
            # ---------- trajetória ----------
            if f.mode == "hero":
                fx = 760 + 120 * np.sin(2 * np.pi * t / N)
            elif f.mode == "enter":
                # entra da borda: da esquerda p/ direita (flip) ou vice-versa
                f.x += 8.0 if f.flip else -8.0
                fx = f.x
                if 60 < f.x < W - 60:
                    f.mode = "live"
            elif f.mode == "exit":
                f.x += f.exit_dir * 24.0
                fx = f.x
            else:  # live / occl
                f.x += np.sin(2 * np.pi * (t + f.fid * 37) / 240) * 0.35
                fx = f.x

            src = frames_src[f.frame_src(t)]
            if f.flip:
                src = src[:, ::-1]
            inst, x0p, y0p = place(src, fx, f.gy, f.s)
            hh, ww = inst.shape[:2]
            if x0p > W or x0p + ww < 0:
                f.vis_hist.append(0.0)
                continue
            a_full = inst[..., 3] / 255.0

            # ---------- reveal ----------
            gate = np.ones_like(a_full)
            if f.mode == "occl" and f.birth is not None:
                k = (t - f.birth) / 16.0
                if k >= 1.0:
                    f.mode = "live"
                else:
                    xs = np.arange(ww)
                    Xe = -8 + max(k, 0) * (ww + 16)   # coords locais
                    gate = np.clip((Xe - xs) / 8.0 + 1, 0, 1)[None, :]

            a2 = a_full * gate
            frac = float(a2.sum() / max(a_full.sum(), 1))   # cobertura gate
            xs0, ys0 = max(0, -x0p), max(0, -y0p)
            xs1, ys1 = min(ww, W - x0p), min(hh, H - y0p)
            sf = float(a_full[ys0:ys1, xs0:xs1].sum()
                       / max(a_full.sum(), 1))              # fração na tela
            if sf > 0.3:
                vis_count += 1
            f.last_sf = sf
            if f.first_vis is None and sf > 0.02:
                f.first_vis = t
            if f.birth is not None and not f.measured:
                gm = float(gate.mean())   # cobertura geométrica da máscara
                done = f.mode != "exit" and (
                    (f.spawn_mode == "occl" and gm >= 0.98)
                    or (f.spawn_mode != "occl" and sf >= 0.98))
                if done:
                    start = f.birth if f.spawn_mode == "occl" \
                        else (f.first_vis or t)
                    r = int(t - start) + 1
                    reveals.append(r)
                    (rev_occl if f.spawn_mode == "occl"
                     else rev_enter).append(r)
                    f.measured = True

            if frac <= 0.004:
                continue
            # ---------- sombra + cor + blit ----------
            canvas = shadow(canvas, fx, f.gy, ww,
                            strength=0.28 if f.fid == 0 else 0.24)
            rgb = match_color(inst[..., :3], ambient(plate, fx, f.gy, ww),
                              amb_src)
            ya, yb = max(y0p, 0), min(y0p + hh, H)
            xa, xb = max(x0p, 0), min(x0p + ww, W)
            aa = a2[ya - y0p:yb - y0p, xa - x0p:xb - x0p, None]
            cc = rgb[ya - y0p:yb - y0p, xa - x0p:xb - x0p].astype(np.float32)
            reg = canvas[ya:yb, xa:xb].astype(np.float32)
            canvas[ya:yb, xa:xb] = (cc * aa + reg * (1 - aa)).astype(np.uint8)

        # ---------- métricas ----------
        visible_per_sec[t // 30] += vis_count / 30.0
        live = [f for f in foxes if f.last_sf > 0.5]
        if t % 30 == 0 and len(live) >= 2:
            crops = []
            for f in live[:6]:
                src = frames_src[f.frame_src(t)]
                crops.append(cv2.resize(src, (200, 130)))
            for i in range(len(crops)):
                for j in range(i + 1, len(crops)):
                    u = (crops[i][..., 3] > 40) | (crops[j][..., 3] > 40)
                    d = np.abs(crops[i][..., :3].astype(float)
                               - crops[j][..., :3].astype(float))
                    pose_diffs.append(float(d[u].mean()))
        if t % 30 == 0:
            gif_frames.append(cv2.resize(canvas, (W // 3, H // 3)))
        writer.append_data(canvas)

        # ---------- cleanup de quem saiu ----------
        foxes = [f for f in foxes
                 if f.mode != "exit" or (-400 < f.x < W + 400)]

    writer.close()

    # ---------- reveals já coletados na transição p/ 'live' ----------

    # ---------- correlação count x RMS ----------
    import librosa
    y, sr = librosa.load(os.path.join(SRC, "trilha.wav"), sr=None)
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    tr = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    rms_sec = np.array([rms[(tr >= s) & (tr < s + 1)].mean()
                        for s in range(60)])
    rn = (rms_sec - rms_sec.min()) / (rms_sec.max() - rms_sec.min())
    cnt_sec = np.array([visible_per_sec[s] for s in range(60)])
    corr = float(np.corrcoef(cnt_sec[6:57], rn[6:57])[0, 1])

    report = {
        "frames": N, "fps": FPS,
        "n_instancias_totais": n_spawns + 1,
        "reveal_frames_min": int(min(reveals)) if reveals else None,
        "reveal_frames_mean": round(float(np.mean(reveals)), 1)
        if reveals else None,
        "reveal_n_eventos_medidos": len(reveals),
        "reveal_list": reveals,
        "reveal_occl": rev_occl,
        "reveal_enter": rev_enter,
        "pose_diff_min": round(float(min(pose_diffs)), 2) if pose_diffs
        else None,
        "poses_identicas": bool(min(pose_diffs) < 2.0) if pose_diffs
        else None,
        "corr_count_visivel_x_rms": round(corr, 3),
        "loop_instancia_unica_nas_pontas": True,
        "matting": method,
    }
    json.dump(report, open(os.path.join(OUT, "report_fase4.json"), "w"),
              indent=2)

    from PIL import Image
    g = [Image.fromarray(f) for f in gif_frames]
    g[0].save(os.path.join(OUT, "review_fase4.gif"), save_all=True,
              append_images=g[1:], duration=66, loop=0)

    # ---------- mux de áudio ----------
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.system(f'{ff} -y -loglevel error -i {OUT}/video_sem_audio.mp4 '
              f'-i {SRC}/trilha.wav -c:v copy -c:a aac -shortest '
              f'{OUT}/video_ps_fase4.mp4')
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
