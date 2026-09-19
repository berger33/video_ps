#!/usr/bin/env python3
"""FASE 4 — build completo 0:00–0:45 (1080 frames @ 24fps).

Estrutura (docs/fase4-build.md):
  S1  f0–257    plano documental — caminhada (janela w160_235, 4 jump-cuts)
  S2  f258–1079 forrageio contínuo (janela w370_442 estabilizada em f406)
                — cadeia de ciclos de caminhada (src 370–399 + 412–441,
                taxas 0,96–1,03) com 6 bicadas reais cravadas na grade
                da trilha: 288, 400, 480, 576, 744, 1068.

Compostos persistentes na geometria f406 (referencial comum):
  migalhas A/B/C/D (mecanismo F2: hop, rachadura, nascimento por oclusão)
  minipombos 1–4 (nascem das carapaças B/C/D/B; B sela em f780–800 e
  reabre em f1008–1017 — leitura casulo aprovada no gate)

Regra de ouro respeitada: nada entra por escala/opacidade a partir do
vazio — todo nascimento é oclusão (conteúdo renderizado desde antes,
coberto pela carapaça fechada, revelado pela abertura animada).

Saidas: assets/out/fase4/{frames_1280x720,faz2_zoom,layers}/,
fase4_full.mp4, fase4_zoom.mp4, reel_fase4.png, evento.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose_fase2 as C  # noqa: E402

ROOT = C.ROOT
OUT = os.path.join(ROOT, "assets", "out", "fase4")
STAB_PECK = C.STAB                                  # w370_442/stab
STAB_WALK = os.path.join(ROOT, "assets", "plates", "w160_235", "stab")
FW, FH = C.FW, C.FH
NF = 1080                                           # 45,000 s x 24 fps
S1_END = 257                                        # S1 = 0..257
CUT = 1080

# ----------------------------- trilha (grade F3) ---------------------------
PECKS = [288, 400, 480, 576, 744, 1068]             # bico toca o chao

# ----------------------------- LUT (quadro filme -> quadro clipe) ----------
WALK_CYCLE = list(range(370, 400)) + list(range(412, 442))   # 60f sem bicada
PECK_SRC = list(range(393, 412))                    # 19f, contato no idx 7
WALK_RATES = (1.0, 0.97, 1.03, 0.98, 1.02, 0.96)    # variacao por ciclo


def build_lut() -> dict[int, tuple[str, int]]:
    lut: dict[int, tuple[str, int]] = {}
    # S1: caminhada (w160_235 = s160..s234, 75f) — 3 loops + cauda de 33f
    for f in range(0, S1_END + 1):
        src = 160 + (f % 75) if f < 225 else 160 + (f - 225)
        lut[f] = ("walk", src)
    # S2: caminhadas (ciclo de 60f, taxa variando) + pedacos de bicada
    pos, wp, cyc = S1_END + 1, 0.0, 0
    for target in PECKS:
        fill_end = target - 7                       # bicada comeca 7f antes
        while pos < fill_end:
            r = WALK_RATES[cyc % len(WALK_RATES)]
            lut[pos] = ("peckwin", WALK_CYCLE[int(wp) % len(WALK_CYCLE)])
            pos += 1
            wp += r
            if int(wp) >= len(WALK_CYCLE):
                wp -= len(WALK_CYCLE)
                cyc += 1
        for i, s in enumerate(PECK_SRC):
            lut[target - 7 + i] = ("peckwin", s)
        pos = target + 12
    assert pos == NF, f"LUT fechou em {pos} != {NF}"
    return lut


# ----------------------------- compostos (estado) --------------------------
MIGALHA = os.path.join(C.SPR, "migalha_rgba.png")
MINIPOMBO = os.path.join(C.SPR, "minipombo_rgba.png")
BIRD_W = 966.0                                      # largura do canvas sprite

MIG = {
    "A": {"born": 258, "pos": (452.0, 621.0), "scale": C.SCALE_A,
          "slide": (258, 259, 0.0, 0.0), "phase": 0.0,
          "hops": [288, 400, 480, 483, 576, 1068]},
    "B": {"born": 412, "pos": C.POS_B, "scale": C.SCALE_B,
          "slide": (412, 421, 40.0, 0.0), "phase": 9.0, "hops": []},
    "C": {"born": 492, "pos": C.POS_A, "scale": C.SCALE_A * 0.62,
          "slide": (492, 501, -32.0, 3.0), "phase": 3.0, "hops": []},
    "D": {"born": 501, "pos": C.POS_A, "scale": C.SCALE_A * 0.55,
          "slide": (501, 510, 88.0, -5.0), "phase": 13.0, "hops": []},
}

# rachadura por keyframes (t, abertura px, rot graus) — interpolacao suave;
# B SELA em 780–800 (leitura casulo) e reabre em 1008–1017 (MP#4)
KEYF = {
    "A": [(412, 0.0, 0.0), (421, 8.0, 6.0), (492, 8.0, 6.0),
          (510, 12.0, 8.0), (1008, 12.0, 8.0), (1017, 14.0, 9.0)],
    "B": [(756, 0.0, 0.0), (765, 8.0, 8.0), (780, 8.0, 8.0),
          (800, 0.0, 0.0), (1008, 0.0, 0.0), (1017, 8.0, 8.0)],
    "C": [(864, 0.0, 0.0), (873, 8.0, 8.0)],
    "D": [(936, 0.0, 0.0), (945, 8.0, 8.0)],
}

BIRD = {   # shell, largura px, reveal, caminhada (t0,t1), estacao final
    "1": {"shell": "B", "w_px": 22.0, "reveal": (756, 765),
          "walk": (780, 810), "station": (508.0, 618.0)},
    "2": {"shell": "C", "w_px": 21.0, "reveal": (864, 873),
          "walk": (884, 940), "station": (536.0, 620.0)},
    "3": {"shell": "D", "w_px": 18.0, "reveal": (936, 945),
          "walk": (956, 1010), "station": (596.0, 613.0)},
    "4": {"shell": "B", "w_px": 22.0, "reveal": (1008, 1017),
          "walk": (1028, 1058), "station": (560.0, 622.0)},
}

# (periodo, amp graus, fase, rot_base) — unicos por bird (regra offset de tempo)
BIRD_SWOB = {
    "1": (15.0, 2.2, 2.1, 0.0),
    "2": (17.0, 1.6, 4.3, -3.0),
    "3": (19.0, 2.8, 1.0, 2.5),
    "4": (13.0, 1.9, 6.2, -2.0),
}
BIRD_DIPS = {"1": [900, 972, 1068], "2": [948, 1014, 1070],
             "3": [990, 1044, 1072], "4": [1032, 1074]}   # coletiva 0/2/4/6f

SAMPLES = [258, 288, 300, 400, 412, 416, 421, 435, 480, 492, 496, 505, 510,
           576, 744, 752, 756, 757, 758, 760, 765, 800, 864, 865, 866, 868,
           873, 936, 937, 938, 940, 945, 1008, 1009, 1010, 1012, 1017, 1032,
           1061, 1068, 1071, 1074, 1079]

ZOOM = (520, 700, 240, 760)                         # y0,y1,x0,x1 (2,4x)


# ----------------------------- helpers -------------------------------------
def cut_halves_opaco(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Metades com feather UNILATERAL: no estado fechado o fecho das duas
    reconstrui a silhueta 100% opaca (sem emenda translucida) — a carapaça
    fechada oculta o minipombo por completo."""
    h, w = rgba.shape[:2]
    xs = [int(x * (w - 1)) for x in (0.513, 0.490, 0.524, 0.502)]
    ys = [int(y * (h - 1)) for y in (0.0, 0.321, 0.688, 1.0)]
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
    s = sign * d                                    # >0 = lado direito
    m_left = np.clip(1.0 - np.maximum(s, 0.0) / feather, 0, 1)
    m_right = np.clip(1.0 - np.maximum(-s, 0.0) / feather, 0, 1)
    left, right = rgba.copy(), rgba.copy()
    left[:, :, 3] *= m_left.astype(np.float32)
    right[:, :, 3] *= m_right.astype(np.float32)
    return left, right


def crack_state(name: str, t: int) -> tuple[float, float]:
    kf = KEYF[name]
    if t < kf[0][0]:
        return 0.0, 0.0
    for i in range(len(kf) - 1):
        (ta, ga, ra), (tb, gb, rb) = kf[i], kf[i + 1]
        if ta <= t < tb:
            u = C.ease((t - ta) / float(tb - ta))
            return ga + (gb - ga) * u, ra + (rb - ra) * u
    return kf[-1][1], kf[-1][2]


def hop_dy(t: int, h0: int) -> tuple[float, tuple[float, float]]:
    """Arco do salto (14px em 9f) + quique (4px em 3f); squash no impacto."""
    if h0 <= t < h0 + 9:
        u = (t - h0) / 9.0
        return -14.0 * 4 * u * (1 - u), (1.06, 0.90) if t == h0 else (1.0, 1.0)
    if h0 + 9 <= t < h0 + 12:
        u = (t - h0 - 9) / 3.0
        return -4.0 * 4 * u * (1 - u), (1.09, 0.86) if t == h0 + 9 else (1.0, 1.0)
    return 0.0, (1.0, 1.0)


def migalha_ev(t: int, name: str) -> dict | None:
    m = MIG[name]
    if t < m["born"]:
        return None
    s0, s1, sdx, sdy = m["slide"]
    p = C.ease((t - s0) / float(s1 - s0)) if t >= s0 else 0.0
    x = m["pos"][0] + sdx * p
    y = m["pos"][1] + sdy * p
    gap, crot = crack_state(name, t)
    wob = C.WOB_AMP * np.sin(2 * np.pi * t / C.WOB_T + m["phase"])
    dy, squash = 0.0, (1.0, 1.0)
    for h0 in m["hops"]:                            # salto duplo 480/483:
        d2, s2 = hop_dy(t, h0)                      # vence o mais fundo
        if d2 < dy:
            dy = d2
        if s2 != (1.0, 1.0):
            squash = s2
    return {"name": name, "kind": "mig", "pos": (x, y), "scale": m["scale"],
            "gap": gap, "rot": round(wob, 3), "rot0": crot,
            "squash": squash, "dy": round(dy, 2), "born": m["born"]}


def bird_ev(t: int, bn: str) -> dict | None:
    b = BIRD[bn]
    r0, r1 = b["reveal"]
    if t < r0:
        return None
    m = MIG[b["shell"]]
    s0, s1, sdx, sdy = m["slide"]
    p = C.ease((t - s0) / float(s1 - s0)) if t >= s0 else 0.0
    bx, by = m["pos"][0] + sdx * p, m["pos"][1] + sdy * p
    rise = 10.0 * (1.0 - C.ease((t - r0 - 2) / 18.0)) if t > r0 + 2 else 10.0
    w0, w1 = b["walk"]
    pw = C.ease((t - w0) / float(w1 - w0))
    x = bx + (b["station"][0] - bx) * pw
    y = by + (b["station"][1] - by) * pw
    bob = 1.0 * np.sin(2 * np.pi * t / (11.0 + int(bn)) + float(bn))
    squash, ddy, drot = (1.0, 1.0), 0.0, 0.0
    for d in BIRD_DIPS[bn]:
        if d <= t < d + 4:
            k = t - d
            squash = (1.0, (0.90, 0.84, 0.90, 1.0)[k])
            ddy = (2.0, 3.0, 1.0, 0.0)[k]
            drot = (-5.0, -7.0, -3.0, 0.0)[k]
    T, amp, ph, base = BIRD_SWOB[bn]
    swob = base + amp * np.sin(2 * np.pi * (t - r1) / T + ph)
    return {"name": bn, "kind": "bird", "shell": b["shell"], "pos": (x, y),
            "w_px": b["w_px"], "rot": round(swob + drot, 3),
            "squash": squash, "dy": round(bob + ddy, 2),
            "rise": 0.0, "born": r0}


# ----------------------------- sprites carregados 1x -----------------------
_MIG = C.grade(C.load_rgba(MIGALHA), C.GRADE)
HALVES = cut_halves_opaco(_MIG)
BIRD_SPR = C.grade(C.load_rgba(MINIPOMBO), C.GRADE)
MIG_W = float(_MIG.shape[1])


def load_assets() -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray],
                           np.ndarray]:
    return _MIG, HALVES, BIRD_SPR


# ----------------------------- render --------------------------------------
def canvases_of(evs: list[dict], halves, bird) -> list[tuple[dict, np.ndarray, tuple, str]]:
    objs = []
    for ev in evs:
        if ev["kind"] == "mig":
            cL, pvL = C.render_object(halves[0], ev["scale"],
                                      ev["rot"] - ev["rot0"], ev["squash"])
            cR, pvR = C.render_object(halves[1], ev["scale"],
                                      ev["rot"] + ev["rot0"], ev["squash"])
            objs.append((ev, cL, pvL, f"mig{ev['name']}L"))
            objs.append((ev, cR, pvR, f"mig{ev['name']}R"))
        else:
            cb, pvb = C.render_object(bird, ev["w_px"] / BIRD_W,
                                      ev["rot"], ev["squash"])
            objs.append((ev, cb, pvb, f"bird{ev['name']}"))
    return objs


def anchor_of(ev: dict, tag: str) -> tuple[float, float]:
    ax, ay = ev["pos"]
    if tag.endswith("L"):
        ax -= ev["gap"] / 2
    if tag.endswith("R"):
        ax += ev["gap"] / 2
    return ax, ay


def main() -> int:
    for d in ("frames_1280x720", "faz2_zoom", "layers"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    mig, halves, bird = load_assets()
    lut = build_lut()

    # compressao do LUT p/ documentacao
    segs, t = [], 0
    while t < NF:
        o, s = lut[t]
        t2 = t
        while t2 + 1 < NF:
            o2, s2 = lut[t2 + 1]
            if o2 != o or (o == "peckwin" and s2 != s + (t2 + 1 - t)):
                break
            t2 += 1
        segs.append([t, t2, o, s, lut[t2][1]])
        t = t2 + 1

    opens = [("migalha_A_abre1", 412, 421), ("migalha_A_abre2", 492, 510),
             ("migalha_B_abre1", 756, 765), ("migalha_B_abre2", 1008, 1017),
             ("migalha_C_abre", 864, 873), ("migalha_D_abre", 936, 945),
             ("minipombo_1", 756, 765), ("minipombo_2", 864, 873),
             ("minipombo_3", 936, 945), ("minipombo_4", 1008, 1017)]
    reveal_log = [{"evento": n, "f0": a, "f1": b, "frames": b - a}
                  for (n, a, b) in opens]

    for t in range(NF):
        o, s = lut[t]
        path = os.path.join(STAB_WALK if o == "walk" else STAB_PECK, f"s{s}.png")
        frame = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB).astype(np.float32)

        if t <= S1_END:
            img = frame.astype(np.uint8)
        else:
            evs = [e for e in (migalha_ev(t, n) for n in ("A", "B", "C", "D")) if e]
            evs += [e for e in (bird_ev(t, n) for n in ("1", "2", "3", "4")) if e]
            objs = canvases_of(evs, halves, bird)

            # sombras (mais distante primeiro; plano alfa por objeto)
            for ev in sorted(evs, key=lambda e: e["pos"][1]):
                plane = np.zeros((FH, FW), np.float32)
                for (ev2, c, pv, tag) in objs:
                    base = ("mig" + ev["name"]) if ev["kind"] == "mig" else ("bird" + ev["name"])
                    if not tag.startswith(base):
                        continue
                    C.paste_canvas(plane, c, pv, anchor_of(ev, tag),
                                   ev["dy"], alpha_only=True)
                if ev["kind"] == "mig":
                    size = sum(c.shape[1] for (e2, c, pv, tg) in objs
                               if tg.startswith("mig" + ev["name"])) - 40
                else:
                    size = next(c.shape[1] for (e2, c, pv, tg) in objs
                                if tg == "bird" + ev["name"])
                C.draw_shadow(frame, plane, ev["pos"], ev["dy"], C.SHADOW, size)

            # composicao (z: y asc; bird antes da migalha no mesmo y)
            out = np.clip(frame, 0, 255).astype(np.uint8)
            order = sorted(range(len(evs)),
                           key=lambda i: (evs[i]["pos"][1], evs[i]["kind"] == "mig"))
            for i in order:
                ev = evs[i]
                for (ev2, c, pv, tag) in objs:
                    base = ("mig" + ev["name"]) if ev["kind"] == "mig" else ("bird" + ev["name"])
                    if not tag.startswith(base):
                        continue
                    C.paste_canvas(out, c, pv, anchor_of(ev, tag), ev["dy"])

            if t in SAMPLES:
                meta = {"migas": {}, "birds": {}}
                for ev in evs:
                    grp = "migas" if ev["kind"] == "mig" else "birds"
                    meta[grp][ev["name"]] = ev
                for (ev, c, pv, tag) in objs:
                    a = c[:, :, 3]
                    rows = np.any(a > 8, axis=1)
                    cols = np.any(a > 8, axis=0)
                    y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
                    x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
                    crop = c[y0:y1 + 1, x0:x1 + 1]
                    cv2.imwrite(os.path.join(OUT, "layers", f"f{t}_{tag}.png"),
                                cv2.cvtColor(crop.astype(np.uint8),
                                             cv2.COLOR_RGBA2BGRA))
                with open(os.path.join(OUT, "layers", f"f{t}_meta.json"), "w") as fh:
                    json.dump(meta, fh, default=float)
            img = out

        cv2.imwrite(os.path.join(OUT, "frames_1280x720", f"f{t:04d}.png"),
                    cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        zy0, zy1, zx0, zx1 = ZOOM
        z = cv2.resize(img[zy0:zy1, zx0:zx1], (1152, 432),
                       interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(os.path.join(OUT, "faz2_zoom", f"z{t:04d}.png"),
                    cv2.cvtColor(z, cv2.COLOR_RGB2BGR))
        if t % 120 == 0:
            print(f"[f4] frame {t}/{NF}", flush=True)

    # ----------------------------- mp4 + reel ------------------------------
    for dirname, pat, name in (("frames_1280x720", "f%04d.png", "fase4_full.mp4"),
                               ("faz2_zoom", "z%04d.png", "fase4_zoom.mp4")):
        subprocess.run([C.FFMPEG, "-y", "-framerate", "24",
                        "-i", os.path.join(OUT, dirname, pat),
                        "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
                        os.path.join(OUT, name)], check=True,
                       capture_output=True)

    keys = [0, 130, 257, 258, 288, 300, 400, 412, 417, 421, 480, 492, 505,
            576, 744, 756, 765, 800, 864, 936, 1008, 1032, 1068, 1079]
    tiles = []
    for k in keys:
        im = cv2.imread(os.path.join(OUT, "frames_1280x720", f"f{k:04d}.png"))
        tiles.append(cv2.resize(im, (480, 270)))
    rows = [np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    reel = np.vstack(rows)
    cv2.imwrite(os.path.join(OUT, "reel_fase4.png"), reel)

    with open(os.path.join(OUT, "evento.json"), "w") as fh:
        json.dump({"fps": 24, "frames": NF, "cut": CUT, "pecks": PECKS,
                   "S1_END": S1_END, "segs": segs, "reveacoes": reveal_log,
                   "migas": {k: {kk: vv for kk, vv in v.items()}
                             for k, v in MIG.items()},
                   "birds": BIRD, "bird_swob": BIRD_SWOB,
                   "dips": BIRD_DIPS, "zoom": ZOOM,
                   "grade": C.GRADE, "shadow": C.SHADOW,
                   "keyframes_rachadura": KEYF},
                  fh, indent=1, default=float, ensure_ascii=False)
    print(f"[ok] {NF} frames -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
