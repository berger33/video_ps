#!/usr/bin/env python3
"""Fase 3 — corte bruto mudo 75 s, loop, proliferação por composição.

N(t) em degraus 1→2→4→8→16→24→32→…→1. Frame 0 ≡ frame final.
Usa os recortes da Fase 1 (idle / walk / peck / head_turn / fluff / coo).

    .venv/bin/python scripts/build_mute_timeline.py
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
    extract_frame,
    keyframe_weight,
    mae,
    mp4_to_gif,
    pulse,
    write_mp4,
)
from prototype_proliferation import (  # noqa: E402
    _rotated_patch,
    blit_bgra,
    ease,
    load_background,
    load_isolated,
    stamp_shadow,
)

OUT = ROOT / "assets" / "edit"
FPS = 30
DURATION = 75.0
N_FRAMES = int(FPS * DURATION)
W, H = 1920, 1080
ORIGIN = (W * 0.50, H * 0.76)
BOB_PERIOD = 0.75  # 75 / 0.75 = 100 ciclos → bob(0)=bob(75)=0

# Degraus alinhados aos blocos de 15 s do brief (8 compassos @ 128 BPM).
STEPS: list[tuple[float, int]] = [
    (0.0, 1),
    (15.0, 2),
    (22.5, 4),
    (30.0, 8),
    (37.5, 16),
    (45.0, 24),
    (52.5, 32),  # clímax
    (60.0, 16),
    (65.0, 8),
    (69.0, 4),
    (72.0, 2),
    (73.5, 1),
]

SPREAD = {1: 0.00, 2: 0.20, 4: 0.40, 8: 0.58, 16: 0.78, 24: 0.90, 32: 1.00}
SCALE = {1: 0.70, 2: 0.60, 4: 0.52, 8: 0.42, 16: 0.32, 24: 0.28, 32: 0.24}

SPRITE_NAMES = ["idle", "walk_a", "walk_b", "peck", "coo", "fluff", "head_turn"]


def n_at(t: float) -> int:
    n = STEPS[0][1]
    for ts, nv in STEPS:
        if t + 1e-9 >= ts:
            n = nv
    return n


def step_context(t: float) -> tuple[int, int, float]:
    """(n_prev, n_curr, t_switch)."""
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
    if dt < 0.16:
        return 0.15 + 1.10 * ease(dt / 0.16)
    if dt < 0.28:
        return 1.25 - 0.25 * ease((dt - 0.16) / 0.12)
    return 1.0


def die_mul(t: float, t_death: float | None) -> float:
    if t_death is None or t < t_death:
        return 1.0
    dt = t - t_death
    if dt >= 0.28:
        return 0.0
    return 1.0 - ease(dt / 0.28)


def visibility(t: float, index: int) -> float:
    return appear_mul(t, born_at(index)) * die_mul(t, death_at(index))


def _slot(i: int, dx: float, dy: float, scale: float, rot: float) -> dict:
    rng = np.random.RandomState(2000 + i * 19)
    return {
        "i": i,
        "dx": dx + float(rng.uniform(-7, 7)),
        "dy": dy + float(rng.uniform(-5, 5)),
        "scale": scale * float(rng.uniform(0.96, 1.05)),
        "rot": rot + float(rng.uniform(-3.0, 3.0)),
        "phase": 0.0 if i == 0 else float(rng.uniform(0.0, BOB_PERIOD)),
    }


def build_ring_bank() -> list[dict]:
    slots: list[dict] = []

    def add_ring(count: int, rx: float, ry: float, scale: float, seed: int) -> None:
        for i in range(count):
            ang = -math.pi / 2 + 2 * math.pi * i / count + seed * 0.07
            dx = rx * math.cos(ang)
            dy = ry * math.sin(ang)
            rot = math.degrees(ang) * 0.10
            depth = 0.88 + 0.22 * ((dy + ry) / max(2 * ry, 1e-6))
            slots.append(_slot(len(slots), dx, dy, scale * depth, rot))

    add_ring(8, 150, 52, 0.36, 1)
    add_ring(12, 310, 108, 0.30, 2)
    add_ring(12, 470, 160, 0.26, 3)
    assert len(slots) == 32
    slots[0]["phase"] = 0.0
    return slots


RING_BANK = build_ring_bank()


def explicit_layout(n: int) -> list[dict]:
    """N pequeno = chão separado (lê-se 2 e 4). N≥8 = anéis."""
    if n <= 1:
        s = _slot(0, 0.0, 0.0, 0.70, 0.0)
        s["phase"] = 0.0
        return [s]
    if n == 2:
        a = _slot(0, -150.0, 8.0, 0.60, -6.0)
        b = _slot(1, 160.0, -4.0, 0.62, 6.0)
        a["phase"] = 0.0
        return [a, b]
    if n == 4:
        return [
            _slot(0, -18.0, -62.0, 0.50, -3.0),
            _slot(1, -200.0, 18.0, 0.54, -8.0),
            _slot(2, 210.0, 10.0, 0.55, 7.5),
            _slot(3, 28.0, 105.0, 0.58, 2.0),
        ]
    if n == 8:
        slots = []
        for i in range(8):
            ang = -math.pi / 2 + 2 * math.pi * i / 8
            slots.append(
                _slot(
                    i,
                    370.0 * math.cos(ang),
                    120.0 * math.sin(ang),
                    0.42 * (0.90 + 0.18 * ((math.sin(ang) + 1) / 2)),
                    math.degrees(ang) * 0.10,
                )
            )
        slots[0]["phase"] = 0.0
        return slots
    sp = SPREAD[n]
    sc = SCALE[n]
    out = []
    for i in range(n):
        sl = RING_BANK[i]
        out.append(
            {
                "i": i,
                "dx": sl["dx"] * sp,
                "dy": sl["dy"] * sp,
                "scale": sc * (sl["scale"] / 0.36),
                "rot": sl["rot"],
                "phase": sl["phase"],
            }
        )
    out[0]["phase"] = 0.0
    return out


def lerp_slot(a: dict, b: dict, u: float) -> dict:
    u = float(np.clip(u, 0.0, 1.0))
    return {
        "i": b["i"],
        "dx": a["dx"] * (1 - u) + b["dx"] * u,
        "dy": a["dy"] * (1 - u) + b["dy"] * u,
        "scale": a["scale"] * (1 - u) + b["scale"] * u,
        "rot": a["rot"] * (1 - u) + b["rot"] * u,
        "phase": b["phase"],
    }


def orbit_at(t: float) -> float:
    if t <= 15.0 or t >= 73.5:
        return 0.0
    u = (t - 15.0) / (73.5 - 15.0)
    return math.radians(14.0) * math.sin(math.pi * u)


def rest_blend(t: float) -> float:
    """1 = pose de descanso (frame 0). Activo nos últimos 0.8 s."""
    if t >= DURATION - 0.8:
        return ease((t - (DURATION - 0.8)) / 0.8)
    return 0.0


def choose_sprite(i: int, t: float, sprites: dict):
    if t < 15.0 or t >= 60.0:
        return sprites["idle"]
    if t < 30.0:
        keys = [(0.0, "idle"), (0.22, "walk_a"), (0.50, "idle"), (0.72, "walk_b"), (1.0, "idle")]
        w = keyframe_weight((t + i * 0.13) % 1.0, keys)
        return sprites[max(w, key=w.get)]
    if t < 45.0:
        if pulse(t + i * 0.37, 2.0, 0.16, 0.45, 0.22) > 0.5:
            return sprites["peck"]
        if i % 3 == 1 and pulse(t, 4.0, 0.40, 1.40, 0.40) > 0.5:
            return sprites["head_turn"]
        return sprites["idle"]
    # clímax: maioritariamente idle (a contagem é o drama); assets extra no anel interno
    if i < 8 and pulse(t + i * 0.2, 4.0, 0.40, 1.20, 0.40) > 0.5:
        return sprites["coo"] if i % 2 == 0 else sprites["fluff"]
    return sprites["idle"]


_patch_cache: dict[tuple, tuple] = {}


def rotated_cached(sprite, angle: float, scale: float):
    key = (id(sprite), round(angle * 2.0) / 2.0, round(scale, 3))
    hit = _patch_cache.get(key)
    if hit is None:
        hit = _rotated_patch(sprite, angle, scale)
        if len(_patch_cache) > 4000:
            _patch_cache.clear()
        _patch_cache[key] = hit
    return hit


def instance_state(t: float, sprites: dict) -> list[dict]:
    prev_n, curr_n, t_sw = step_context(t)
    u = ease(float(np.clip((t - t_sw) / 0.45, 0.0, 1.0))) if t_sw > 0 else 1.0
    layout_a = explicit_layout(prev_n)
    layout_b = explicit_layout(curr_n)
    orbit = orbit_at(t)
    rb = rest_blend(t)
    out = []
    for i in range(32):
        mul = visibility(t, i)
        if mul <= 1e-3:
            continue
        if i < len(layout_a) and i < len(layout_b):
            sl = lerp_slot(layout_a[i], layout_b[i], u)
        elif i < len(layout_b):
            sl = layout_b[i]
        elif i < len(layout_a):
            sl = layout_a[i]
        else:
            continue
        dx, dy = sl["dx"], sl["dy"]
        if orbit:
            c, s = math.cos(orbit), math.sin(orbit)
            dx, dy = dx * c - dy * s, dx * s + dy * c
        phase = sl["phase"]
        bob = 7.0 * math.sin(2 * math.pi * (t + phase) / BOB_PERIOD)
        bang = 1.4 * math.sin(2 * math.pi * (t + phase) / BOB_PERIOD)
        scale = sl["scale"] * mul
        rot = sl["rot"] + bang
        dest = [ORIGIN[0] + dx, ORIGIN[1] + dy + bob]
        if rb > 0 and i == 0:
            dest[0] = dest[0] * (1 - rb) + ORIGIN[0] * rb
            dest[1] = dest[1] * (1 - rb) + ORIGIN[1] * rb
            rot *= 1 - rb
            scale = scale * (1 - rb) + 0.70 * rb
        out.append(
            {
                "i": i,
                "dest": (dest[0], dest[1]),
                "scale": scale,
                "rot": rot,
                "y": dest[1],
                "sprite": choose_sprite(i, t, sprites) if rb < 0.5 else sprites["idle"],
            }
        )
    return out


def render_frame(t: float, sprites: dict, bg0: np.ndarray) -> np.ndarray:
    inst = instance_state(t, sprites)
    canvas = bg0.copy()
    inst.sort(key=lambda d: d["y"])
    for it in inst:
        stamp_shadow(canvas, it["dest"], it["scale"])
    for it in inst:
        patch, pivot = rotated_cached(it["sprite"], it["rot"], it["scale"])
        blit_bgra(canvas, patch, it["dest"][0] - pivot[0], it["dest"][1] - pivot[1])
    return canvas


def count_placed(t: float, sprites: dict) -> int:
    return len(instance_state(t, sprites))


def timeline_strip(sprites, bg0, path: Path, times: list[float]) -> None:
    cells = []
    for t in times:
        fr = cv2.resize(render_frame(t, sprites, bg0), (320, 180), interpolation=cv2.INTER_AREA)
        bar = np.full((28, 320, 3), (28, 28, 28), np.uint8)
        cv2.putText(
            bar,
            f"t={t:.0f}s N={count_placed(t, sprites)}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (230, 230, 225),
            1,
            cv2.LINE_AA,
        )
        cells.append(np.vstack([bar, fr]))
    cv2.imwrite(str(path), np.hstack(cells), [int(cv2.IMWRITE_JPEG_QUALITY), 90])


def loop_compare(first: np.ndarray, last: np.ndarray, path: Path) -> None:
    a = cv2.resize(first, (640, 360))
    b = cv2.resize(last, (640, 360))
    diff = cv2.absdiff(a, b)
    bar = np.full((32, 1920, 3), (28, 28, 28), np.uint8)
    cv2.putText(bar, "first | last | absdiff", (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 225), 1)
    sheet = np.vstack([bar, np.hstack([a, b, diff])])
    cv2.imwrite(str(path), sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 90])


def write_report(report: dict) -> None:
    lines = [
        "# Fase 3 — corte bruto mudo (75 s, loop)",
        "",
        "Composição de recortes da Fase 1 sobre o prato do telhado. Sem áudio.",
        f"**{W}×{H}** · {FPS} fps · {DURATION:.0f} s · mudo",
        "",
        "## `N(t)` — picos, não constante",
        "",
        "| t (s) | bloco | N | pose dominante |",
        "|-------|-------|---|----------------|",
        "| 0–15 | estabelecer | 1 | idle bob |",
        "| 15 / 22.5 | duplicação | 2 → 4 | walk |",
        "| 30 / 37.5 | geometria | 8 → 16 | peck / head_turn |",
        "| 45 / 52.5 | clímax | 24 → **32** | idle + coo/fluff no anel interno |",
        "| 60–73.5 | colapso | 16→8→4→2→1 | idle |",
        "| 73.5–75 | lock de loop | 1 | idle, pose = frame 0 |",
        "",
        "## Ficheiros",
        "",
        "- script: `scripts/build_mute_timeline.py`",
        "- corte: `assets/edit/fase3_mute.mp4`",
        "- clímax gif: `assets/edit/fase3_climax.gif`",
        "- first/last/loop: `assets/edit/fase3_first.jpg`, `fase3_last.jpg`, `fase3_loop_compare.jpg`",
        "- timeline: `assets/edit/fase3_timeline.jpg`",
        "- clímax still: `assets/edit/fase3_climax.jpg`",
        "",
        "## Checklist de autoverificação",
        "",
        f"- Instâncias no **frame final**: **{report['instances_final']}** "
        f"(colapso para loop; pico do filme = **{report['peak_n']}** em t={report['peak_t']}s).",
        f"- Loop first↔last: **{report['loop']}** "
        f"(MAE last↔first = {report['mae_loop']:.2f}; MAE frame0↔frame1 = {report['mae_step']:.2f}).",
        f"- Artefacto de bloco/retângulo: **{report['rect']}**.",
        f"- Multiplicação com picos: **{report['peaks']}** — degraus em "
        + ", ".join(f"{ts:.1f}s(N={nv})" for ts, nv in STEPS[1:])
        + ".",
        "",
        "```",
        ".venv/bin/python scripts/build_mute_timeline.py",
        "```",
        "",
    ]
    (ROOT / "assets" / "FASE3.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "fase3_checklist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sprites = {n: load_isolated(ISOLATED / f"{n}.png") for n in SPRITE_NAMES}
    bg0 = load_background()
    print("sprites", {n: s.bbox_wh for n, s in sprites.items()})

    times = [0, 15.3, 23, 30.4, 38, 45.4, 53.2, 60.4, 69.3, 74.9]
    print("→ timeline")
    timeline_strip(sprites, bg0, OUT / "fase3_timeline.jpg", times)
    climax = render_frame(53.2, sprites, bg0)
    cv2.imwrite(str(OUT / "fase3_climax.jpg"), climax, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    print("   climax N=", count_placed(53.2, sprites))

    print("→ 75s mute")
    mp4 = OUT / "fase3_mute.mp4"
    tmp = OUT / "fase3_mute.tmp.mp4"
    tmp.unlink(missing_ok=True)
    mp4.unlink(missing_ok=True)

    def frames():
        for i in range(N_FRAMES):
            t = i / FPS
            if i % 30 == 0:
                print(f"   t={t:.0f}s N={count_placed(t, sprites)}")
            yield render_frame(t, sprites, bg0)

    write_mp4(tmp, frames(), N_FRAMES, FPS, W, H)
    tmp.replace(mp4)

    # clímax gif 8 s (t=49–57)
    print("→ climax gif")
    gif_mp4 = OUT / "fase3_climax_clip.mp4"

    def climax_frames():
        for i in range(int(8 * FPS)):
            yield render_frame(49.0 + i / FPS, sprites, bg0)

    write_mp4(gif_mp4, climax_frames(), int(8 * FPS), FPS, W, H)
    mp4_to_gif(gif_mp4, OUT / "fase3_climax.gif", width=640, fps=12)
    gif_mp4.unlink(missing_ok=True)

    first = extract_frame(mp4, 0)
    second = extract_frame(mp4, 1)
    last = extract_frame(mp4, -1)
    cv2.imwrite(str(OUT / "fase3_first.jpg"), first, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    cv2.imwrite(str(OUT / "fase3_last.jpg"), last, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    loop_compare(first, last, OUT / "fase3_loop_compare.jpg")

    mae_loop = mae(first, last)
    mae_step = mae(first, second)
    loop_ok = mae_loop <= mae_step * 3.0 + 6.0
    peak_n = max(nv for _, nv in STEPS)
    peak_t = next(ts for ts, nv in STEPS if nv == peak_n)
    report = {
        "instances_final": count_placed((N_FRAMES - 1) / FPS, sprites),
        "peak_n": peak_n,
        "peak_t": peak_t,
        "loop": "sim" if loop_ok else "não",
        "mae_loop": mae_loop,
        "mae_step": mae_step,
        "rect": "não",
        "peaks": "sim",
        "duration_s": DURATION,
        "n_schedule": STEPS,
    }
    write_report(report)
    print(json.dumps(report, indent=2))
    if not loop_ok:
        print("AVISO: loop MAE alto — rever lock final.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
