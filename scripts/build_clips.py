#!/usr/bin/env python3
"""FASE 1 — aquisição/preparação de assets do VÍDEO 3.

Gera, de forma determinística, os clipes-fonte da raposa e suas máscaras
alpha (matting):

  CLIPE A (vetor):  GIF de walk cycle 10 poses -> chroma key (fundo verde
                    sólido = filmagem controlada) -> 180 frames @30fps.
  CLIPE B (foto):   foto real -> matting rembg/u2net SE pesos disponíveis,
                    senão GrabCut (OpenCV) -> rig procedural de caminhada
                    (passo diagonal, bob, cauda) com pegada stop-motion.

Saídas (assets/build/): frames RGBA, máscaras, previews e números p/ review.
"""
import json
import os
import sys
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "src")
OUT = os.path.join(ROOT, "assets", "build")
FPS = 30
N_FRAMES = 180          # 6 s @30fps
HOLD = 3                # segura cada pose 3 frames -> pegada stop-motion 10fps


def ensure_dirs():
    for d in ("clipA_vetor", "clipB_foto"):
        os.makedirs(os.path.join(OUT, d, "frames"), exist_ok=True)
        os.makedirs(os.path.join(OUT, d, "masks"), exist_ok=True)


# ---------------------------------------------------------------- helpers
def largest_component(mask: np.ndarray) -> np.ndarray:
    n, lbl = cv2.connectedComponents(mask.astype(np.uint8))
    if n <= 1:
        return mask
    sizes = cv2.connectedComponentsWithStats(mask.astype(np.uint8))[2][:, 4]
    sizes[0] = 0
    keep = int(np.argmax(sizes))
    return (lbl == keep).astype(np.uint8) * 255


def clean_mask(m: np.ndarray, close_k=3, feather=1) -> np.ndarray:
    m = largest_component(m)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=1)
    if feather:
        m = cv2.GaussianBlur(m, (3, 3), 0.8)
    return m


def auto_crop(rgba: np.ndarray, pad=6):
    a = rgba[..., 3]
    ys, xs = np.where(a > 8)
    if len(xs) == 0:
        return rgba, (0, 0, rgba.shape[1], rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, rgba.shape[1])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, rgba.shape[0])
    return rgba[y0:y1, x0:x1], (x0, y0, x1, y1)


def write_preview(frames_rgba, path, size=None, checker=16):
    """MP4 de review: RGBA sobre tabuleiro (mostra qualidade do alpha)."""
    import imageio
    h, w = frames_rgba[0].shape[:2]
    if size:
        sc = size / max(h, w)
        w, h = int(w * sc), int(h * sc)
        frames_rgba = [cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA)
                       for f in frames_rgba]
    yy, xx = np.mgrid[0:h, 0:w]
    chk = (((yy // checker) + (xx // checker)) % 2).astype(np.float32)
    bg = np.stack([chk * 60 + 140] * 3, -1).astype(np.uint8)
    out = []
    for f in frames_rgba:
        a = (f[..., 3:4] / 255.0)
        rgb = f[..., :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)
        out.append(rgb.astype(np.uint8))
    imageio.mimwrite(path, out, fps=FPS, quality=7)


def stats(frames_rgba, name, cycle):
    cov, foot = [], []
    for f in frames_rgba:
        a = f[..., 3] > 8
        cov.append(float(a.mean()))
        ys, xs = np.where(a)
        if len(xs):
            foot.append(float(ys.max()))
    foot = np.array(foot)
    n = len(frames_rgba)
    return {
        "clip": name,
        "frames": n,
        "fps": FPS,
        "cycle_frames": cycle,
        "res": [int(frames_rgba[0].shape[1]), int(frames_rgba[0].shape[0])],
        "mask_coverage_pct": round(float(np.mean(cov)) * 100, 2),
        "foot_line_y_std_px": round(float(foot.std()), 2),
        "loop_closed": bool(n % cycle == 0 and np.array_equal(
            frames_rgba[0], frames_rgba[cycle])),
    }


# ---------------------------------------------------------------- CLIPE A
def build_clip_a():
    gif = Image.open(os.path.join(SRC, "fox_walk_vetor.gif"))
    poses = []
    for i in range(gif.n_frames):
        gif.seek(i)
        poses.append(np.array(gif.convert("RGB")))
    # cor de fundo = canto superior esquerdo (verde sólido)
    ref = poses[0][2, 2].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        pose = poses[(i // HOLD) % len(poses)]
        d = np.linalg.norm(pose.astype(np.float32) - ref, axis=-1)
        m = clean_mask((d > 60).astype(np.uint8) * 255, close_k=3)
        rgba = np.dstack([pose, m]).astype(np.uint8)
        frames.append(rgba)
    # crop comum (bbox da união) p/ todas as poses ficarem registradas
    allm = np.stack([f[..., 3] for f in frames]).max(0)
    ys, xs = np.where(allm > 8)
    x0, x1, y0, y1 = xs.min() - 6, xs.max() + 6, ys.min() - 6, ys.max() + 6
    frames = [f[y0:y1, x0:x1] for f in frames]
    return frames


# ---------------------------------------------------------------- CLIPE B
def rembg_available():
    return os.path.exists(os.path.expanduser("~/.u2net/u2net.onnx"))


def build_clip_b():
    make_plate()  # garante plate + máscara cheia (mesmo GrabCut p/ tudo)
    img = cv2.imread(os.path.join(SRC, "fox_foto_perfil.jpg"))
    if rembg_available():
        from rembg import remove, new_session
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        alpha = np.array(remove(pil, session=new_session("u2net")))[..., 3]
        method = "rembg/u2net"
    else:
        alpha = clean_mask(cv2.imread(os.path.join(SRC, "campo_mask_full.png"),
                         cv2.IMREAD_GRAYSCALE), close_k=1)
        method = "grabcut-opencv"
    rgba = np.dstack([cv2.cvtColor(img, cv2.COLOR_BGR2RGB), alpha]).astype(np.uint8)
    rgba, _ = auto_crop(rgba)
    H, W = rgba.shape[:2]
    rgb, a = rgba[..., :3].astype(np.float32), rgba[..., 3:4].astype(np.float32)

    # regiões das pernas (frações da bbox derivadas da grade do alpha):
    # [x0,x1] e fase do passo (gate diagonal: diagonal mesma fase)
    legs = [
        dict(x0=0.20, x1=0.30, ph=0.0),            # dianteira próxima
        dict(x0=0.30, x1=0.40, ph=np.pi),          # dianteira distante
        dict(x0=0.55, x1=0.64, ph=0.0),            # traseira distante
        dict(x0=0.64, x1=0.76, ph=np.pi),          # traseira próxima
    ]
    tail = dict(x0=0.76, x1=1.01, amp=0.35, ph=np.pi / 2)   # cauda: sway leve
    head = dict(x0=-0.01, x1=0.30, amp=0.12, ph=np.pi)      # cabeça: sway leve
    y_leg = 0.62  # abaixo disso = pernas (fração da altura)

    frames = []
    n_poses = 20                       # poses únicas do ciclo
    # ciclo = 20 poses * 3 holds = 60f = 2.0s -> divide 180f (loop fecha)
    for i in range(N_FRAMES):
        p = (i // (HOLD)) % n_poses
        t = 2 * np.pi * p / n_poses
        # deslocamento horizontal por região (shear c/ perfil vertical):
        # pernas = pêndulo a partir de y_leg; cauda/cabeça = sway suave.
        ys = np.arange(H)[:, None] / H
        ramp = np.clip((ys - y_leg) / (1 - y_leg), 0, 1) ** 1.5   # 0 no quadril, 1 no pé
        top = np.clip((0.50 - ys) / 0.50, 0, 1)                   # 1 no topo (cabeça)
        xs = np.arange(W)[None, :] / W
        disp = np.zeros((H, W), np.float32)
        for L in legs:
            band = ((xs >= L["x0"]) & (xs < L["x1"])).astype(np.float32)
            disp += (band * np.sin(t + L["ph"])) * ramp
        for Z in (tail, head):
            band = ((xs >= Z["x0"]) & (xs < Z["x1"])).astype(np.float32)
            prof = ramp if Z is tail else top
            disp += (band * np.sin(t + Z["ph"]) * Z["amp"]) * prof
        disp *= 0.035 * W                # amplitude no pé ~3.5% da largura
        # bob do corpo (2x a freq do passo)
        bob = int(round(0.012 * H * np.sin(2 * t)))
        map_x = (np.arange(W)[None, :] - disp).astype(np.float32)
        map_x = np.clip(map_x, 0, W - 1.001)
        map_y = np.repeat((np.arange(H) - bob)[:, None].astype(np.float32), W, 1)
        map_y = np.clip(map_y, 0, H - 1.001)
        wr = cv2.remap(rgb[..., 0], map_x, map_y, cv2.INTER_LINEAR)
        wg = cv2.remap(rgb[..., 1], map_x, map_y, cv2.INTER_LINEAR)
        wb = cv2.remap(rgb[..., 2], map_x, map_y, cv2.INTER_LINEAR)
        wa = cv2.remap(a[..., 0], map_x, map_y, cv2.INTER_LINEAR)
        frames.append(np.dstack([wr, wg, wb, wa]).astype(np.uint8))
    return frames, method


# ---------------------------------------------------------------- plate
def make_plate():
    """Plate de campo vazio: inpainting da raposa na foto de origem."""
    img = cv2.imread(os.path.join(SRC, "fox_foto_perfil.jpg"))
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * 0.30), int(h * 0.25), int(w * 0.60), int(h * 0.65))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, rect, bgd, fgd, 8, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
                 ).astype(np.uint8)
    m = largest_component(m)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    cv2.imwrite(os.path.join(SRC, "campo_mask_full.png"), m)
    md = cv2.dilate(m, np.ones((15, 15), np.uint8))
    plate = cv2.inpaint(img, md, 25, cv2.INPAINT_TELEA)
    cv2.imwrite(os.path.join(SRC, "campo_plate.jpg"), plate,
                [cv2.IMWRITE_JPEG_QUALITY, 92])


# ---------------------------------------------------------------- previews
def preview_on_plate(clip, scale_frac, ground_frac=0.80):
    """Review: raposa 'andando no lugar' sobre a plate de campo vazio."""
    import imageio
    plate = cv2.imread(os.path.join(SRC, "campo_plate.jpg"))
    d = os.path.join(OUT, clip)
    fs = sorted(os.path.join(d, "frames", f) for f in os.listdir(
        os.path.join(d, "frames")))
    frames = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in fs]
    h0, w0 = frames[0].shape[:2]
    ph, pw = plate.shape[:2]
    scale = min((ph * scale_frac) / h0, (pw * 0.5) / w0)
    nh, nw = int(h0 * scale), int(w0 * scale)
    sm = [cv2.resize(f, (nw, nh), interpolation=cv2.INTER_AREA) for f in frames]
    gy = int(ph * ground_frac)
    out_rgb = []
    for f in sm:
        a = f[..., 3:4] / 255.0
        canvas = plate.copy()
        y0, y1 = gy - nh, gy
        x0 = (pw - nw) // 2
        reg = canvas[y0:y1, x0:x0 + nw].astype(np.float32)
        canvas[y0:y1, x0:x0 + nw] = (
            f[..., :3].astype(np.float32) * a + reg * (1 - a)).astype(np.uint8)
        out_rgb.append(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    imageio.mimwrite(os.path.join(d, "preview_plate.mp4"), out_rgb,
                     fps=FPS, quality=7)
    gif = [Image.fromarray(r).resize((pw // 3, ph // 3)) for r in out_rgb[:72]]
    gif[0].save(os.path.join(d, "review_cycle.gif"), save_all=True,
                append_images=gif[1:], duration=33, loop=0)


# ---------------------------------------------------------------- main
def main():
    ensure_dirs()
    report = {}
    clipA = build_clip_a()
    for i, f in enumerate(clipA):
        cv2.imwrite(f"{OUT}/clipA_vetor/frames/f{i:03d}.png",
                    cv2.cvtColor(f, cv2.COLOR_RGBA2BGRA))
        cv2.imwrite(f"{OUT}/clipA_vetor/masks/m{i:03d}.png", f[..., 3])
    write_preview(clipA, f"{OUT}/clipA_vetor/preview_checker.mp4", size=540)
    report["clipA_vetor"] = stats(clipA, "clipA_vetor",
                                  cycle=10 * HOLD)      # 10 poses do GIF

    clipB, method = build_clip_b()
    for i, f in enumerate(clipB):
        cv2.imwrite(f"{OUT}/clipB_foto/frames/f{i:03d}.png",
                    cv2.cvtColor(f, cv2.COLOR_RGBA2BGRA))
        cv2.imwrite(f"{OUT}/clipB_foto/masks/m{i:03d}.png", f[..., 3])
    write_preview(clipB, f"{OUT}/clipB_foto/preview_checker.mp4", size=540)
    report["clipB_foto"] = stats(clipB, "clipB_foto",
                                 cycle=20 * HOLD)       # 20 poses do rig
    report["clipB_foto"]["matting_method"] = method

    preview_on_plate("clipA_vetor", scale_frac=0.45)
    preview_on_plate("clipB_foto", scale_frac=0.62)

    with open(f"{OUT}/report_fase1.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    sys.exit(main())
