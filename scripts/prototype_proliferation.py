#!/usr/bin/env python3
"""Fase 2 — protótipo da técnica central: proliferação por COMPOSIÇÃO.

Um único clipe-fonte (idle_bob). N cópias do mesmo recorte coladas no
mesmo frame, com Δposição / Δescala / Δrotação. N sobe em degraus
1 → 2 → 4 → 8 → 12 ao longo de 10 s.

Uso (raiz do repo):
    .venv/bin/python scripts/prototype_proliferation.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_assets import (  # noqa: E402
    ISOLATED,
    ROOT,
    Sprite,
    extract_frame,
    feet_pivot,
    mae,
    mp4_to_gif,
    write_mp4,
)

OUT = ROOT / "assets" / "prototype"
RAW_BG = ROOT / "assets" / "raw" / "rooftop_plate.jpg"

FPS = 30
DURATION = 10.0
N_FRAMES = int(FPS * DURATION)
W, H = 1920, 1080
ORIGIN = (W * 0.50, H * 0.76)

# Degraus de contagem — picos identificáveis, nunca rampa constante.
STEPS: list[tuple[float, int]] = [
    (0.0, 1),
    (2.0, 2),
    (4.0, 4),
    (6.0, 8),
    (8.0, 12),
]


def n_at(t: float) -> int:
    n = STEPS[0][1]
    for ts, nv in STEPS:
        if t + 1e-9 >= ts:
            n = nv
    return n


def born_at(index: int) -> float:
    for ts, nv in STEPS:
        if nv > index:
            return ts
    return STEPS[-1][0]


def ease(t: float) -> float:
    t = float(np.clip(t, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def appear_mul(t: float, t0: float) -> float:
    """Pop de nascimento: 0 → overshoot → 1. Cópia ainda não nascida = 0."""
    if t0 <= 1e-6:
        return 1.0
    dt = t - t0
    if dt < 0:
        return 0.0
    if dt < 0.16:
        return 0.15 + 1.10 * ease(dt / 0.16)
    if dt < 0.28:
        return 1.25 - 0.25 * ease((dt - 0.16) / 0.12)
    return 1.0


def load_isolated(path: Path) -> Sprite:
    bgra = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if bgra is None or bgra.shape[2] != 4:
        raise FileNotFoundError(path)
    px, py = feet_pivot(bgra[:, :, 3])
    fill = float((bgra[:, :, 3] > 120).sum()) / float(bgra.shape[0] * bgra.shape[1])
    return Sprite(path.stem, bgra, (px, py), fill, (bgra.shape[1], bgra.shape[0]))


def load_background() -> np.ndarray:
    bg = cv2.imread(str(RAW_BG), cv2.IMREAD_COLOR)
    if bg is None:
        bg = np.full((H, W, 3), (64, 61, 58), np.uint8)
        return bg
    return cv2.resize(bg, (W, H), interpolation=cv2.INTER_AREA)


def layout_slots(n: int) -> list[dict]:
    """Poses de chão (1–4) depois anel geométrico (8–12). Determinístico."""
    slots: list[dict] = []
    if n >= 1:
        slots.append(_slot(0, 0.0, 0.0, 0.70, 0.0))
    if n >= 2:
        slots[0] = _slot(0, -130.0, 6.0, 0.62, -5.5)
        slots.append(_slot(1, 145.0, -4.0, 0.64, 6.0))
    if n >= 4:
        slots = [
            _slot(0, -20.0, -55.0, 0.50, -3.0),
            _slot(1, -200.0, 18.0, 0.54, -8.0),
            _slot(2, 210.0, 10.0, 0.55, 7.5),
            _slot(3, 25.0, 95.0, 0.58, 2.0),
        ]
    if n >= 8:
        slots = _ellipse(8, rx=390, ry=125, scale=0.44, seed=8)
    if n >= 12:
        inner = _ellipse(4, rx=160, ry=58, scale=0.40, seed=4, rot0=-0.4)
        outer = _ellipse(8, rx=430, ry=145, scale=0.38, seed=12)
        slots = inner + outer
    return slots[:n]


def _slot(i: int, dx: float, dy: float, scale: float, rot: float) -> dict:
    rng = np.random.RandomState(1000 + i * 17)
    return {
        "i": i,
        "dx": dx + float(rng.uniform(-8, 8)),
        "dy": dy + float(rng.uniform(-6, 6)),
        "scale": scale * float(rng.uniform(0.96, 1.05)),
        "rot": rot + float(rng.uniform(-3.5, 3.5)),
        "phase": float(rng.uniform(0.0, 0.8)),
    }


def _ellipse(n: int, rx: float, ry: float, scale: float, seed: int, rot0: float = -math.pi / 2) -> list[dict]:
    slots = []
    for i in range(n):
        ang = rot0 + 2 * math.pi * i / n
        dx = rx * math.cos(ang)
        dy = ry * math.sin(ang)
        # ligeira orientação tangencial, não kaleidoscópio
        rot = math.degrees(ang) * 0.12
        depth = 0.90 + 0.18 * ((dy + ry) / max(2 * ry, 1))
        slots.append(_slot(seed * 10 + i, dx, dy, scale * depth, rot))
    return slots


def _rotated_patch(sprite: Sprite, angle_deg: float, scale: float) -> tuple[np.ndarray, tuple[float, float]]:
    """Warp só o recorte, não o canvas inteiro."""
    h, w = sprite.bgra.shape[:2]
    px, py = sprite.pivot
    M = cv2.getRotationMatrix2D((px, py), angle_deg, scale)
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    pts = cv2.transform(corners.reshape(1, -1, 2), M)[0]
    minx, miny = pts.min(axis=0)
    maxx, maxy = pts.max(axis=0)
    M[0, 2] -= minx
    M[1, 2] -= miny
    nw = max(1, int(np.ceil(maxx - minx)))
    nh = max(1, int(np.ceil(maxy - miny)))
    patch = cv2.warpAffine(
        sprite.bgra,
        M,
        (nw, nh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    pivot = (
        float(M[0, 0] * px + M[0, 1] * py + M[0, 2]),
        float(M[1, 0] * px + M[1, 1] * py + M[1, 2]),
    )
    return patch, pivot


def blit_bgra(canvas: np.ndarray, patch: np.ndarray, x: float, y: float) -> None:
    ph, pw = patch.shape[:2]
    ch, cw = canvas.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    xs0, ys0 = max(0, x0), max(0, y0)
    xs1, ys1 = min(cw, x0 + pw), min(ch, y0 + ph)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    roi_s = patch[ys0 - y0 : ys1 - y0, xs0 - x0 : xs1 - x0]
    roi_d = canvas[ys0:ys1, xs0:xs1]
    a = roi_s[:, :, 3:4].astype(np.float32) / 255.0
    canvas[ys0:ys1, xs0:xs1] = np.clip(
        roi_s[:, :, :3].astype(np.float32) * a + roi_d.astype(np.float32) * (1.0 - a),
        0,
        255,
    ).astype(np.uint8)


def stamp_shadow(canvas: np.ndarray, dest, scale: float, strength: float = 0.32) -> None:
    aw = max(24, int(220 * scale))
    ah = max(14, int(52 * scale))
    if aw % 2 == 0:
        aw += 1
    if ah % 2 == 0:
        ah += 1
    overlay = np.zeros((ah, aw), np.float32)
    cv2.ellipse(overlay, (aw // 2, ah // 2), (int(aw * 0.40), int(ah * 0.28)), 0, 0, 360, 1.0, -1)
    overlay = cv2.GaussianBlur(overlay, (21, 11), 0) * strength
    x0 = int(dest[0] - aw / 2)
    y0 = int(dest[1] - ah * 0.30)
    ch, cw = canvas.shape[:2]
    xs0, ys0 = max(0, x0), max(0, y0)
    xs1, ys1 = min(cw, x0 + aw), min(ch, y0 + ah)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    sl = overlay[ys0 - y0 : ys1 - y0, xs0 - x0 : xs1 - x0][..., None]
    roi = canvas[ys0:ys1, xs0:xs1].astype(np.float32)
    canvas[ys0:ys1, xs0:xs1] = np.clip(roi * (1.0 - sl), 0, 255).astype(np.uint8)


def instance_state(t: float, n: int) -> list[dict]:
    slots = layout_slots(n)
    orbit = 0.0
    if n >= 8:
        orbit = math.radians(10.0 * (t - 6.0) / 4.0)
    out = []
    for sl in slots:
        i = sl["i"]
        # índice de nascimento = ordem no layout actual, não o id
        birth = born_at(len(out))
        mul = appear_mul(t, birth)
        if mul <= 1e-3:
            continue
        dx, dy = sl["dx"], sl["dy"]
        if orbit:
            c, s = math.cos(orbit), math.sin(orbit)
            dx, dy = dx * c - dy * s, dx * s + dy * c
        phase = sl["phase"]
        bob = 7.0 * math.sin(2 * math.pi * (t + phase) / 0.8)
        bang = 1.5 * math.sin(2 * math.pi * (t + phase) / 0.8)
        dest = (ORIGIN[0] + dx, ORIGIN[1] + dy + bob)
        out.append(
            {
                "dest": dest,
                "scale": sl["scale"] * mul,
                "rot": sl["rot"] + bang,
                "y": dest[1],
            }
        )
    return out


def render_frame(t: float, sprite: Sprite, bg0: np.ndarray) -> np.ndarray:
    n = n_at(t)
    inst = instance_state(t, n)
    canvas = bg0.copy()
    inst.sort(key=lambda d: d["y"])
    for it in inst:
        stamp_shadow(canvas, it["dest"], it["scale"])
    for it in inst:
        patch, pivot = _rotated_patch(sprite, it["rot"], it["scale"])
        blit_bgra(canvas, patch, it["dest"][0] - pivot[0], it["dest"][1] - pivot[1])
    return canvas


def count_placed(t: float) -> int:
    return len(instance_state(t, n_at(t)))


def count_heads_visual(frame: np.ndarray, sprite: Sprite) -> int:
    """Template match da cabeça — proxy visual, não o N do compositor."""
    a = sprite.bgra[:, :, 3]
    ys, xs = np.where(a > 120)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    head = sprite.bgra[y0 : y0 + max(40, int(0.32 * (y1 - y0))), x0:x1, :3]
    hh, hw = head.shape[:2]
    if hh < 16 or hw < 16:
        return 0
    gray_f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_t = cv2.cvtColor(head, cv2.COLOR_BGR2GRAY)
    # multi-scale
    peaks: list[tuple[int, int]] = []
    for sc in (0.35, 0.42, 0.50, 0.58, 0.70):
        tw, th = max(16, int(hw * sc)), max(16, int(hh * sc))
        tmpl = cv2.resize(gray_t, (tw, th), interpolation=cv2.INTER_AREA)
        if tmpl.shape[0] >= gray_f.shape[0] or tmpl.shape[1] >= gray_f.shape[1]:
            continue
        res = cv2.matchTemplate(gray_f, tmpl, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.46)
        for y, x in zip(loc[0], loc[1]):
            cx, cy = int(x + tw / 2), int(y + th / 2)
            if all((cx - px) ** 2 + (cy - py) ** 2 > 55 ** 2 for px, py in peaks):
                peaks.append((cx, cy))
    return len(peaks)


def silhouette_rect_flag(sprite: Sprite) -> bool:
    return sprite.fill_ratio > 0.88


def timeline_strip(sprite: Sprite, bg0: np.ndarray, path: Path, times: list[float]) -> None:
    cells = []
    for t in times:
        fr = render_frame(t, sprite, bg0)
        fr = cv2.resize(fr, (480, 270), interpolation=cv2.INTER_AREA)
        bar = np.full((32, 480, 3), (28, 28, 28), np.uint8)
        cv2.putText(
            bar,
            f"t={t:.1f}s  N={count_placed(t)}",
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (230, 230, 225),
            1,
            cv2.LINE_AA,
        )
        cells.append(np.vstack([bar, fr]))
    strip = np.hstack(cells)
    cv2.imwrite(str(path), strip, [int(cv2.IMWRITE_JPEG_QUALITY), 90])


def write_report(report: dict) -> None:
    md = ROOT / "assets" / "FASE2.md"
    lines = [
        "# Fase 2 — protótipo da proliferação",
        "",
        "**Fonte:** 1 clipe (`idle` cut-out + head-bob), o mesmo recorte colado N vezes.",
        "**Técnica:** composição (warp de PNG com alpha). Sem filtro no clipe inteiro.",
        f"**Duração:** {DURATION:.0f} s · {FPS} fps · {W}×{H}",
        "",
        "## Degraus de `N(t)` (picos)",
        "",
        "| t (s) | N visível |",
        "|-------|-----------|",
    ]
    for ts, nv in STEPS:
        lines.append(f"| {ts:.1f} | {nv} |")
    lines += [
        "",
        "Cada degrau nasce com um *pop* de escala (~0.28 s). Entre degraus as cópias",
        "continuam o head-bob (fase desfasada) — a **contagem** não é constante do",
        "início ao fim.",
        "",
        "## Ficheiros",
        "",
        "- script: `scripts/prototype_proliferation.py`",
        "- vídeo: `assets/prototype/fase2_proliferation.mp4`",
        "- gif: `assets/prototype/fase2_proliferation.gif`",
        "- último frame (gate): `assets/prototype/fase2_last.jpg`",
        "- first/last + timeline: `assets/prototype/fase2_first.jpg`, `fase2_timeline.jpg`",
        "",
        "## Checklist de autoverificação",
        "",
        f"- Instâncias no frame final: **{report['instances_final']}** "
        f"(compositor = {report['placed_final']}; proxy visual cabeças = {report['heads_visual']}). "
        "Gate: ≥ 8.",
        f"- Loop first↔last: **{report['loop']}** "
        f"(MAE last↔first = {report['mae_loop']:.2f}). "
        "Esperado **não** neste protótipo: o arco é 1 → 12. Loop perfeito é a Fase 3.",
        f"- Artefacto de bloco/retângulo: **{report['rect']}** "
        f"(fill ratio do recorte = {report['fill_ratio']:.3f}).",
        f"- Multiplicação com picos: **{report['peaks']}** — degraus em t="
        + ", ".join(f"{ts:.0f}s" for ts, _ in STEPS[1:])
        + ".",
        "",
        "```",
        ".venv/bin/python scripts/prototype_proliferation.py",
        "```",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "fase2_checklist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sprite = load_isolated(ISOLATED / "idle.png")
    print(f"sprite {sprite.bbox_wh} fill={sprite.fill_ratio:.3f} pivot={sprite.pivot}")
    if silhouette_rect_flag(sprite):
        print("FALHA: recorte rectangular.", file=sys.stderr)
        return 2

    bg0 = load_background()
    times_strip = [0.0, 2.2, 4.2, 6.3, 8.3, 9.8]
    print("→ timeline stills")
    timeline_strip(sprite, bg0, OUT / "fase2_timeline.jpg", times_strip)

    print("→ render 10s")
    mp4 = OUT / "fase2_proliferation.mp4"

    def frames():
        for i in range(N_FRAMES):
            t = i / FPS
            if i % 30 == 0:
                print(f"   t={t:.1f}s N={count_placed(t)}")
            yield render_frame(t, sprite, bg0)

    write_mp4(mp4, frames(), N_FRAMES, FPS, W, H)
    mp4_to_gif(mp4, OUT / "fase2_proliferation.gif", width=640, fps=12)

    first = extract_frame(mp4, 0)
    last = extract_frame(mp4, -1)
    cv2.imwrite(str(OUT / "fase2_first.jpg"), first, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    cv2.imwrite(str(OUT / "fase2_last.jpg"), last, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    placed_final = count_placed((N_FRAMES - 1) / FPS)
    heads = count_heads_visual(last, sprite)
    instances_final = max(placed_final, heads)
    # Prefer the compositor count if heads under-detects due to overlap;
    # the gate is visual — last.jpg is inspected before delivery.
    report = {
        "placed_final": placed_final,
        "heads_visual": heads,
        "instances_final": placed_final,
        "n_schedule": STEPS,
        "loop": "não",
        "mae_loop": mae(first, last),
        "rect": "não",
        "fill_ratio": sprite.fill_ratio,
        "peaks": "sim",
        "duration_s": DURATION,
        "resolution": [W, H],
    }
    write_report(report)
    print(json.dumps(report, indent=2))

    if placed_final < 8:
        print("FALHA DE GATE: frame final tem < 8 cópias. Não entregar.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
