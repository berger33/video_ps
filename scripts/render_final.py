#!/usr/bin/env python3
"""Fase 5 — polimento e exportação final (1920×1080, 30 fps, 75 s, com trilha).

O que muda em relação ao corte bruto da Fase 3 (tudo *dentro* do contrato:
a multiplicação continua a ser composição de recortes, nada de filtro sobre
o clipe inteiro):

1. **Profundidade por planos.** Os slots passam a ter três planos — fundo
   (junto ao horizonte, pequenos, com névoa atmosférica), meio (anel) e
   frente (grandes, junto à câmara). A ordem de revelação acrescenta os
   planos de trás primeiro, portanto N=16 lê-se como "multidão com fundo",
   não como "mais um anel".
2. **Onda de nascimento.** Cada degrau de N(t) não aparece de uma vez:
   as cópias nascem em onda (0.03 s entre elas, do centro para fora) com
   pop de escala + fade de luminância. O pico é um acontecimento, não um
   corte de montagem.
3. **Micro-movimento com período divisor de 75 s** (12.5 s / 15 s / 18.75 s):
   deriva lenta, giro lento e *head-bob* a 0.75 s (100 ciclos) — o quadro
   final coincide com o inicial por construção, não por correção.
4. **Grounding**: mapa de sombra única acumulada (massa) + ponto de contacto
   por ave + névoa atmosférica por plano. Sem caixas, sem halos.
5. **Post leve** (`profundidade de campo` macro no prato, bloom a partir de
   altas luzes, grão fino de período 15 frames, jitter global de ±1 px e
   curva de cor S). O *fade* global é ~0 em t=0 e t=75 (gate por N): o que
   se vê é a colagem, não um "look" aplicado ao clipe.
6. **Timing**: o colapso passa a cair na grelha musical (compassos 32, 34,
   35.5, 37, 38.5) definida em `score_grid.py` — a mesma que a trilha usa.

Uso (raiz do repo):
    .venv/bin/python scripts/render_final.py              # 75 s completos
    .venv/bin/python scripts/render_final.py --still 52.5 --out /tmp/a.jpg
    .venv/bin/python scripts/render_final.py --verify     # só frames de QA
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_assets import ISOLATED, ROOT, mae, write_mp4  # noqa: E402
from prototype_proliferation import _rotated_patch, blit_bgra, load_isolated  # noqa: E402
from score_grid import (  # noqa: E402
    BAR,
    BEAT,
    DURATION,
    FPS,
    OUT_AUDIO,
    OUT_FINAL,
    PEAK_N,
    STEPS,
    SWITCH_TIMES,
    n_at,
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080
N_FRAMES = int(round(DURATION * FPS))
PLATE = ROOT / "assets" / "raw" / "rooftop_plate.jpg"
SCORE_WAV = OUT_AUDIO / "coo_score.wav"

BOB_PERIOD = 0.75          # 75 / 0.75 = 100 ciclos
DRIFT_PERIOD = 12.5        # 75 / 12.5 = 6
SPIN_PERIOD = 18.75        # 75 / 18.75 = 4
SHIMMER_PERIOD = 0.5       # 75 / 0.5 = 150
GRAIN_PERIOD = 15          # 2250 / 15 = 150 frames distintos
JITTER_PERIOD = 6

SPRITE_NAMES = ["idle", "walk_a", "walk_b", "peck", "coo", "fluff", "head_turn"]
HAZE_BGR = np.array([118.0, 116.0, 112.0], np.float32)   # névoa do horizonte


def ease(t: float) -> float:
    t = float(np.clip(t, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def ramp(n: float) -> float:
    """0 no sujeito solitário (N=1) → 1 no pico (N=32)."""
    return float(np.clip(math.log2(max(n, 1)) / math.log2(PEAK_N), 0.0, 1.0))


# ============================================================== sprites =====
@dataclass
class Sprite:
    name: str
    bgra: np.ndarray
    pivot: tuple[float, float]
    fill_ratio: float
    bbox_wh: tuple[int, int]


def load_sprite(name: str) -> Sprite:
    bgra = cv2.imread(str(ISOLATED / f"{name}.png"), cv2.IMREAD_UNCHANGED)
    if bgra is None:
        raise FileNotFoundError(name)
    b, g, r, a = cv2.split(bgra)
    bgr = cv2.merge([b, g, r])
    # claridade: leve unsharp para o recorte aguentar a escala pequena
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.1)
    bgr = cv2.addWeighted(bgr, 1.45, blur, -0.45, 0)
    # pena de 0.6 px na máscara: mata o serrilhado do recorte, sem halo
    a = cv2.GaussianBlur(a, (3, 3), 0.6)
    bgra = cv2.merge([bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2], a])
    ys, xs = np.where(a > 120)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    pivot = (0.5 * (x0 + x1), float(y1))
    fill = float((a > 120).sum()) / float(a.shape[0] * a.shape[1])
    return Sprite(name, bgra, pivot, fill, (bgra.shape[1], bgra.shape[0]))


# ============================================================== fundo =======
class BackgroundBank:
    """Prato original + variantes desfocadas (profundidade de campo macro)."""

    def __init__(self, path: Path = PLATE) -> None:
        plate = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if plate is None:
            raise FileNotFoundError(path)
        self.levels = [cv2.resize(plate, (W, H), interpolation=cv2.INTER_AREA)]
        for sigma in (1.6, 2.6, 3.6, 4.8, 6.0):
            self.levels.append(cv2.GaussianBlur(self.levels[0], (0, 0), sigma))
        # vinheta muito leve, parte do "prato", não do "efeito"
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vignette = (1.0 - 0.10 * np.clip(r - 0.55, 0, None) ** 1.5)[..., None]
        self.levels = [
            np.clip(lv.astype(np.float32) * self.vignette, 0, 255).astype(np.uint8) for lv in self.levels
        ]

    def at(self, blur_strength: float) -> np.ndarray:
        k = int(np.clip(round(blur_strength * (len(self.levels) - 1)), 0, len(self.levels) - 1))
        return self.levels[k]


# ============================================================== layout ======
@dataclass
class Slot:
    i: int
    dx: float = 0.0          # px, relativo a ORIGIN
    dy: float = 0.0
    scale: float = 0.42
    rot: float = 0.0
    phase: float = 0.0       # fase do head-bob
    tier: str = "main"
    depth: float = 0.5       # 0 = horizonte, 1 = junto à câmara
    drift_phase: float = 0.0
    spin_phase: float = 0.0
    flip: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)


def _slot(i: int, dx, dy, scale, rot, tier, depth, seed) -> Slot:
    rng = np.random.RandomState(seed)
    return Slot(
        i=i,
        dx=dx + float(rng.uniform(-6, 6)),
        dy=dy + float(rng.uniform(-4, 4)),
        scale=scale * float(rng.uniform(0.96, 1.04)),
        rot=rot + float(rng.uniform(-2.5, 2.5)),
        phase=float(rng.uniform(0.0, BOB_PERIOD)),
        tier=tier,
        depth=depth,
        drift_phase=float(rng.uniform(0.0, DRIFT_PERIOD)),
        spin_phase=float(rng.uniform(0.0, SPIN_PERIOD)),
        flip=(tier == "far" and (i % 2 == 0)),
    )


def small_layout(n: int) -> list[Slot]:
    """N = 1, 2, 4 — o pombo sozinho e a primeira duplicação (chão, legível)."""
    if n <= 1:
        s = _slot(0, 0.0, 0.0, 0.70, 0.0, "hero", 0.62, 3000)
        # sem jitter: o herói do primeiro frame é bit-a-bit o do último
        s.dx = s.dy = 0.0
        s.scale, s.rot = 0.70, 0.0
        s.phase = s.drift_phase = s.spin_phase = 0.0
        return [s]
    if n == 2:
        a = _slot(0, -155.0, 10.0, 0.62, -5.0, "hero", 0.60, 3001)
        b = _slot(1, 165.0, -6.0, 0.63, 5.5, "hero", 0.60, 3002)
        a.phase = 0.0
        return [a, b]
    return [  # n == 4
        _slot(0, -22.0, -58.0, 0.50, -3.0, "main", 0.52, 3003),
        _slot(1, -215.0, 22.0, 0.54, -7.5, "main", 0.55, 3004),
        _slot(2, 225.0, 14.0, 0.55, 7.0, "main", 0.56, 3005),
        _slot(3, 30.0, 112.0, 0.58, 2.0, "main", 0.62, 3006),
    ]


# O prato é um plano *raso* e próximo: o chão visível vai de ~y=520 (junto à
# aresta) a y=1080. Toda a ave fica dentro dessa faixa, com escala coerente
# com a profundidade — é isto que faz a colagem "pousar" em vez de flutuar.
ORIGIN = (W * 0.50, H * 0.755)          # y=815, o pé do herói (frame 0)
ROOF_TOP = 520.0                        # linha da aresta do telhado
FLOOR_BOTTOM = 1075.0

TIER_SPEC = {
    # tier: (count, rx, ry, y_abs, scale, depth, angle_offset)
    "main": (8, 430.0, 96.0, 838.0, 0.555, 0.55, 0.0),
    "far": (8, 900.0, 10.0, 596.0, 0.150, 0.06, 0.0),
    "mid": (8, 615.0, 40.0, 676.0, 0.395, 0.34, math.pi / 8),
    "near": (8, 855.0, 34.0, 1032.0, 0.760, 1.00, math.pi / 8),
}


def ring(tier: str, seed: int) -> list[Slot]:
    count, rx, ry, y_abs, scale, depth, ang_off = TIER_SPEC[tier]
    rng = np.random.RandomState(seed)
    out: list[Slot] = []
    for k in range(count):
        ang = -math.pi / 2 + ang_off + 2 * math.pi * k / count
        # elipse jitterizada: sem anel de compasso, sem duplicar posições
        rr = 1.0 + float(rng.uniform(-0.12, 0.12))
        dx = rx * rr * math.cos(ang)
        y = y_abs + ry * math.sin(ang) + float(rng.uniform(-9, 9))
        y = float(np.clip(y, ROOF_TOP + 8.0, FLOOR_BOTTOM))
        out.append(_slot(k, dx, y - ORIGIN[1], scale, math.degrees(ang) * 0.08, tier, depth, seed + k * 13))
    return out


def pack(slots: list[Slot], iterations: int = 520,
         x_range: tuple[float, float] = (-900.0, 900.0)) -> None:
    """Distanciamento físico determinístico.

    Resolve os três defeitos que a revisão da composição apanhou:
    cópias empilhadas no mesmo pixel, fileiras que se duplicam em coluna e
    a frente a tapar totalmente o fundo. Repele pares abaixo do raio de
    exclusão e puxa cada cópia para o `y` do seu plano (coerência de
    profundidade: nada é empurrado para "voar" acima do telhado).
    """
    pos = np.array([[s.dx, s.dy] for s in slots], np.float64)
    tier = [s.tier for s in slots]
    scale = np.array([s.scale for s in slots], np.float64)
    radius = 0.46 * 430.0 * scale + 26.0
    y_home = np.array([TIER_SPEC[t][3] - ORIGIN[1] for t in tier], np.float64)
    y_lo = ROOF_TOP + 6.0 - ORIGIN[1]
    y_hi = FLOOR_BOTTOM - ORIGIN[1]
    for _ in range(iterations):
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.hypot(d[:, :, 0], d[:, :, 1])
        np.fill_diagonal(dist, 1e9)
        need = 0.5 * (radius[:, None] + radius[None, :])
        overlap = np.clip(need - dist, 0.0, None)
        push = (overlap / np.maximum(dist, 1e-6))[..., None] * d
        pos = pos + 0.34 * push.sum(axis=1)
        pos[:, 1] += 0.18 * (y_home - pos[:, 1])
        pos[:, 0] = np.clip(pos[:, 0], x_range[0], x_range[1])
        pos[:, 1] = np.clip(pos[:, 1], y_lo, y_hi)
    for s, (dx, dy) in zip(slots, pos):
        s.dx, s.dy = float(dx), float(dy)


def build_slots() -> dict[int, list[Slot]]:
    """Slots por N, na ordem de revelação (índice estável entre degraus).

    A ordem é a do arranjo dramático: anel principal → plano distante →
    plano intermédio → primeiro plano. As cópias reveladas primeiro ficam
    *atrás* das seguintes, para que o quadro continue legível a cada degrau
    e não seja um aglomerado.
    """
    main = ring("main", 4000)
    far = ring("far", 5000)
    mid = ring("mid", 6000)
    near = ring("near", 7000)
    for s in far:
        s.rot *= 0.5
        s.flip = True
    all_slots = main + far + mid + near
    pack(all_slots)
    # escala coerente com a profundidade: mais perto da câmara (y maior) = maior
    for s in all_slots:
        y = s.dy + ORIGIN[1]
        u = (y - ROOF_TOP) / (FLOOR_BOTTOM - ROOF_TOP)
        s.scale *= 1.0 + 0.16 * (u - 0.45)
    groups = [main, far, mid, near]
    for g in groups:
        g.sort(key=lambda s: (s.dx * s.dx + (s.dy * 0.7) ** 2))

    layouts: dict[int, list[Slot]] = {1: small_layout(1), 2: small_layout(2), 4: small_layout(4)}
    ring8 = [Slot(**{**s.__dict__, "i": i}) for i, s in enumerate(main)]
    ring8[0].phase = 0.0
    layouts[8] = ring8
    layouts[16] = ring8 + [Slot(**{**s.__dict__, "i": 8 + j}) for j, s in enumerate(far)]
    layouts[24] = layouts[16] + [Slot(**{**s.__dict__, "i": 16 + j}) for j, s in enumerate(mid)]
    layouts[32] = layouts[24] + [Slot(**{**s.__dict__, "i": 24 + j}) for j, s in enumerate(near)]
    return layouts


LAYOUTS = build_slots()


def step_context(t: float) -> tuple[int, int, float]:
    prev_n, curr_n, t_sw = STEPS[0][1], STEPS[0][1], STEPS[0][0]
    for ts, nv in STEPS:
        if t + 1e-9 >= ts:
            prev_n = curr_n
            curr_n = nv
            t_sw = ts
    return prev_n, curr_n, t_sw


def born_at(index: int) -> float:
    for ts, nv in STEPS:
        if nv > index:
            return ts
    return STEPS[-1][0]


def wave_offset(index: int, t_sw: float) -> float:
    """Atraso na onda de nascimento: centro → fora, dentro do degrau."""
    n_prev = 0
    for ts, nv in STEPS:
        if abs(ts - t_sw) < 1e-9:
            n_prev = STEPS[max(0, STEPS.index((ts, nv)) - 1)][1]
    rank = index - n_prev
    return 0.030 * max(rank, 0)


def death_at(index: int) -> float | None:
    seen = False
    for ts, nv in STEPS:
        if nv > index:
            seen = True
        elif seen and nv <= index:
            return ts
    return None


def appear_mul(t: float, t0: float) -> float:
    if t0 <= 1e-6:
        return 1.0
    dt = t - t0
    if dt < 0:
        return 0.0
    if dt < 0.18:
        return 0.08 + 1.16 * ease(dt / 0.18)
    if dt < 0.30:
        return 1.24 - 0.24 * ease((dt - 0.18) / 0.12)
    return 1.0


def die_mul(t: float, t_death: float | None) -> float:
    if t_death is None or t < t_death:
        return 1.0
    dt = t - t_death
    if dt >= 0.30:
        return 0.0
    return 1.0 - ease(dt / 0.30)


def visibility(t: float, index: int) -> float:
    t_sw = born_at(index)
    return appear_mul(t, t_sw + (wave_offset(index, t_sw) if index > 0 else 0.0)) * die_mul(t, death_at(index))


def rest_blend(t: float) -> float:
    tail = 1.0
    if t >= DURATION - tail:
        return ease((t - (DURATION - tail)) / tail)
    return 0.0


def choose_sprite(i: int, t: float, sprites: dict[str, Sprite], n: int) -> Sprite:
    """Poses por bloco, como no corte bruto — mas o fundo mantém-se em idle."""
    if n <= 4 or t >= 60.0:
        return sprites["idle"]
    t_slot = t + i * 0.137
    if t < 30.0:
        u = t_slot % 1.0
        if 0.20 <= u < 0.42:
            return sprites["walk_a"]
        if 0.66 <= u < 0.88:
            return sprites["walk_b"]
        return sprites["idle"]
    if t < 45.0:
        if (t_slot % 2.0) < 0.22 and i % 2 == 0:
            return sprites["peck"]
        if (t_slot % 4.0) < 0.38 and i % 5 == 2:
            return sprites["head_turn"]
        return sprites["idle"]
    if i < 8 and (t_slot % 3.5) < 0.30:
        return sprites["coo"] if i % 3 == 0 else sprites["fluff"]
    if i >= 8 and (t_slot % 5.0) < 0.25:
        return sprites["head_turn"] if i % 4 == 0 else sprites["idle"]
    return sprites["idle"]


# ========================================================== instâncias ======
_patch_cache: dict[tuple, tuple] = {}


def rotated_cached(sprite: Sprite, angle: float, scale: float, flip: bool):
    key = (sprite.name, "f" if flip else "n", round(angle * 3.0) / 3.0, round(scale, 3))
    hit = _patch_cache.get(key)
    if hit is None:
        sp = sprite
        if flip:
            bgra = sp.bgra[:, ::-1]
            pivot = (bgra.shape[1] - 1 - sp.pivot[0], sp.pivot[1])
            sp = Sprite(sp.name, bgra, pivot, sp.fill_ratio, sp.bbox_wh)
        hit = _rotated_patch(sp, angle, scale)
        if len(_patch_cache) > 3000:
            _patch_cache.clear()
        _patch_cache[key] = hit
    return hit


def instance_state(t: float, sprites: dict[str, Sprite]) -> list[dict]:
    prev_n, curr_n, t_sw = step_context(t)
    u = ease(float(np.clip((t - t_sw) / 0.5, 0.0, 1.0))) if t_sw > 0 else 1.0
    la, lb = LAYOUTS[prev_n], LAYOUTS[curr_n]
    rb = rest_blend(t)
    # sucção do colapso: as cópias contraem para o centro no momento do degrau
    suck = 0.0
    for t_d in SWITCH_TIMES:
        if t_d > 45.0 and n_at(t_d - 1e-6) > n_at(t_d + 1e-6):
            dt = t - t_d
            if 0.0 <= dt < 0.55:
                suck = max(suck, math.sin(math.pi * dt / 0.55) * 0.08)
    out: list[dict] = []
    for i in range(PEAK_N):
        mul = visibility(t, i)
        if mul <= 1e-3:
            continue
        if i < len(la) and i < len(lb):
            sa, sb = la[i], lb[i]
            sl = sa if sa.tier == sb.tier and abs(sa.dx - sb.dx) < 1e-6 else sa
            k = u
            dx = sl.dx * (1 - k) + sb.dx * k
            dy = sl.dy * (1 - k) + sb.dy * k
            scale = sl.scale * (1 - k) + sb.scale * k
            rot = sl.rot * (1 - k) + sb.rot * k
            tier, depth, flip = sb.tier, sb.depth, sb.flip
            phase, drift_phase, spin_phase = sb.phase, sb.drift_phase, sb.spin_phase
        elif i < len(lb):
            s = lb[i]
            dx, dy, scale, rot = s.dx, s.dy, s.scale, s.rot
            tier, depth, flip = s.tier, s.depth, s.flip
            phase, drift_phase, spin_phase = s.phase, s.drift_phase, s.spin_phase
        else:
            continue

        # ---- micro-movimento (períodos divisores de 75 s) ---------------
        drift_x = 9.0 * math.sin(2 * math.pi * (t + drift_phase) / DRIFT_PERIOD)
        drift_y = 3.4 * math.sin(2 * math.pi * (t + drift_phase * 1.7) / (DRIFT_PERIOD * 1.5))
        spin = 5.5 * math.sin(2 * math.pi * (t + spin_phase) / SPIN_PERIOD)
        bob = 7.0 * math.sin(2 * math.pi * (t + phase) / BOB_PERIOD)
        rock = 1.5 * math.sin(2 * math.pi * (t + phase) / BOB_PERIOD)

        dx, dy = dx + drift_x - dx * suck, dy + drift_y - dy * suck
        rot = rot + spin + rock
        scale = scale * mul
        dest = (ORIGIN[0] + dx, ORIGIN[1] + dy + bob)

        if rb > 0 and i == 0:
            u2 = rb
            dest = (dest[0] * (1 - u2) + ORIGIN[0] * u2, dest[1] * (1 - u2) + ORIGIN[1] * u2)
            rot *= 1 - u2
            scale = scale * (1 - u2) + 0.70 * u2

        out.append(
            {
                "i": i,
                "dest": dest,
                "scale": scale,
                "rot": rot,
                "depth": depth,
                "flip": flip,
                "tier": tier,
                "vis": mul,
                "sprite": sprites["idle"] if rb > 0.5 else choose_sprite(i, t, sprites, curr_n),
            }
        )
    out.sort(key=lambda d: d["dest"][1])
    return out


# ========================================================== composição ======
def shadow_map(inst: list[dict], strength: float) -> np.ndarray:
    """Massa de sombra acumulada (fundo escurecido antes das colagens)."""
    acc = np.zeros((H, W), np.float32)
    for it in inst:
        x, y = it["dest"]
        s = it["scale"]
        aw = max(18, int(250 * s))
        ah = max(10, int(60 * s))
        cy = y - 0.06 * ah
        layer = np.zeros((ah + 2, aw + 2), np.float32)
        cv2.ellipse(layer, ((aw + 2) // 2, (ah + 2) // 2), (int(aw * 0.42), int(ah * 0.30)), 0, 0, 360, 1.0, -1)
        x0, y0 = int(x - aw / 2), int(cy - ah / 2)
        xs0, ys0 = max(0, x0), max(0, y0)
        xs1, ys1 = min(W, x0 + aw + 2), min(H, y0 + ah + 2)
        if xs1 <= xs0 or ys1 <= ys0:
            continue
        sl = layer[ys0 - y0 : ys1 - y0, xs0 - x0 : xs1 - x0]
        acc[ys0:ys1, xs0:xs1] = np.maximum(acc[ys0:ys1, xs0:xs1], sl * (0.20 + 0.42 * it["depth"]) * strength)
        # ponto de contacto (pés) — mais escuro, mais pequeno
        cw = max(10, int(46 * s))
        chh = max(6, int(16 * s))
        cl = np.zeros((chh + 2, cw + 2), np.float32)
        cv2.ellipse(cl, ((cw + 2) // 2, (chh + 2) // 2), (int(cw * 0.45), int(chh * 0.42)), 0, 0, 360, 1.0, -1)
        cx0, cy0 = int(x - cw / 2), int(y - chh * 0.30)
        xs0b, ys0b = max(0, cx0), max(0, cy0)
        xs1b, ys1b = min(W, cx0 + cw + 2), min(H, cy0 + chh + 2)
        if xs1b <= xs0b or ys1b <= ys0b:
            continue
        acc[ys0b:ys1b, xs0b:xs1b] = np.minimum(
            1.0, acc[ys0b:ys1b, xs0b:xs1b] + cl[ys0b - cy0 : ys1b - cy0, xs0b - cx0 : xs1b - cx0] * 0.42 * strength
        )
    k = cv2.GaussianBlur(acc, (0, 0), 8.0)
    return np.clip(k, 0.0, 0.72)


def apply_lum(patch: np.ndarray, lum: float, haze: float) -> np.ndarray:
    """LUT por instância: jitter de luminância + névoa atmosférica do plano."""
    if abs(lum - 1.0) < 0.004 and haze < 0.004:
        return patch
    table = np.arange(256, dtype=np.float32)
    table = table * lum
    table = table * (1.0 - haze) + HAZE_BGR.mean() * haze
    lut = np.clip(table, 0, 255).astype(np.uint8)
    lut3 = np.repeat(lut[:, None], 3, axis=1)[None, :, :]
    out = patch.copy()
    out[:, :, :3] = cv2.LUT(patch[:, :, :3], lut3)
    return out


def compose_frame(t: float, sprites: dict[str, Sprite], bg: BackgroundBank) -> np.ndarray:
    """Colagem pura (sem post): máscaras, sombras, planos. É isto que a colagem
    é — o post só acrescenta o acabamento."""
    inst = instance_state(t, sprites)
    n = len(inst)
    r = ramp(n)

    canvas = bg.at(0.15 + 0.85 * r).astype(np.float32)
    smap = shadow_map(inst, 0.75 + 0.45 * r)
    canvas *= (1.0 - smap)[..., None]
    canvas = canvas.astype(np.uint8)

    for it in inst:
        lum = 1.0 + (0.030 * math.sin(2 * math.pi * (t + it["i"] * 0.53) / SHIMMER_PERIOD)) * r
        patch, pivot = rotated_cached(it["sprite"], it["rot"], it["scale"], it["flip"])
        patch = apply_lum(patch, lum, haze=0.16 * (1.0 - it["depth"]) * r)
        blit_bgra(canvas, patch, it["dest"][0] - pivot[0], it["dest"][1] - pivot[1])
    return canvas


def render_frame(t: float, sprites: dict[str, Sprite], bg: BackgroundBank) -> np.ndarray:
    return post(compose_frame(t, sprites, bg), t, ramp(len(instance_state(t, sprites))))


# =============================================================== post =======
_GRAIN_CACHE: dict[int, np.ndarray] = {}


def grain_field(k: int) -> np.ndarray:
    hit = _GRAIN_CACHE.get(k)
    if hit is None:
        rng = np.random.default_rng(7000 + k)
        hit = (rng.standard_normal((H, W, 1)) * 1.9).astype(np.float32)
        if len(_GRAIN_CACHE) > 64:
            _GRAIN_CACHE.clear()
        _GRAIN_CACHE[k] = hit
    return hit


def shift_int(img: np.ndarray, dx: int, dy: int) -> np.ndarray:
    if dx == 0 and dy == 0:
        return img
    out = np.empty_like(img)
    ys_src = np.clip(np.arange(H) - dy, 0, H - 1)
    xs_src = np.clip(np.arange(W) - dx, 0, W - 1)
    return img[ys_src][:, xs_src]


S_CURVE = np.clip(
    (np.arange(256) / 255.0 + 0.075 * np.sin(2 * np.pi * (np.arange(256) / 255.0 - 0.5))) * 255.0, 0, 255
).astype(np.uint8)


def post(canvas: np.ndarray, t: float, r: float) -> np.ndarray:
    frame = int(round(t * FPS))
    # 1) jitter global de ±1 px — periódico em 3 s (75/3 = 25 ciclos exactos),
    #    logo o primeiro e o último frame recebem exactamente o mesmo offset
    jx = int(round(math.sin(2 * math.pi * t / 3.0)))
    jy = int(round(math.cos(2 * math.pi * t / 3.0)))
    out = shift_int(canvas, jx, jy) if (jx or jy) else canvas
    # 2) curva de cor (S muito leve) + micro-saturação
    out = cv2.LUT(out, S_CURVE)
    # 3) bloom das altas luzes — gate por N, logo ~0 no primeiro e último frame
    strength = 0.10 * r * (1.0 - rest_blend(t))
    if strength > 0.012:
        lum = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        mask = np.clip((lum.astype(np.float32) - 186.0) / 62.0, 0.0, 1.0)[..., None]
        blur = cv2.GaussianBlur(out, (0, 0), 6.0).astype(np.float32)
        out = np.clip(out.astype(np.float32) + blur * mask * strength, 0, 255).astype(np.uint8)
    # 4) grão fino, periódico em 15 frames (amplitude contida: é acabamento,
    #    não "look VHS" — e custa bitrate)
    amp = 0.45 + 1.10 * r + 1.4 * suck_now(t)
    g = grain_field(frame % GRAIN_PERIOD)
    out = np.clip(out.astype(np.float32) + g * amp, 0, 255).astype(np.uint8)
    return out


def suck_now(t: float) -> float:
    for t_d in SWITCH_TIMES:
        if t_d > 45.0 and n_at(t_d - 1e-6) > n_at(t_d + 1e-6):
            dt = t - t_d
            if 0.0 <= dt < 0.55:
                return math.sin(math.pi * dt / 0.55)
    return 0.0


# =============================================================== QA =========
def sheet(images: list[np.ndarray], labels: list[str], path: Path, cols: int = 4, cell: int = 420) -> None:
    rows = []
    for r0 in range(0, len(images), cols):
        chunk = images[r0 : r0 + cols]
        labels_c = labels[r0 : r0 + cols]
        cells = []
        for im, lab in zip(chunk, labels_c):
            h = int(cell * im.shape[0] / im.shape[1])
            small = cv2.resize(im, (cell, h), interpolation=cv2.INTER_AREA)
            bar = np.full((26, cell, 3), 26, np.uint8)
            cv2.putText(bar, lab, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 230), 1, cv2.LINE_AA)
            cells.append(np.vstack([bar, small]))
        while len(cells) < cols:
            cells.append(np.zeros_like(cells[0]))
        rows.append(np.hstack(cells))
    cv2.imwrite(str(path), np.vstack(rows), [int(cv2.IMWRITE_JPEG_QUALITY), 90])


def alpha_fill_flag(sprites: dict[str, Sprite]) -> dict[str, float]:
    return {k: round(v.fill_ratio, 3) for k, v in sprites.items()}


def verify(sprites, bg, out_dir: Path) -> dict:
    """Frames de verificação, contagem por degrau e costura do loop."""
    times = [0.0, 7.5, 15.2, 22.7, 30.2, 37.7, 45.2, 53.0, 60.2, 63.95, 66.76, 69.58, 72.4, 74.97]
    stills, labels = [], []
    counts = []
    for t in times:
        fr = render_frame(t, sprites, bg)
        stills.append(fr)
        n = len(instance_state(t, sprites))
        counts.append({"t": round(t, 2), "n_compositor": n})
        labels.append(f"t={t:.1f}s N={n}")
    sheet(stills, labels, out_dir / "fase5_timeline.jpg", cols=4)
    cv2.imwrite(str(out_dir / "fase5_climax.jpg"), stills[7], [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    cv2.imwrite(str(out_dir / "fase5_first.jpg"), stills[0], [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    cv2.imwrite(str(out_dir / "fase5_last.jpg"), stills[-1], [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    m_loop = mae(stills[0], stills[-1])
    m_step = mae(stills[0], render_frame(1.0 / FPS, sprites, bg))
    # controlo honesto: o mesmo plano, meio ciclo de head-bob depois (pose
    # mais afastada dentro do mesmo estado). Se a costura for menor que isto,
    # é indistinguível de um frame normal da cena.
    m_control = mae(stills[0], render_frame(0.375, sprites, bg))
    a = cv2.resize(stills[0], (640, 360))
    b = cv2.resize(stills[-1], (640, 360))
    diff = cv2.absdiff(a, b)
    bar = np.full((32, 1920, 3), 26, np.uint8)
    cv2.putText(bar, "primeiro | ultimo | diferenca", (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 235, 230), 1)
    cv2.imwrite(str(out_dir / "fase5_loop_compare.jpg"), np.vstack([bar, np.hstack([a, b, diff])]),
                [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return {
        "counts": counts,
        "mae_control_half_bob": m_control,
        "peak_n": PEAK_N,
        "peak_t": next(t for t, n in STEPS if n == PEAK_N),
        "mae_loop": m_loop,
        "mae_step": m_step,
        # loop bom = costura mais parecida que um momento qualquer do mesmo
        # estado, e dentro de 3x o salto normal entre frames
        "loop_ok": bool(m_loop <= max(3.0 * m_step, 4.0) and m_loop < 0.5 * m_control),
    }


# ============================================================== export ======
def encode(frames_iter, path: Path, crf: int = 20) -> None:
    tmp = path.with_suffix(".tmp.mp4")
    tmp.unlink(missing_ok=True)
    path.unlink(missing_ok=True)
    write_mp4_with_crf(tmp, frames_iter, N_FRAMES, FPS, W, H, crf)
    tmp.replace(path)


def write_mp4_with_crf(path: Path, frame_iter, n: int, fps: int, w: int, h: int, crf: int) -> None:
    cmd = [
        FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-x264-params", "keyint=250:scenecut=0", "-movflags", "+faststart", str(path),
    ]
    log = path.with_suffix(".ffmpeg.log")
    with open(log, "wb") as logf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logf)
        assert proc.stdin is not None
        try:
            for fr in frame_iter:
                proc.stdin.write(np.ascontiguousarray(fr).tobytes())
        finally:
            proc.stdin.close()
            proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(log.read_text(errors="ignore")[-2000:])
    log.unlink(missing_ok=True)


def mux(video: Path, audio: Path, out: Path, bitrate: str = "256k") -> None:
    cmd = [
        FFMPEG, "-y", "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", bitrate, "-shortest", "-movflags", "+faststart", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-2000:])


def gif_preview(src: Path, out: Path, start: float, dur: float, width: int = 640, fps: int = 12) -> None:
    filt = (
        f"fps={fps},scale={width}:-2:flags=lanczos,"
        f"split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=full[p];"
        f"[s1][p]paletteuse=dither=bayer:bayer_scale=3"
    )
    cmd = [FFMPEG, "-y", "-ss", f"{start}", "-t", f"{dur}", "-i", str(src), "-vf", filt, "-loop", "0", str(out)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-2000:])


def poster(src: Path, out: Path, t: float) -> None:
    cmd = [FFMPEG, "-y", "-ss", f"{t}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-2000:])


# =============================================================== main =======
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=float, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--no-render", action="store_true", help="só QA, sem codificar o MP4")
    ap.add_argument("--crf", type=int, default=20)
    args = ap.parse_args()

    OUT_FINAL.mkdir(parents=True, exist_ok=True)
    sprites = {n: load_sprite(n) for n in SPRITE_NAMES}
    bg = BackgroundBank()

    if args.still is not None:
        fr = render_frame(args.still, sprites, bg)
        dest = Path(args.out) if args.out else OUT_FINAL / f"still_{args.still:.1f}.jpg"
        cv2.imwrite(str(dest), fr, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        print(f"{dest} · N={len(instance_state(args.still, sprites))}")
        return 0

    print("→ frames de verificação")
    report = verify(sprites, bg, OUT_FINAL)
    report["sprite_fill_ratio"] = alpha_fill_flag(sprites)
    report["resolution"] = [W, H]
    report["fps"] = FPS
    report["duration_s"] = DURATION
    report["steps"] = [[t, n] for t, n in STEPS]
    print(json.dumps({k: v for k, v in report.items() if k != "counts"}, indent=2, ensure_ascii=False))
    if args.verify or args.no_render:
        (OUT_FINAL / "fase5_qa.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    print("→ render 75 s @ 1920×1080")
    silent = OUT_FINAL / "coo_final_silent.mp4"

    def frames():
        for i in range(N_FRAMES):
            if i % 150 == 0:
                t = i / FPS
                print(f"   t={t:5.1f}s N={len(instance_state(t, sprites))}", flush=True)
            yield render_frame(i / FPS, sprites, bg)

    encode(frames(), silent, crf=args.crf)

    final = OUT_FINAL / "coo_final_1080p.mp4"
    if SCORE_WAV.exists():
        mux(silent, SCORE_WAV, final)
        silent.unlink(missing_ok=True)
    else:
        print("AVISO: trilha ausente — rode scripts/compose_score.py", file=sys.stderr)
        final = silent

    print("→ pós-produção de entrega")
    gif_preview(final, OUT_FINAL / "coo_preview_climax.gif", start=46.0, dur=10.0)
    gif_preview(final, OUT_FINAL / "coo_preview_loop.gif", start=0.0, dur=8.0, width=560, fps=10)
    poster(final, OUT_FINAL / "coo_poster.jpg", t=53.0)
    poster(final, OUT_FINAL / "coo_poster_abertura.jpg", t=1.5)

    # QA do ficheiro final (reencode → mede o que sai, não o que entra)
    first = extract(final, 0.0)
    second = extract(final, 1.0 / FPS)
    last = extract(final, DURATION - 1.0 / FPS)
    report["encoded"] = str(final.relative_to(ROOT))
    report["mae_loop_encoded"] = mae(first, last)
    report["mae_step_encoded"] = mae(first, second)
    report["loop_ok_encoded"] = bool(mae(first, last) <= max(3.0 * mae(first, second), 4.0))
    (OUT_FINAL / "fase5_qa.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("loop_ok", "mae_loop", "mae_step", "loop_ok_encoded", "mae_loop_encoded")}, indent=2))
    return 0


def extract(video: Path, t: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, fr = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"frame @ {t}s de {video}")
    return fr


if __name__ == "__main__":
    sys.exit(main())
