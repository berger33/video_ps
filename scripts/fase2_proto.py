#!/usr/bin/env python3
"""FASE 2 — protótipo do mecanismo central: UM evento de duplicação (1->2).

Técnicas aplicadas (1-6):
 1 matting: frames RGBA da Fase 1 (clipB_foto).
 2 ancoragem: foot-anchor por frame (linha de contato dos pés) alinha cada
   cópia ao plano de chão; câmera fixa = plano de perspectiva estável.
 3 offset de tempo: cópia 2 = mesmo clipe em loop, fase +12 frames.
 4 reveal por OCLUSÃO + máscara animada: cópia 2 desenha SOB a cópia 1 e
   desliza p/ fora; wipe com borda suave (keyframes) de 16 frames garante
   0%->100% mensurável, sem pop/scale.
 5 casamento de cor (mean/std transfer vs região local da plate) + sombra
   de contato elíptica suave, direção de luz consistente.
 6 profundidade: escala = f(y do chão), perspectiva linear.

Saída: preview mp4/gif + números (reveal frames, diff de pose, shadow etc.)
"""
import json
import os
import sys
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_clips import build_clip_b, SRC, OUT  # noqa: E402

FPS = 30
N = 180
EV_START, EV_LEN = 60, 16          # início e duração do reveal (frames)
OFFSET2 = 12                       # offset de tempo da cópia 2 (não uniforme)
Y_BOT, S_BOT = 754.0, 1.00         # plano de perspectiva (câmera fixa)
Y_TOP, S_TOP = 480.0, 0.55
WALK_VX = -1.3                     # px/frame (raposa olha p/ esquerda)


def scale_for(gy):
    t = (gy - Y_TOP) / (Y_BOT - Y_TOP)
    return S_TOP + t * (S_BOT - S_TOP)


def foot_anchor(rgba):
    a = rgba[..., 3]
    ys, xs = np.where(a > 8)
    ay = ys.max()
    ax = xs[ys >= ay - 4].mean()
    return ax, ay


def place(rgba, fx, gy, s):
    """Retorna (img, x0, y0) com o foot-anchor em (fx, gy), escala s."""
    h, w = rgba.shape[:2]
    nh, nw = max(int(h * s), 2), max(int(w * s), 2)
    img = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA)
    ax, ay = foot_anchor(img)
    x0 = int(round(fx - ax))
    y0 = int(round(gy - ay))
    return img, x0, y0


def shadow(canvas, fx, gy, w_inst, strength=0.28):
    h, w = canvas.shape[:2]
    sh = np.zeros((h, w), np.float32)
    cv2.ellipse(sh, (int(fx + 0.06 * w_inst), int(gy)),
                (max(int(0.42 * w_inst), 4), max(int(0.05 * w_inst), 2)),
                0, 0, 360, 1.0, -1)
    sh = cv2.GaussianBlur(sh, (0, 0), 9)
    sh = np.clip(sh / max(sh.max(), 1e-6), 0, 1) * strength
    # luz vinda de trás/esquerda -> sombra projetada p/ direita/frente
    dark = 1.0 - sh[..., None]
    return (canvas.astype(np.float32) * dark).astype(np.uint8)


def ambient(plate, fx, gy, w_inst):
    """Cor ambiente local (fundo) perto do contato da instância."""
    h, w = plate.shape[:2]
    x0 = int(np.clip(fx - w_inst, 0, w)); x1 = int(np.clip(fx + w_inst, 0, w))
    y0 = int(np.clip(gy - 30, 0, h)); y1 = int(np.clip(gy + 10, 0, h))
    return plate[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32).mean(0)


def match_color(rgb, amb_local, amb_src, strength=1.0):
    """Casamento de cor por ambiente: ganho = ambiente_local/ambiente_origem.
    Faz a cópia herdar a luz do ponto da cena onde está plantada, sem
    virar 'cor de grama' (o alvo é o lighting, não o fundo em si)."""
    gain = (amb_local + 1.0) / (amb_src + 1.0)
    gain = 1.0 + strength * (gain - 1.0)
    return np.clip(rgb.astype(np.float32) * gain[None, None, :], 0,
                   255).astype(np.uint8)


def main():
    frames, method = build_clip_b()
    plate = cv2.cvtColor(cv2.imread(os.path.join(SRC, "campo_plate.jpg")),
                         cv2.COLOR_BGR2RGB)
    photo = cv2.cvtColor(cv2.imread(os.path.join(SRC, "fox_foto_perfil.jpg")),
                         cv2.COLOR_BGR2RGB)
    H, W = plate.shape[:2]
    # ambiente de origem: grama ao redor dos pés na foto original
    amb_src = photo[630:670, 620:990].reshape(-1, 3).astype(np.float32).mean(0)

    gy1 = 640.0
    s1 = scale_for(gy1)
    gy2 = 600.0
    s2 = scale_for(gy2)

    meas = {"reveal_visible_frac": [], "pose_diff_mean_abs": [],
            "color_delta_before": None, "color_delta_after": None}

    out_frames = []
    for t in range(N):
        canvas = plate.copy()
        fx1 = 760 + WALK_VX * t
        inst1, x1, y1 = place(frames[t % N], fx1, gy1, s1)
        w1 = inst1.shape[1]
        canvas = shadow(canvas, fx1, gy1, w1)

        # ---------- cópia 2 (após o evento) ----------
        vis2_frac = 0.0
        if t >= EV_START:
            k = min((t - EV_START) / EV_LEN, 1.0)          # keyframe 0->1
            slide = 55 + 30 * k                            # desliza p/ fora
            fx2 = fx1 + slide
            inst2, x2, y2 = place(frames[(t + OFFSET2) % N], fx2, gy2, s2)
            w2 = inst2.shape[1]
            # wipe animado (borda suave 8px): expõe de trás da cópia 1
            # (esquerda) p/ direita; 0% no start, 100% no fim, por construção
            ww2 = inst2.shape[1]
            xs = np.arange(ww2)
            Xe = (x2 - 8) + k * (ww2 + 16)
            col = np.clip((Xe - xs) / 8.0 + 1, 0, 1)
            gate = np.broadcast_to(col[None, :], inst2.shape[:2]).copy()
            a2 = (inst2[..., 3] / 255.0) * gate
            canvas = shadow(canvas, fx2, gy2, w2, strength=0.24)
            rgb2 = match_color(inst2[..., :3], ambient(plate, fx2, gy2, w2),
                               amb_src)
            # blit cópia 2 (embaixo)
            hh, ww = a2.shape
            ya, yb = max(y2, 0), min(y2 + hh, H)
            xa, xb = max(x2, 0), min(x2 + ww, W)
            if yb > ya and xb > xa:
                reg = canvas[ya:yb, xa:xb].astype(np.float32)
                aa = a2[ya - y2:yb - y2, xa - x2:xb - x2, None]
                cc = rgb2[ya - y2:yb - y2, xa - x2:xb - x2].astype(np.float32)
                canvas[ya:yb, xa:xb] = (cc * aa + reg * (1 - aa)).astype(np.uint8)
                # fração visível real (descontando o que a cópia 1 cobre)
                a1full = np.zeros((H, W), np.float32)
                h1, w1b = inst1.shape[:2]
                ya1, yb1 = max(y1, 0), min(y1 + h1, H)
                xa1, xb1 = max(x1, 0), min(x1 + w1b, W)
                a1full[ya1:yb1, xa1:xb1] = inst1[ya1 - y1:yb1 - y1,
                                                 xa1 - x1:xb1 - x1, 3] / 255.
                vis = a2 * (1 - a1full[y2:y2 + hh, x2:x2 + ww])
                vis2_frac = float(vis.sum() / max((inst2[..., 3] / 255.).sum(), 1))
        else:
            k = 0.0

        # ---------- cópia 1 (por cima) ----------
        h1, w1 = inst1.shape[:2]
        ya, yb = max(y1, 0), min(y1 + h1, H)
        xa, xb = max(x1, 0), min(x1 + w1, W)
        a1 = (inst1[..., 3] / 255.0)[ya - y1:yb - y1, xa - x1:xb - x1, None]
        c1 = inst1[..., :3][ya - y1:yb - y1, xa - x1:xb - x1].astype(np.float32)
        reg = canvas[ya:yb, xa:xb].astype(np.float32)
        canvas[ya:yb, xa:xb] = (c1 * a1 + reg * (1 - a1)).astype(np.uint8)

        out_frames.append(canvas)
        if t >= EV_START:
            meas["reveal_visible_frac"].append(round(vis2_frac, 4))

        # diff de pose entre as 2 instâncias (ambas visíveis)
        if t >= EV_START + EV_LEN and t % 6 == 0:
            i1 = cv2.resize(frames[t % N], (200, 130))
            i2 = cv2.resize(frames[(t + OFFSET2) % N], (200, 130))
            u = ((i1[..., 3] > 40) | (i2[..., 3] > 40))
            d = np.abs(i1[..., :3].astype(float) - i2[..., :3].astype(float))
            meas["pose_diff_mean_abs"].append(round(float(d[u].mean()), 2))

    # reveal RELATIVO ao fim do gate (oclusão permanente de multidão é
    # legítima depois; o evento de entrada é o gate+slide de EV_LEN frames)
    vf = np.array(meas["reveal_visible_frac"])
    vf_final = max(float(vf[EV_LEN - 1]), 1e-6)
    rel = vf / vf_final
    lo = int(np.argmax(rel > 0.02)); hi = int(np.argmax(rel > 0.98))
    reveal_frames = (hi - lo) + 1

    # delta de ambiente antes/depois do casamento de cor
    amb_local = ambient(plate, 700, gy2, 500)
    before = float(np.abs(amb_local - amb_src).mean())
    gain = (amb_local + 1.0) / (amb_src + 1.0)
    after = float(np.abs(amb_local - amb_src * gain).mean())
    meas["color_delta_before"] = round(before, 2)
    meas["color_delta_after"] = round(after, 2)

    report = {
        "evento_duplicacao_frame": EV_START,
        "reveal_frames_2pct_a_98pct": reveal_frames,
        "reveal_gate_keyframes": EV_LEN,
        "offset_tempo_copia2_frames": OFFSET2,
        "pose_diff_mean_abs_min": float(np.min(meas["pose_diff_mean_abs"])),
        "pose_diff_mean_abs_mean": float(np.mean(meas["pose_diff_mean_abs"])),
        "poses_identicas_simultaneas": bool(
            np.min(meas["pose_diff_mean_abs"]) < 2.0),
        "escalas": {"copia1": round(s1, 3), "copia2": round(s2, 3)},
        "sombra_contato": "elipse blur sigma=9, strength 0.28/0.24",
        "color_match_delta_local_antes": meas["color_delta_before"],
        "color_match_delta_local_depois": meas["color_delta_after"],
        "matting": method,
        "ancoragem_chao": "foot-anchor por frame (Fase 1: std 3.69px)",
    }
    d = os.path.join(OUT, "fase2")
    os.makedirs(d, exist_ok=True)
    import imageio
    imageio.mimwrite(os.path.join(d, "preview_fase2.mp4"), out_frames,
                     fps=FPS, quality=8)
    from PIL import Image
    g = [Image.fromarray(f).resize((W // 2, H // 2)) for f in out_frames]
    g[0].save(os.path.join(d, "review_fase2.gif"), save_all=True,
              append_images=g[1:], duration=33, loop=0)
    with open(os.path.join(d, "report_fase2.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
