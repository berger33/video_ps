#!/usr/bin/env python3
"""Fase 1 — isola o pombo (chroma key) e gera clipes curtos em loop.

Uso (raiz do repo):
    .venv/bin/python scripts/prepare_assets.py
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
ISOLATED = ROOT / "assets" / "isolated"
MASKS = ROOT / "assets" / "masks"
CLIPS = ROOT / "assets" / "clips"
PREVIEWS = ROOT / "assets" / "previews"

FPS = 30
DURATION = 4.0
N_FRAMES = int(FPS * DURATION)
CLIP_W, CLIP_H = 1280, 720
BG_RGB = (58, 61, 64)  # #3A3D40
TARGET_SPRITE_H = 390
FOOT_DEST = (CLIP_W * 0.50, CLIP_H * 0.78)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

HERO = "idle"
POSE_FILES = {
    "idle": "var_a_classic.jpg",
    "peck": "pose_peck.jpg",
    "coo": "pose_coo.jpg",
    "fluff": "pose_fluff.jpg",
    "walk_a": "pose_walk_a.jpg",
    "walk_b": "pose_walk_b.jpg",
    "head_turn": "pose_head_turn.jpg",
}
VARIATIONS = {
    "var_a_classic": "var_a_classic.jpg",
    "var_b_checker": "var_b_checker.jpg",
    "var_c_pale": "var_c_pale.jpg",
    "var_d_dark": "var_d_dark.jpg",
}


@dataclass
class Sprite:
    name: str
    bgra: np.ndarray
    pivot: tuple[float, float]
    fill_ratio: float
    bbox_wh: tuple[int, int]


def smoothstep(x: np.ndarray | float, a: float, b: float):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def chroma_key(bgr: np.ndarray) -> np.ndarray:
    """Soft green-screen pull + despill. Returns BGRA uint8."""
    bgr_f = bgr.astype(np.float32)
    b, g, r = cv2.split(bgr_f)
    ge = g - np.maximum(r, b)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    green_hue = (h >= 32) & (h <= 92) & (s >= 50)

    # High green-excess is background. Soft band avoids rectangular mattes.
    alpha = 1.0 - smoothstep(ge, 10.0, 46.0)
    alpha = np.where(green_hue & (ge > 28), np.minimum(alpha, 0.15), alpha)
    alpha = np.where(ge < 8.0, np.maximum(alpha, 0.92), alpha)
    alpha = np.clip(alpha, 0.0, 1.0)

    hard = (alpha > 0.45).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, kernel)
    hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(hard, 8)
    if n > 1:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(labels == keep, 255, 0).astype(np.uint8)
    else:
        fg = hard

    # Fill tiny body holes; keep the gap between legs (lower holes).
    inv = 255 - fg
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 8)
    h_img, w_img = fg.shape
    ys, xs = np.where(fg > 0)
    if len(ys):
        y0, y1 = int(ys.min()), int(ys.max())
        body_cut = y0 + 0.68 * (y1 - y0)
    else:
        body_cut = h_img
    for i in range(1, n2):
        x, y, bw, bh, area = (int(st2[i, j]) for j in range(5))
        touches = x <= 0 or y <= 0 or x + bw >= w_img - 1 or y + bh >= h_img - 1
        if touches:
            continue
        cy = y + bh * 0.5
        if area < 90 or (area < 380 and cy < body_cut):
            fg[lab2 == i] = 255

    fg = cv2.erode(fg, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    # Alpha comes from the cleaned silhouette only — never from green-excess
    # inside the bird (iridescent neck must stay opaque).
    soft = cv2.GaussianBlur(fg.astype(np.float32), (5, 5), 0) / 255.0
    alpha = np.clip(soft, 0.0, 1.0)

    # Despill: pull residual green toward magenta-neutral.
    ge_pos = np.maximum(ge, 0.0)
    g2 = g - ge_pos * (0.70 * (1.0 - alpha) + 0.35 * alpha)
    g2 = np.minimum(g2, np.maximum(r, b) * 1.04 + 6.0)
    out_bgr = np.stack([b, np.clip(g2, 0, 255), r], axis=-1)
    bgra = np.dstack([out_bgr, alpha * 255.0]).astype(np.uint8)
    return bgra


def feet_pivot(alpha: np.ndarray) -> tuple[float, float]:
    ys, xs = np.where(alpha > 120)
    if len(ys) == 0:
        h, w = alpha.shape
        return w / 2.0, h * 0.9
    y_cut = np.quantile(ys, 0.90)
    foot_xs = xs[ys >= y_cut]
    foot_ys = ys[ys >= y_cut]
    return float(foot_xs.mean()), float(foot_ys.max())


def crop_sprite(bgra: np.ndarray, pad: int = 28) -> tuple[np.ndarray, tuple[float, float], float]:
    alpha = bgra[:, :, 3]
    ys, xs = np.where(alpha > 12)
    if len(xs) == 0:
        raise RuntimeError("chroma key produced empty matte")
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(bgra.shape[1] - 1, x1 + pad)
    y1 = min(bgra.shape[0] - 1, y1 + pad)
    cropped = bgra[y0 : y1 + 1, x0 : x1 + 1].copy()
    px, py = feet_pivot(cropped[:, :, 3])
    bbox = (x1 - x0 + 1, y1 - y0 + 1)
    fill = float((cropped[:, :, 3] > 120).sum()) / float(bbox[0] * bbox[1])
    return cropped, (px, py), fill


def load_sprite(name: str, filename: str) -> Sprite:
    path = RAW / filename
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    bgra = chroma_key(bgr)
    cropped, pivot, fill = crop_sprite(bgra)
    MASKS.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(MASKS / f"{name}_alpha.png"), cropped[:, :, 3])
    ISOLATED.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ISOLATED / f"{name}.png"), cropped)
    return Sprite(name, cropped, pivot, fill, (cropped.shape[1], cropped.shape[0]))


def checkerboard(h: int, w: int, cell: int = 16) -> np.ndarray:
    yy, xx = np.indices((h, w))
    field = ((xx // cell) + (yy // cell)) % 2
    img = np.where(field[..., None] == 0, 210, 160).astype(np.uint8)
    return np.repeat(img, 3, axis=2)


def composite_on(bg_bgr: np.ndarray, sprite: np.ndarray) -> np.ndarray:
    a = sprite[:, :, 3:4].astype(np.float32) / 255.0
    out = bg_bgr.astype(np.float32) * (1.0 - a) + sprite[:, :, :3].astype(np.float32) * a
    return np.clip(out, 0, 255).astype(np.uint8)


def warp_sprite(sprite: Sprite, dest_xy, angle_deg: float, scale: float, canvas_wh) -> np.ndarray:
    h, w = canvas_wh[1], canvas_wh[0]
    px, py = sprite.pivot
    M = cv2.getRotationMatrix2D((px, py), angle_deg, scale)
    M[0, 2] += dest_xy[0] - px
    M[1, 2] += dest_xy[1] - py
    return cv2.warpAffine(
        sprite.bgra,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def blend_bgra(a: np.ndarray, b: np.ndarray, w: float) -> np.ndarray:
    w = float(np.clip(w, 0.0, 1.0))
    aa = a[:, :, 3:4].astype(np.float32) * (1.0 - w)
    ba = b[:, :, 3:4].astype(np.float32) * w
    denom = np.maximum(aa + ba, 1.0)
    rgb = (a[:, :, :3].astype(np.float32) * aa + b[:, :, :3].astype(np.float32) * ba) / denom
    alpha = np.clip(aa + ba, 0, 255)
    return np.dstack([rgb, alpha]).astype(np.uint8)


def contact_shadow(canvas_bgr: np.ndarray, dest_xy, scale: float) -> np.ndarray:
    overlay = np.zeros((CLIP_H, CLIP_W), np.float32)
    cx, cy = int(dest_xy[0]), int(dest_xy[1] + 6)
    axes = (int(110 * scale), int(16 * scale))
    cv2.ellipse(overlay, (cx, cy), axes, 0, 0, 360, 1.0, -1)
    overlay = cv2.GaussianBlur(overlay, (31, 15), 0)
    overlay = np.clip(overlay * 0.38, 0, 1)[..., None]
    out = canvas_bgr.astype(np.float32) * (1.0 - overlay)
    return np.clip(out, 0, 255).astype(np.uint8)


def ease_in_out(t: float) -> float:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def pulse(t: float, period: float, attack: float, hold: float, release: float) -> float:
    """0 at period boundaries. attack+hold+release < period."""
    x = t % period
    if x < attack:
        return ease_in_out(x / attack)
    if x < attack + hold:
        return 1.0
    if x < attack + hold + release:
        return 1.0 - ease_in_out((x - attack - hold) / release)
    return 0.0


def keyframe_weight(t: float, keys: list[tuple[float, str]]) -> dict[str, float]:
    """Periodic keys at times in [0, 1). Last should match first name."""
    t = t % 1.0
    times = [k[0] for k in keys]
    names = [k[1] for k in keys]
    for i in range(len(keys) - 1):
        t0, t1 = times[i], times[i + 1]
        if t0 <= t <= t1 or (t0 == t1):
            span = t1 - t0 if t1 > t0 else 1.0
            u = 0.0 if span == 0 else (t - t0) / span
            u = ease_in_out(u)
            w = {n: 0.0 for n in set(names)}
            w[names[i]] += 1.0 - u
            w[names[i + 1]] += u
            return w
    w = {n: 0.0 for n in set(names)}
    w[names[0]] = 1.0
    return w


def pose_layer(sprites: dict[str, Sprite], weights: dict[str, float], dest, angle, scale) -> np.ndarray:
    """Cut-out: uma pose de cada vez. Crossfade cria cabeça-dupla e falha o gate."""
    items = [(n, wt) for n, wt in weights.items() if wt > 1e-4]
    if not items:
        return np.zeros((CLIP_H, CLIP_W, 4), np.uint8)
    name = max(items, key=lambda kv: kv[1])[0]
    return warp_sprite(sprites[name], dest, angle, scale, (CLIP_W, CLIP_H))


def clip_scale(sprites: dict[str, Sprite]) -> float:
    h = sprites["idle"].bgra.shape[0]
    return TARGET_SPRITE_H / float(h)


def render_motion(name: str, t: float, sprites: dict[str, Sprite], scale: float) -> np.ndarray:
    dest = list(FOOT_DEST)
    angle = 0.0
    sc = scale
    weights = {"idle": 1.0}

    if name == "idle_bob":
        bob = math.sin(2 * math.pi * t / 0.8)
        dest[1] += 7.0 * bob
        angle = 1.4 * bob
        weights = {"idle": 1.0}
    elif name == "walk_in_place":
        cycle = (t / 0.5)  # 2 steps / s → period 0.5s maps poorly; use 1s cycle
        u = (t % 1.0)
        keys = [(0.0, "idle"), (0.22, "walk_a"), (0.50, "idle"), (0.72, "walk_b"), (1.0, "idle")]
        weights = keyframe_weight(u, keys)
        bob = math.sin(2 * math.pi * t * 2.0)
        dest[1] += 9.0 * bob
        dest[0] += 5.0 * math.sin(2 * math.pi * t)
        angle = 2.2 * bob
    elif name == "peck":
        w = pulse(t, 2.0, 0.16, 0.50, 0.22)
        weights = {"idle": 1.0 - w, "peck": w}
        dest[1] += 3.0 * w
        angle = -3.0 * w
    elif name == "coo":
        w = pulse(t, 4.0, 0.45, 1.35, 0.50)
        weights = {"idle": 1.0 - w, "coo": w}
        sc = scale * (1.0 + 0.03 * w)
        angle = -1.5 * w
    elif name == "fluff":
        w = pulse(t, 2.0, 0.28, 0.22, 0.35)
        weights = {"idle": 1.0 - w, "fluff": w}
        sc = scale * (1.0 + 0.04 * w)
        angle = 2.0 * math.sin(2 * math.pi * t)
    elif name == "head_turn":
        w = pulse(t, 4.0, 0.40, 1.50, 0.45)
        weights = {"idle": 1.0 - w, "head_turn": w}
        dest[1] += 3.0 * math.sin(2 * math.pi * t / 0.8) * (1.0 - 0.5 * w)
    elif name == "weight_shift":
        s = math.sin(2 * math.pi * t / 4.0)
        angle = 4.5 * s
        dest[0] += 14.0 * s
        dest[1] += 4.0 * abs(s)
        weights = {"idle": 1.0}
    elif name == "strut":
        u = t % 1.0
        keys = [(0.0, "idle"), (0.25, "walk_a"), (0.50, "walk_b"), (0.75, "walk_a"), (1.0, "idle")]
        weights = keyframe_weight(u, keys)
        bob = math.sin(2 * math.pi * t * 2.0)
        dest[1] += 11.0 * bob
        dest[0] += 8.0 * math.sin(2 * math.pi * t)
        angle = 3.0 * bob
        sc = scale * (1.0 + 0.02 * abs(bob))
    else:
        raise KeyError(name)

    bg = np.full((CLIP_H, CLIP_W, 3), BG_RGB[::-1], np.uint8)  # BGR
    bg = contact_shadow(bg, dest, sc / scale)
    layer = pose_layer(sprites, weights, dest, angle, sc)
    return composite_on(bg, layer)


CLIP_NAMES = [
    ("idle_bob", "idle + head-bob (pivô nos pés)"),
    ("walk_in_place", "passo no sítio idle↔walk_a↔walk_b"),
    ("peck", "bicar o chão, 2x / 4s"),
    ("coo", "garganta inflada (display)"),
    ("fluff", "eriçar / abrir a asa"),
    ("head_turn", "virar a cabeça à câmara"),
    ("weight_shift", "transferência de peso, 1 ciclo / 4s"),
    ("strut", "passo + bob mais amplo"),
]


def write_mp4(path: Path, frame_iter, n: int, fps: int, w: int, h: int) -> None:
    cmd = [
        FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-", "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-preset", "medium", "-movflags", "+faststart",
        str(path),
    ]
    log_path = path.with_suffix(".ffmpeg.log")
    with open(log_path, "wb") as logf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logf)
        assert proc.stdin is not None
        try:
            for i, frame in enumerate(frame_iter):
                if frame.shape[1] != w or frame.shape[0] != h:
                    raise RuntimeError(f"frame {i} shape {frame.shape} != {(h, w)}")
                proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        finally:
            proc.stdin.close()
            proc.wait()
    if proc.returncode != 0:
        err = log_path.read_text(encoding="utf-8", errors="ignore")[-2000:]
        raise RuntimeError(err)
    log_path.unlink(missing_ok=True)


def mp4_to_gif(mp4: Path, gif: Path, width: int = 480, fps: int = 12) -> None:
    filt = (
        f"fps={fps},scale={width}:-2:flags=lanczos,"
        f"split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=full[p];"
        f"[s1][p]paletteuse=dither=bayer:bayer_scale=3"
    )
    cmd = [FFMPEG, "-y", "-i", str(mp4), "-vf", filt, "-loop", "0", str(gif)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-2000:])


def extract_frame(mp4: Path, index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(mp4))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if index < 0:
        index = n + index
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"could not read frame {index} of {mp4}")
    return frame


def count_instances(frame_bgr: np.ndarray) -> int:
    """Count large foreground blobs. H264 ringing is merged with a close."""
    bg = frame_bgr[8:16, 8:16].reshape(-1, 3).mean(axis=0).astype(np.int16)
    diff = np.abs(frame_bgr.astype(np.int16) - bg).max(axis=2)
    mask = (diff > 30).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return 0
    areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, n)]
    dominant = max(areas)
    return sum(1 for a in areas if a >= max(8000, int(0.35 * dominant)))


def rectangular_artifact(frame_bgr: np.ndarray) -> bool:
    bg = np.array(BG_RGB[::-1], np.int16)
    diff = np.abs(frame_bgr.astype(np.int16) - bg).max(axis=2)
    mask = (diff > 22).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    for i in range(1, n):
        x, y, w, h, area = (int(stats[i, j]) for j in range(5))
        if area < 800:
            continue
        fill = area / float(w * h)
        # A pasted rectangle fills its bbox almost completely and is axis-aligned.
        roi = mask[y : y + h, x : x + w]
        # Straight-edge score: fraction of bbox perimeter that is ON
        if w > 40 and h > 40 and fill > 0.92:
            return True
        top, bot = roi[0].mean(), roi[-1].mean()
        left, right = roi[:, 0].mean(), roi[:, -1].mean()
        if fill > 0.84 and min(top, bot, left, right) > 200:
            return True
    return False


def mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def label_bar(img_bgr: np.ndarray, text: str) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    bar_h = 36
    canvas = np.zeros((h + bar_h, w, 3), np.uint8)
    canvas[:] = (32, 32, 32)
    canvas[bar_h:] = img_bgr
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil)
    font = ImageFont.truetype(FONT_PATH, 16)
    draw.text((10, 8), text, font=font, fill=(235, 235, 230))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def contact_sheet_stills(sprites: dict[str, Sprite], variations: dict[str, Sprite], path: Path) -> None:
    items = list(variations.items()) + [(f"pose:{k}", v) for k, v in sprites.items()]
    cols = 4
    cell_w, cell_h = 320, 220
    rows = math.ceil(len(items) / cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (36, 38, 40))
    font = ImageFont.truetype(FONT_PATH, 14)
    for i, (name, sp) in enumerate(items):
        r, c = divmod(i, cols)
        chk = checkerboard(cell_h - 28, cell_w, 12)
        h, w = sp.bgra.shape[:2]
        sc = min((cell_w - 20) / w, (cell_h - 48) / h)
        nw, nh = max(1, int(w * sc)), max(1, int(h * sc))
        resized = cv2.resize(sp.bgra, (nw, nh), interpolation=cv2.INTER_AREA)
        x = (cell_w - nw) // 2
        y = (cell_h - 28 - nh) // 2
        roi = chk[y : y + nh, x : x + nw]
        chk[y : y + nh, x : x + nw] = composite_on(roi, resized)
        cell = np.full((cell_h, cell_w, 3), (36, 38, 40), np.uint8)
        cell[28:] = chk
        rgb = cv2.cvtColor(cell, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        ImageDraw.Draw(pil).text((8, 6), name, font=font, fill=(230, 230, 225))
        sheet.paste(pil, (c * cell_w, r * cell_h))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=92)


def write_index(sprites: dict[str, Sprite], report: dict, path: Path) -> None:
    lines = [
        "# Fase 1 — índice de assets",
        "",
        "**Peça:** COO · **sujeito:** pombo-das-rochas (variação A, clássica)",
        "**Modelo de geração:** API de imagem da sessão Arena (text-to-image para 4 variações;",
        "img2img a partir de `var_a_classic.jpg` para as poses). O checkpoint interno não é",
        "exposto pela ferramenta — não inventar nome de modelo.",
        "",
        "## Variações visuais (mín. 4)",
        "",
        "| id | ficheiro | escolha |",
        "|----|----------|---------|",
        "| A clássica | `assets/raw/var_a_classic.jpg` | **HERÓI** — silhueta limpa, barras negras, iridescência, chroma uniforme |",
        "| B checker | `assets/raw/var_b_checker.jpg` | reserva (padrão manchado, enfrenta o lado oposto) |",
        "| C pale | `assets/raw/var_c_pale.jpg` | reserva (cinza-prata, menos contraste) |",
        "| D dark | `assets/raw/var_d_dark.jpg` | reserva (melanística; chroma com gradiente, pior para key) |",
        "",
        "Clipes e recortes de produção usam **apenas A** + poses img2img derivadas de A.",
        "",
        "## Stills isolados (RGBA)",
        "",
        "| pose | png | pivot pés (x,y) | fill ratio bbox |",
        "|------|-----|-----------------|-----------------|",
    ]
    for n, sp in sprites.items():
        lines.append(
            f"| `{n}` | `assets/isolated/{n}.png` | "
            f"{sp.pivot[0]:.1f}, {sp.pivot[1]:.1f} | {sp.fill_ratio:.3f} |"
        )
    lines += [
        "",
        "Fill ratio ≪ 1.0 = silhueta orgânica (não é um retângulo colado).",
        "",
        "## Clipes 4.0 s · 30 fps · 1280×720 · loop",
        "",
        "Fundo neutro `#3A3D40`. Câmera fixa. Uma instância do sujeito.",
        "Animação: puppet cut-out (rotação/escala em torno dos pés; uma pose visível de cada vez).",
        "",
        "| ficheiro | movimento |",
        "|----------|-----------|",
    ]
    for cid, desc in CLIP_NAMES:
        lines.append(f"| `assets/clips/{cid}.mp4` · `{cid}.gif` | {desc} |")
    lines += [
        "",
        "## Preview",
        "",
        "- grelha de todos os loops: `assets/previews/fase1_mosaic.mp4` / `.gif`",
        "- contact sheet dos recortes: `assets/previews/fase1_stills.jpg`",
        "",
        "## Regenerar",
        "",
        "```",
        ".venv/bin/python scripts/prepare_assets.py",
        "```",
        "",
        "## Checklist de autoverificação",
        "",
        f"- Instâncias no frame final de cada clipe: **{report['instances']}** "
        "(esperado = 1 nesta fase; a multiplicação é a Fase 2).",
        f"- Primeiro e último frame compatíveis para loop: **{report['loop']}** "
        f"(MAE médio last↔first = {report['mae_mean']:.2f}; MAE médio frame0↔frame1 = {report['mae_step']:.2f}; "
        "salto de loop ≤ ~1 frame de movimento).",
        f"- Artefacto de bloco/retângulo estático: **{report['rect']}**.",
        f"- Picos de distorção/multiplicação: **N/A** — Fase 1 é o sujeito isolado, "
        "sem proliferação. O head-bob / peck / fluff têm picos de pose, não de contagem.",
        "",
        f"Relatório bruto: `assets/previews/fase1_checklist.json`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    for d in (ISOLATED, MASKS, CLIPS, PREVIEWS):
        d.mkdir(parents=True, exist_ok=True)

    print("→ chroma key / isolate")
    sprites = {name: load_sprite(name, fn) for name, fn in POSE_FILES.items()}
    variations = {name: load_sprite(name, fn) for name, fn in VARIATIONS.items()}
    for n, sp in sprites.items():
        print(f"   {n:12s}  fill={sp.fill_ratio:.3f}  size={sp.bbox_wh}  pivot={sp.pivot}")
        if sp.fill_ratio > 0.88:
            print("   !! fill ratio alto demais — possível matte rectangular", file=sys.stderr)

    scale = clip_scale(sprites)
    contact_sheet_stills(sprites, variations, PREVIEWS / "fase1_stills.jpg")

    print("→ clipes")
    loop_maes = []
    step_maes = []
    inst_final = []
    rect_flags = []

    for cid, desc in CLIP_NAMES:
        print(f"   {cid}")

        def frames(cid=cid):
            for i in range(N_FRAMES):
                t = i / FPS
                yield render_motion(cid, t, sprites, scale)

        mp4 = CLIPS / f"{cid}.mp4"
        write_mp4(mp4, frames(), N_FRAMES, FPS, CLIP_W, CLIP_H)
        mp4_to_gif(mp4, CLIPS / f"{cid}.gif")

        first = extract_frame(mp4, 0)
        second = extract_frame(mp4, 1)
        last = extract_frame(mp4, -1)
        loop_maes.append(mae(first, last))
        step_maes.append(mae(first, second))
        inst_final.append(count_instances(last))
        rect_flags.append(rectangular_artifact(last) or rectangular_artifact(first))
        cv2.imwrite(str(PREVIEWS / f"{cid}_first.jpg"), first)
        cv2.imwrite(str(PREVIEWS / f"{cid}_last.jpg"), last)

    print("→ mosaic")

    def mosaic_frames():
        cols, rows = 4, 2
        cw, ch = CLIP_W // cols, CLIP_H // rows
        for i in range(N_FRAMES):
            t = i / FPS
            canvas = np.full((CLIP_H, CLIP_W, 3), (24, 24, 24), np.uint8)
            for k, (cid, desc) in enumerate(CLIP_NAMES):
                r, c = divmod(k, cols)
                cell = render_motion(cid, t, sprites, scale)
                cell = cv2.resize(cell, (cw, ch), interpolation=cv2.INTER_AREA)
                cell = label_bar(cell, cid)
                cell = cv2.resize(cell, (cw, ch), interpolation=cv2.INTER_AREA)
                y, x = r * ch, c * cw
                canvas[y : y + ch, x : x + cw] = cell
            yield canvas

    write_mp4(PREVIEWS / "fase1_mosaic.mp4", mosaic_frames(), N_FRAMES, FPS, CLIP_W, CLIP_H)
    mp4_to_gif(PREVIEWS / "fase1_mosaic.mp4", PREVIEWS / "fase1_mosaic.gif", width=960, fps=12)

    instances = inst_final
    all_one = all(n == 1 for n in instances)
    any_rect = any(rect_flags)
    mae_mean = float(np.mean(loop_maes))
    mae_step = float(np.mean(step_maes))
    # Loop is compatible if last→first jump is on the order of one in-clip frame step.
    loop_ok = mae_mean <= mae_step * 2.5 + 4.0

    report = {
        "instances_per_clip_final": instances,
        "instances": "1 em todos" if all_one else str(instances),
        "loop": "sim" if loop_ok else "não",
        "mae_mean": mae_mean,
        "mae_step": mae_step,
        "mae_last_vs_first": loop_maes,
        "rect": "não" if not any_rect else "sim",
        "fill_ratios": {n: sp.fill_ratio for n, sp in sprites.items()},
    }
    (PREVIEWS / "fase1_checklist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_index(sprites, report, ROOT / "assets" / "INDEX.md")

    print("\nCHECKLIST")
    print(json.dumps(report, indent=2))
    if any_rect:
        print("FALHA: artefacto rectangular — não entregar.", file=sys.stderr)
        return 2
    if not all_one:
        print("AVISO: instâncias != 1 (Fase 1 espera 1).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
