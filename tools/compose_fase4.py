#!/usr/bin/env python3
"""FASE 4 — build do trecho completo 0:00-0:45 (1080 frames @ 24fps).

Desenho (docs/fase4-build.md):
  S1 f0-257    "documental": janela de caminhada w160_235 em 4 trechos
               (jump-cuts); sem compostos.
  S2 f258-1079 "forrageio": janela w370_442 em ciclos — walk-chunk
               (src 370-399 + 412-441, taxas 0,97-1,03x) + peck-chunk
               (src 393-411, tempo real) nas bicadas:
               f288 (salto), f400 (F2: 1->2), f480/483 (2->4), f576
               (preparo), f744 (+rachadura f756: patas MP#1),
               f864/f936/f1008 (MP#2/#3/#4 na camada de minibicadas),
               f1068 COLETIVA (bicada real + 4 minipombos, stagger
               0/2/4/6f) -> hold 12f -> CORTE f1080 (45,000s).

Compostos (referencial f406, persistem em S2):
  Migalhas A/B/C/D (sprite, carapaca), minipombos 1-4 (sprite, nascem das
  caracas por oclusao), sombras sinteticas, cor casada (GRADE da F2).

Tecnicas: oclusao (revelacao 10f, zero pop), offset de tempo (fases/escalas
próprias), sombra de contato, profundidade por escala.

Saidas (assets/out/fase4/): frames 1280x720, zoom 2,4x, MP4s, reel,
layers (amostras p/ verify), evento.json (LUT em segmentos + estados).

Uso: tools/venv/bin/python tools/compose_fase4.py
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OMP_NUM_THREADS", "2")
import compose_fase2 as C  # noqa: E402  (grade, sombra, render, rachadura)

def cut_halves_opaque(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Versao F4 da rachadura: metades OPACAS ate a linha de corte (tiling
    sem emenda no estado fechado => cobertura 100% do conteudo interior;
    a penumbra de 2px fica so na borda interna, visivel quando abre).
    A F2 usa C.cut_halves (feather simetrico); o look e o mesmo quando
    aberto, e o estado fechado da F4 e perfeitamente opaco (anti-pop
    maximo)."""
    h, w = rgba.shape[:2]
    xn, yn = [0.513, 0.490, 0.524, 0.502], [0.0, 0.321, 0.688, 1.0]
    xs = [int(x * (w - 1)) for x in xn]
    ys = [int(y * (h - 1)) for y in yn]
    feather = 2.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pts = []
    for i in range(len(xs) - 1):
        n = int(max(2, np.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i])))
        for k in range(n + 1):
            t = k / n
            pts.append((xs[i] + t * (xs[i + 1] - xs[i]),
                        ys[i] + t * (ys[i + 1] - ys[i])))
    pts = np.array(pts, np.float32)
    d = np.min(np.hypot(xx[:, :, None] - pts[None, None, 0, :],
                        yy[:, :, None] - pts[None, None, 1, :]), axis=2)
    sign = np.where(xx >= np.interp(yy, ys, xs), 1.0, -1.0)
    s_ = sign * d  # >0 direita da linha, <0 esquerda
    m_left = np.clip(1.0 - np.maximum(s_, 0.0) / feather, 0, 1)
    m_right = np.clip(1.0 - np.maximum(-s_, 0.0) / feather, 0, 1)
    left = rgba.copy()
    right = rgba.copy()
    left[:, :, 3] *= m_left
    right[:, :, 3] *= m_right
    return left, right


SRC_PECK = os.path.join(ROOT, "assets", "plates", "w370_442", "stab")
SRC_WALK = os.path.join(ROOT, "assets", "plates", "w160_235", "stab")
SPR = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "assets", "out", "fase4")

FW, FH = C.FW, C.FH            # 1280x720
FPS = 24
NF = 1080                      # 45,000s
S1_END = 257                   # S1 = 0..257 ; S2 = 258..1079
PECKS = [288, 400, 480, 576, 744, 1068]
PECK_SRC = list(range(393, 412))          # 19f; contato no idx 7 (src 400)
WALK_CYCLE = list(range(370, 400)) + list(range(412, 442))  # 60f sem bicada
WALK_RATES = [1.00, 0.97, 1.02, 0.98, 1.03, 0.97, 1.01, 0.98]

# --------------------------- compostos (S2) --------------------------------
SCALE_A = C.SCALE_A                        # 40px / 582
MIG = {
    # nome: (escala, fase wobble, posicao-ancora, slide (t0,t1,fx,fy), hops)
    "A": {"scale": SCALE_A,        "phase": 0,  "pos": (452.0, 621.0)},
    "B": {"scale": SCALE_A * 0.68, "phase": 9,  "pos": (452.0, 619.0),
          "slide": (412, 421, 40.0, -2.0)},
    "C": {"scale": SCALE_A * 0.62, "phase": 3,  "pos": (452.0, 621.0),
          "slide": (492, 501, -32.0, 3.0)},
    "D": {"scale": SCALE_A * 0.55, "phase": 13, "pos": (452.0, 621.0),
          "slide": (501, 510, 88.0, -5.0)},
}
# rachaduras como keyframes (t, gap, rot): a carapaca B SELA apos o MP#1
# (leitura de carapaca/coao confirmada) e REABRE em f1008 p/ o MP#4.
KEYF = {
    "A": [(412, 0.0, 0.0), (421, 8.0, 6.0), (492, 8.0, 6.0),
          (510, 12.0, 8.0), (1008, 12.0, 8.0), (1017, 14.0, 9.0)],
    "B": [(756, 0.0, 0.0), (765, 8.0, 8.0), (780, 8.0, 8.0),
          (800, 0.0, 0.0), (1008, 0.0, 0.0), (1017, 8.0, 8.0)],
    "C": [(864, 0.0, 0.0), (873, 8.0, 8.0)],
    "D": [(936, 0.0, 0.0), (945, 8.0, 8.0)],
}


def crack_state(name: str, t: int) -> tuple[float, float]:
    ks = KEYF[name]
    if not ks or t < ks[0][0]:
        return 0.0, 0.0
    for i in range(len(ks) - 1):
        t0, g0, r0 = ks[i]
        t1, g1, r1 = ks[i + 1]
        if t0 <= t <= t1:
            p = C.ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            return g0 + (g1 - g0) * p, r0 + (r1 - r0) * p
    t_, g_, r_ = ks[-1]
    return g_, r_
BORN = {"A": 258, "B": 412, "C": 492, "D": 501}

# minipombos: nascem da carapaca correspondente
BIRD = {
    #      shell  (w px)  reveal      estacao (x,y)  caminhada (t0,t1)  bob T
    # w_px tem margena >= 2px dentro da carapaca fechada (anti-vazamento)
    "1": ("B", 22.0, (756, 765), (508.0, 618.0), (780, 810), 11.0),
    "2": ("C", 21.0, (864, 873), (536.0, 620.0), (884, 940), 13.0),
    "3": ("D", 18.0, (936, 945), (596.0, 613.0), (956, 1010), 15.0),
    "4": ("B", 22.0, (1008, 1017), (560.0, 622.0), (1028, 1058), 9.0),
}
BIRD_SPR_W = 1028.0
# swob (respiracao/trabalho do corpo) unico por bird: (periodo, amp graus,
# fase, rotacao base) — rot_base diferente torna poses idênticas
# simultaneas estruturalmente impossíveis (regra de offset de tempo)
BIRD_SWOB = {"1": (15.0, 2.2, 2.1, 0.0),
             "2": (17.0, 1.6, 4.3, -3.0),
             "3": (19.0, 2.8, 1.0, 2.5),
             "4": (13.0, 1.9, 6.2, -2.0)}
# bicadas proprias (cabeça pra baixo) nos frames da grade de minibicadas
BIRD_DIPS = {
    "1": [900, 972, 1068],
    "2": [948, 1020, 1070],
    "3": [990, 1044, 1072],
    "4": [1032, 1074],
}
# coletiva f1068: stagger 0/2/4/6f nos 4 minipecks do audio
COLLECTIVE = 1068

HOP_H, BOUNCE_H = 14.0, 4.0          # como na F2
WOB_T, WOB_AMP = 18.0, 1.8
FW_, FH_ = FW, FH
FFMPEG = C.FFMPEG
ZOOM = (520, 700, 240, 760)          # y0,y1,x0,x1 do crop de legibilidade


# ------------------------------- LUT ----------------------------------------
def build_lut() -> tuple[list[tuple[int, int]], dict[int, tuple[str, int]]]:
    """Retorna (segmentos, lut). segmentos = [(film_a, film_b, origem,
    src_a, src_b, taxa)] p/ o evento.json; lut = film_f -> (origem, src_f)."""
    lut: dict[int, tuple[str, int]] = {}
    segs: list[tuple[int, int, str, int, int, float]] = []
    # S1: janela de caminhada 160-234 (75f) em 4 trechos
    chunks = [(0, 74), (75, 149), (150, 224), (225, 257)]
    for a, b in chunks:
        src_a = 160 + (a % 75) if a < 225 else 160 + (a - 225)
        segs.append((a, b, "walk", src_a, src_a + (b - a), 1.0))
        for f in range(a, b + 1):
            lut[f] = ("walk", 160 + (f % 75) if f < 225 else 160 + (f - 225))
    # S2: walk fills + peck chunks
    pos = S1_END + 1
    cyc = 0
    wp = 0.0  # posicao fracionaria no walk cycle
    for target in PECKS:
        fill_end = target - 7
        while pos < fill_end:
            r = WALK_RATES[cyc % len(WALK_RATES)]
            src = int(wp) % len(WALK_CYCLE)
            lut[pos] = ("peckwin", WALK_CYCLE[src])
            wp += r
            if int(wp) >= len(WALK_CYCLE):
                wp -= len(WALK_CYCLE)
                cyc += 1
            pos += 1
        for i, s in enumerate(PECK_SRC):
            lut[target - 7 + i] = ("peckwin", s)
        pos = target + 12
    assert pos == NF, f"LUT nao fecha: pos={pos}"
    # comprime o lut em segmentos contiguos (p/ o evento.json)
    t = 0
    while t < NF:
        o, s0 = lut[t]
        t2 = t
        while t2 + 1 < NF:
            o2, s2 = lut[t2 + 1]
            if o2 != o or (o == "peckwin" and s2 != s0 + (t2 - t)):
                break
            t2 += 1
        typ = "peck" if o == "peck" or (o == "peckwin"
                                        and s0 >= 393 and s0 <= 411
                                        and t2 - t + 1 >= 19) else (
            "walk_s1" if o == "walk" else "walk_s2")
        segs.append((t, t2, o, s0, lut[t2][1], typ))
        t = t2 + 1
    return segs, lut


# --------------------------- estados por frame ------------------------------
def hop_dy(t: int, t0: int) -> tuple[float, tuple[float, float]]:
    """Salto F2: arco 14px (9f) + quique 4px (3f) + squashes."""
    if t0 <= t <= t0 + 9:
        u = (t - t0) / 9.0
        return -HOP_H * 4 * u * (1 - u), (1.06, 0.90) if t == t0 else (1.0, 1.0)
    if t0 + 9 < t <= t0 + 12:
        u = (t - t0 - 9) / 3.0
        sq = (1.09, 0.86) if t == t0 + 9 else (1.0, 1.0)
        return -BOUNCE_H * 4 * u * (1 - u), sq
    return 0.0, (1.0, 1.0)


def migalha_ev(name: str, t: int) -> dict | None:
    """Estado da migalha/carapaca no frame t (None = ainda nao existe)."""
    if t < BORN[name]:
        return None
    m = MIG[name]
    ax, ay = m["pos"]
    dx, dy_slide = 0.0, 0.0
    if "slide" in m:
        s0, s1, sx, sy = m["slide"]
        if t >= s0:
            p = C.ease((t - s0) / (s1 - s0)) if s1 > s0 else 1.0
            dx, dy_slide = sx * p, sy * p
    # rachadura (keyframes; a carapaca pode selar e reabrir)
    gap, rot = crack_state(name, t)
    # A: salto em toda bicada real; 480/483 = dupla (K3 do audio); 1068 =
    # coletiva (o bico bate na carapaca aberta)
    hops = {"A": [288, 400, 480, 483, 576, 1068]}.get(name, [])
    dy = 0.0
    squash = (1.0, 1.0)
    for h0 in hops:
        d, s = hop_dy(t, h0)
        if d < dy:          # salto duplo: fica o mais profundo
            dy = d
        if s != (1.0, 1.0):  # squash: jato do impacto mais recente
            squash = s
    wob = WOB_AMP * np.sin(2 * np.pi * t / WOB_T + m["phase"])
    return {"pos": (ax + dx, ay + dy_slide), "scale": m["scale"],
            "gap": gap, "rot0": rot, "wob": wob, "dy": dy,
            "squash": squash, "born": BORN[name]}


def bird_ev(bn: str, t: int) -> dict | None:
    shell, w_px, (r0, r1), (sx, sy), (w0, w1), bobT = BIRD[bn]
    if t < r0:
        return None
    m = MIG[shell]
    px, py = m["pos"]
    if "slide" in m:  # a carapaca ja deslizou no birth (estacao do shell)
        s0, s1, sx_, sy_ = m["slide"]
        p = C.ease((t - s0) / (s1 - s0))
        px, py = px + sx_ * p, py + sy_ * p
    # subida da carapaca: 10px em 18f a partir de r0+2
    rise = 0.0
    if t >= r0 + 2:
        rise = 10.0 * (1.0 - C.ease(min(1.0, (t - r0 - 2) / 18.0)))
    # caminhada p/ estacao
    cx, cy = px, py
    if t >= w0:
        p = C.ease(min(1.0, (t - w0) / (w1 - w0)))
        cx, cy = px + (sx - px) * p, py + (sy - py) * p
    # bob (respiracao/andar) apos a subida
    bob = 0.0
    if t > r1:
        bob = -1.0 * (1.0 + np.sin(2 * np.pi * (t - r1) / bobT + float(bn))) * 0.5
    # dip (bicada propria): squash vertical + dy + rot
    dip = 0
    for k, d in enumerate(BIRD_DIPS[bn]):
        if d == t:
            dip = 1
        elif d + 1 == t:
            dip = 2
        elif d + 2 == t:
            dip = 3
    sq = (1.0, 1.0)
    ddy, drot = 0.0, 0.0
    if dip == 1:
        sq, ddy, drot = (1.0, 0.90), 2.0, -5.0
    elif dip == 2:
        sq, ddy, drot = (1.0, 0.84), 3.0, -7.0
    elif dip == 3:
        sq, ddy, drot = (1.0, 0.90), 1.0, -3.0
    T_s, amp_s, ph_s, base_s = BIRD_SWOB[bn]
    swob = base_s + amp_s * np.sin(2 * np.pi * (t - r1) / T_s + ph_s)
    return {"pos": (cx, cy), "w_px": w_px, "dy": rise + bob + ddy,
            "rot": swob + drot, "squash": sq, "reveal": (r0, r1),
            "shell": shell}


# ------------------------------- render ------------------------------------
def main() -> int:
    os.makedirs(os.path.join(OUT, "layers"), exist_ok=True)
    segs, lut = build_lut()

    mig = C.grade(C.load_rgba(os.path.join(SPR, "migalha_rgba.png")), C.GRADE)
    half_L, half_R = cut_halves_opaque(mig)
    bird = C.grade(C.load_rgba(os.path.join(SPR, "minipombo_rgba.png")), C.GRADE)

    # cache de frames de origem (evita reler PNGs repetidos dos ciclos)
    cache: dict[tuple[str, int], np.ndarray] = {}

    def src_frame(o: str, s: int) -> np.ndarray:
        k = (o, s)
        if k not in cache:
            d = SRC_WALK if o == "walk" else SRC_PECK
            f = cv2.imread(os.path.join(d, f"s{s}.png"))
            cache[k] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB).astype(np.float32)
        return cache[k].copy()

    # amostras p/ layers (verify): covers reveal + coletivas + repouso
    samples = sorted(set(
        [258, 288, 300, 392, 400, 412, 416, 421, 492, 496, 505, 510,
         576, 744, 752, 756, 760, 765, 864, 868, 873, 936, 940, 945,
         1008, 1012, 1017, 1032, 1061, 1068, 1071, 1074, 1079]
        + [756, 757, 864, 865, 936, 937, 1008, 1009]))  # 1o frames da oclusao

    reveal_log: dict[str, dict] = {}
    opens = [("migalha_A_abre1", 412, 421),
             ("migalha_A_abre2", 492, 510),
             ("migalha_B_abre1", 756, 765),
             ("migalha_B_abre2", 1008, 1017),
             ("migalha_C_abre", 864, 873),
             ("migalha_D_abre", 936, 945)]
    for tag, c0, c1 in opens:
        reveal_log[tag] = {"t0": c0, "t1": c1, "frames": c1 - c0}
    for bn, (shell, w, (r0, r1), st, wk, bt) in BIRD.items():
        reveal_log[f"minipombo_{bn}"] = {"t0": r0, "t1": r1,
                                         "frames": r1 - r0,
                                         "carapaca": shell}

    n_frames = 0
    for t in range(NF):
        o, s = lut[t]
        frame = src_frame(o, s)
        evs: list[dict] = []

        if t >= S1_END + 1:
            # migalhas
            for name in "ABCD":
                ev = migalha_ev(name, t)
                if ev:
                    evs.append({"kind": "mig", "name": name, **ev})
            # minipombos (sempre ATRAS da propria carapaca)
            for bn in "1234":
                ev = bird_ev(bn, t)
                if ev:
                    evs.append({"kind": "bird", "name": bn, **ev})

            # ------------- renderiza objetos (2x SSAA via C) -------------
            objs = []
            for ev in evs:
                if ev["kind"] == "bird":
                    sc = ev["w_px"] / BIRD_SPR_W
                    c, pv = C.render_object(bird, sc, ev["rot"], ev["squash"])
                    objs.append((ev, c, pv, "bird" + ev["name"]))
                else:
                    w_rot = ev["wob"]
                    cL, pvL = C.render_object(half_L, ev["scale"],
                                              w_rot - ev["rot0"], ev["squash"])
                    cR, pvR = C.render_object(half_R, ev["scale"],
                                              w_rot + ev["rot0"], ev["squash"])
                    objs.append((ev, cL, pvL, "mig" + ev["name"] + "L"))
                    objs.append((ev, cR, pvR, "mig" + ev["name"] + "R"))

            # ------------- sombras (uma por objeto, mais distante 1o) ----
            def canvases_of(ev):
                base = ("mig" + ev["name"] if ev["kind"] == "mig"
                        else "bird" + ev["name"])
                for (ev2, c, pv, tag) in objs:
                    if tag.startswith(base):
                        ax, ay = ev["pos"]
                        if ev["kind"] == "mig" and tag.endswith("L"):
                            ax -= ev["gap"] / 2
                        if ev["kind"] == "mig" and tag.endswith("R"):
                            ax += ev["gap"] / 2
                        yield c, pv, (ax, ay)

            for ev in sorted(evs, key=lambda e: -e["pos"][1]):
                plane = np.zeros((FH, FW), np.float32)
                cs = list(canvases_of(ev))
                for c, pv, anch in cs:
                    C.paste_canvas(plane, c, pv, anch, ev.get("dy", 0.0),
                                   alpha_only=True)
                # obj_size = largura de canvas renderizado (como na F2)
                if ev["kind"] == "mig":
                    size = cs[0][0].shape[1] + cs[1][0].shape[1] - 40
                else:
                    size = cs[0][0].shape[1]
                C.draw_shadow(frame, plane, ev["pos"], ev.get("dy", 0.0),
                              C.SHADOW, size)

            # ------------- composicao (z: y crescente = mais perto;
            #                 bird sempre ANTES da propria carapaca) ------
            out = np.clip(frame, 0, 255).astype(np.uint8)
            order = sorted(range(len(evs)), key=lambda i: (
                evs[i]["pos"][1], evs[i]["kind"] == "mig"))
            for i in order:
                ev = evs[i]
                for c, pv, anch in canvases_of(ev):
                    C.paste_canvas(out, c, pv, anch, ev.get("dy", 0.0))

            # ------------- dump de layers (amostras) ---------------------
            if t in samples:
                for (ev2, c, pv, tag) in objs:
                    a = c[:, :, 3]
                    rows = np.any(a > 8, axis=1)
                    cols = np.any(a > 8, axis=0)
                    if not rows.any():
                        continue
                    y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
                    x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
                    crop = c[y0:y1 + 1, x0:x1 + 1]
                    cv2.imwrite(os.path.join(OUT, "layers", f"f{t}_{tag}.png"),
                                cv2.cvtColor(crop.astype(np.uint8),
                                             cv2.COLOR_RGBA2BGRA))
                meta = {"t": t,
                        "migas": {e["name"]: e for e in evs
                                  if e["kind"] == "mig"},
                        "birds": {e["name"]: e for e in evs
                                  if e["kind"] == "bird"}}
                with open(os.path.join(OUT, "layers", f"f{t}_meta.json"), "w") as fh:
                    json.dump(meta, fh, indent=1, default=float)

        img = out if t >= S1_END + 1 else frame.astype(np.uint8)
        cv2.imwrite(os.path.join(OUT, f"f{t:04d}.png"),
                    cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        zy0, zy1, zx0, zx1 = ZOOM
        z = cv2.resize(img[zy0:zy1, zx0:zx1],
                       (int((zx1 - zx0) * 2.4), int((zy1 - zy0) * 2.4)),
                       interpolation=cv2.INTER_CUBIC)
        cv2.putText(z, f"f{t}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (255, 60, 40), 2)
        cv2.imwrite(os.path.join(OUT, f"z{t:04d}.png"),
                    cv2.cvtColor(z, cv2.COLOR_RGB2BGR))
        n_frames += 1

    # ------------------------------ videos ---------------------------------
    os.system(f'{FFMPEG} -hide_banner -loglevel error -framerate 24 '
              f'-i {OUT}/f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 17 '
              f'-movflags +faststart {OUT}/fase4_full.mp4 -y')
    os.system(f'{FFMPEG} -hide_banner -loglevel error -framerate 24 '
              f'-i {OUT}/z%04d.png -c:v libx264 -pix_fmt yuv420p -crf 17 '
              f'-movflags +faststart {OUT}/fase4_zoom.mp4 -y')

    evento = {
        "duracao_frames": NF, "fps": FPS, "duracao_s": NF / FPS,
        "shots": {"S1": [0, S1_END], "S2": [S1_END + 1, NF - 1]},
        "bicadas_visuais": PECKS,
        "coletiva": COLLECTIVE, "corte": NF,
        "revelacoes": reveal_log,
        "lut_segmentos": segs,
        "migas": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv)
                      for kk, vv in v.items()} for k, v in MIG.items()},
        "caracas_keyframes": {k: v for k, v in KEYF.items()},
        "minipombos": {bn: {"carapaca": v[0], "w_px": v[1], "reveal": v[2],
                            "estacao": v[3], "caminhada": v[4],
                            "dips": BIRD_DIPS[bn]}
                       for bn, v in BIRD.items()},
        "grade_cor": C.GRADE, "sombra": C.SHADOW,
    }
    with open(os.path.join(OUT, "evento.json"), "w") as fh:
        json.dump(evento, fh, indent=1, ensure_ascii=False)

    # reel de contact sheet
    reel_ids = [0, 60, 150, 257, 262, 281, 288, 296, 392, 400, 406, 412, 417,
                421, 480, 492, 505, 510, 576, 744, 752, 756, 761, 765, 800,
                864, 869, 936, 941, 1008, 1013, 1040, 1061, 1068, 1071, 1074,
                1079]
    cols = 8
    th, tw = 180, 320
    rows = (len(reel_ids) + cols - 1) // cols
    canvas = np.full((rows * th, cols * tw, 3), 30, np.uint8)
    for k, f in enumerate(reel_ids):
        im = cv2.resize(cv2.imread(os.path.join(OUT, f"f{f:04d}.png")),
                        (tw, th), interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"f{f}", (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 200, 255), 1)
        canvas[(k // cols) * th:(k // cols) * th + th,
               (k % cols) * tw:(k % cols) * tw + tw] = im
    cv2.imwrite(os.path.join(OUT, "reel_fase4.png"), canvas)

    print(f"[ok] {n_frames} frames -> {OUT}/")
    print(f"[ok] fases: S1 0-{S1_END} | S2 {S1_END+1}-{NF-1} | corte f{NF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
