#!/usr/bin/env python3
"""FASE 1 — painel de aprovacao (contact sheet + checagem de alpha).

Gera assets/preview/ com:
  - painel_fase1.png      painel geral para aprovacao humana
  - alpha_check.png       sprites sobre tabuleiro (checagem de alfa/sombra)
  - sprites/ (copy)       sprites RGBA para inspecao direta

Uso: tools/venv/bin/python tools/preview_fase1.py
"""
from __future__ import annotations

import os
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIP = os.path.join(ROOT, "crie_de_outro_video_de_pombo.mp4")
STAB = os.path.join(ROOT, "assets", "plates", "w370_442", "stab")
SPR = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "assets", "preview")

WALK_FRAMES = [160, 169, 178, 187, 196, 205, 220, 235]
PECK_FRAMES = [388, 392, 395, 397, 399, 400, 401, 403, 406, 412]
PECK_CONTACT = 400

COLS = 4
CELL_W = 372
CELL_H = 210
MARGIN = 14
GAP = 10
FONT = 15


def font(sz: int = FONT):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sz)
    except OSError:
        return ImageFont.load_default(sz)


def mono(path: str) -> np.ndarray:
    return cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)


def rgb_from_clip(frames: list[int]) -> list[np.ndarray]:
    cap = cv2.VideoCapture(CLIP)
    out: dict[int, np.ndarray] = {}
    i = 0
    want = set(frames)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            out[i] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        i += 1
    cap.release()
    return [out[i] for i in frames]


def checker(h: int, w: int, sq: int = 16) -> np.ndarray:
    g = np.zeros((h, w, 3), np.uint8)
    for y in range(0, h, sq):
        for x in range(0, w, sq):
            v = 205 if ((x // sq) + (y // sq)) % 2 == 0 else 245
            g[y : y + sq, x : x + sq] = v
    return g


def cell(img: np.ndarray, h: int = CELL_H, w: int = CELL_W) -> np.ndarray:
    r = min(w / img.shape[1], h / img.shape[0])
    nw, nh = int(img.shape[1] * r), int(img.shape[0] * r)
    im = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), 250, np.uint8)
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    out[y0 : y0 + nh, x0 : x0 + nw] = im
    return out


def section_title(draw: ImageDraw.ImageDraw, y: int, text: str) -> int:
    draw.text((MARGIN, y), text, fill=(20, 20, 25), font=font(17))
    return y + 26


def row_of(draw: ImageDraw.ImageDraw, imgs: list[np.ndarray], labels: list[str],
           y: int, hl: int | None = None) -> int:
    k = 0
    while k < len(imgs):
        x = MARGIN
        for j in range(COLS):
            if k + j >= len(imgs):
                break
            c = cell(imgs[k + j])
            base = Image.fromarray(c)
            d = ImageDraw.Draw(base)
            color = (20, 20, 25) if k + j != hl else (200, 40, 20)
            d.rectangle([0, 0, CELL_W - 1, CELL_H - 1],
                        outline=(230, 230, 235, 255), width=2)
            d.text((6, 4), labels[k + j], fill=color, font=font())
            panel.paste(base, (x, y))
            x += CELL_W + GAP
        y += CELL_H + GAP
        k += COLS
    return y


def make_panel() -> None:
    global panel
    rows = 2 + 2 + 1
    W = MARGIN * 2 + COLS * CELL_W + (COLS - 1) * GAP
    # altura estimada
    H = (MARGIN + 34) + section_h() * 1 + 2 * (2 * CELL_H + GAP) + \
        section_h() + (2 * CELL_H + GAP) + section_h() + (CELL_H + 60) + MARGIN
    panel = Image.new("RGB", (W, H + 40), (252, 252, 254))
    draw = ImageDraw.Draw(panel)
    draw.text((MARGIN, MARGIN - 2),
              "POMBO//PROTOCOLO — FASE 1 — PAINEL DE APROVAÇÃO DE ASSETS (24 fps, 1280×720)",
              fill=(10, 10, 12), font=font(19))
    y = MARGIN + 30

    y = section_title(draw, y, "A) JANELA DE CAMINHADA f160–235 — bloco 0:00–0:15 (pan 1,6 px/f, nitidez alta)")
    walk = rgb_from_clip(WALK_FRAMES)
    labels = [f"f{i}" for i in WALK_FRAMES]
    y = row_of(draw, walk[:COLS], labels[:COLS], y)
    y = row_of(draw, walk[COLS:], labels[COLS:], y)

    y = section_title(draw, y, "B) BICADA — janela f370–442 ESTABILIZADA (residual 0,53 px; bico toca o chão em f400, marcado)")
    stab = [mono(os.path.join(STAB, f"s{i}.png")) for i in PECK_FRAMES]
    labels = [f"f{i}" + ("  ← CONTATO" if i == PECK_CONTACT else "") for i in PECK_FRAMES]
    hl = PECK_FRAMES.index(PECK_CONTACT)
    y = row_of(draw, stab, labels, y, hl=hl)

    y = section_title(draw, y, "C) SPRITES COM ALPHA (chave de fundo branco — sombra do estúdio removida do alfa; ela será sintetizada na cena)")
    ch = checker(CELL_H, CELL_W)
    sprites = []
    for name in ("migalha_rgba", "minipombo_rgba"):
        rgba = cv2.imread(os.path.join(SPR, f"{name}.png"), cv2.IMREAD_UNCHANGED)
        rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
        r = min((CELL_W * 0.9) / rgba.shape[1], (CELL_H * 0.92) / rgba.shape[0])
        rgba = cv2.resize(rgba, (int(rgba.shape[1] * r), int(rgba.shape[0] * r)),
                          interpolation=cv2.INTER_AREA)
        h, w = rgba.shape[:2]
        base = checker(h, w)
        a = rgba[:, :, 3:4].astype(np.float32) / 255
        comp = base.astype(np.float32) * (1 - a) + rgba[:, :, :3].astype(np.float32) * a
        out = np.full((CELL_H, CELL_W, 3), 250, np.uint8)
        y0, x0 = (CELL_H - h) // 2, (CELL_W - w) // 2
        out[y0 : y0 + h, x0 : x0 + w] = comp.astype(np.uint8)
        sprites.append(out)
    y = row_of(draw, sprites, ["migalha_rgba.png", "minipombo_rgba.png"], y)

    y = section_title(draw, y, "D) PLATE LIMPO da janela B (temporal median) — fantasma do pombo = 0,13% da área (marcado); decisão pendente: inpaint por clonagem OU still limpo seu")
    plate = mono(os.path.join(ROOT, "assets", "plates", "w370_442", "plate_clean.png"))
    pconf = mono(os.path.join(ROOT, "assets", "plates", "w370_442", "plate_confianca.png"))
    # bbox do fantasma: pixels inválidos no mapa de confianca (claros)
    inv = (cv2.cvtColor(pconf, cv2.COLOR_RGB2GRAY) > 90).astype(np.uint8)
    cnts, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        x0, y0, bw, bh = cv2.boundingRect(max(cnts, key=cv2.contourArea))
        plate = plate.copy()
        cv2.rectangle(plate, (x0, y0), (x0 + bw, y0 + bh), (255, 60, 60), 2)
    c1 = cell(plate)
    c2 = cell(pconf)
    for k, (c, lab) in enumerate(((c1, "plate_clean.png"), (c2, "plate_confianca.png (escuro = inválido)"))):
        base = Image.fromarray(c)
        d = ImageDraw.Draw(base)
        d.rectangle([0, 0, CELL_W - 1, CELL_H - 1], outline=(230, 230, 235, 255), width=2)
        d.text((6, 4), lab, fill=(20, 20, 25), font=font())
        panel.paste(base, (MARGIN + k * (CELL_W + GAP), y))
    y += CELL_H + GAP
    panel = panel.crop((0, 0, W, y + MARGIN))
    panel.save(os.path.join(OUT, "painel_fase1.png"))
    print("[ok] assets/preview/painel_fase1.png", panel.size)


def section_h() -> int:
    return 26


def make_alpha_check() -> None:
    """Zoom 2x da borda de cada sprite sobre tabuleiro fino — checar penumbra/sombra."""
    strips = []
    for name in ("migalha_rgba", "minipombo_rgba"):
        rgba = cv2.imread(os.path.join(SPR, f"{name}.png"), cv2.IMREAD_UNCHANGED)
        rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
        a = rgba[:, :, 3:4].astype(np.float32) / 255
        base = checker(rgba.shape[0], rgba.shape[1], sq=8).astype(np.float32)
        comp = base * (1 - a) + rgba[:, :, :3].astype(np.float32) * a
        strips.append(comp.astype(np.uint8))
    h = max(s.shape[0] for s in strips)
    W = sum(s.shape[1] for s in strips) + 40
    canvas = np.full((h + 40, W, 3), 252, np.uint8)
    x = 10
    for s, name in zip(strips, ("migalha", "minipombo")):
        y = (h - s.shape[0]) // 2
        canvas[y : y + s.shape[0], x : x + s.shape[1]] = s
        x += s.shape[1] + 20
    Image.fromarray(canvas).save(os.path.join(OUT, "alpha_check.png"))
    print("[ok] assets/preview/alpha_check.png", canvas.shape)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "sprites"), exist_ok=True)
    for f in ("migalha_rgba.png", "minipombo_rgba.png",
              "migalha_alpha.png", "minipombo_alpha.png"):
        shutil.copy2(os.path.join(SPR, f), os.path.join(OUT, "sprites", f))
    make_panel()
    make_alpha_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
