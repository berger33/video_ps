#!/usr/bin/env python3
"""FASE 2 — prototipo do mecanismo: 1 bicada -> 1 duplicacao de migalha.

Evento (janela estabilizada f370-442, 24 fps, referencial f406):
  f400   bico toca o chao (bicada #1, video real) -> migalha A leva o hit
  f400-412  salto curto de A (arco 14px + squash de pouso + quique 4px)
  f412-421 OCLUSAO: A racha (duas metades se abrem 8px, rot +6/-6 em torno da
           ancora no chao) e a migalha B (mesma origem, escala 0.88 = mais
           distante, rot +10, fase de wobble defasada 9f) emerge de dentro de
           A por atras das metades e desliza 40px para a direita.
           Reveal = 10 frames (>= 8). B e 100% ocluida por A ate a abertura
           (verificado e logado em evento.json).
  f421-441  as duas migalhas em repouso, cada uma com wobble em fase propria
           (nunca pose identica simultanea), sombra de contato propria.

Tecnicas obrigatorias implementadas:
  - oclusao: B NUNCA anima escala/opacidade (anti-pop verificado em
    verify_fase2.py); a revelacao e feita por atras da mascara das metades
  - offset de tempo: cada copia amostra o "clipe de origem" (animacao
    sintetizada do objeto: wobble) em fase defasada + escala/rotacao proprias
  - cor: ganho por canal medido do plate (ponto branco da cena vs estudio)
  - sombra: darkening multiplicativo do chao real (luz difusa; delta medido
    ~16,5 lum sob as patas do pombo)
  - profundidade: B mais alta no quadro (mais distante) e menor (0.65x)

Saidas (assets/out/fase2/):
  frames_1280x720/    compositedo completo
  faz2_zoom/          crop 2.4x da regiao do evento (legibilidade)
  fase2_full.mp4      72f @ 24fps 1280x720
  fase2_zoom.mp4      72f @ 24fps 864x504
  layers/             layers por objeto nos frames de amostra (p/ verify)
  evento.json         timeline + cobertura + grade (p/ verify e p/ Fase 3)

Uso: tools/venv/bin/python tools/compose_fase2.py
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAB = os.path.join(ROOT, "assets", "plates", "w370_442", "stab")
SPR = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "assets", "out", "fase2")

# ----------------------------- timeline (frames globais) -------------------
T0, T1 = 370, 441
HIT = 400                      # bicada visual (bico toca o chao)
HOP_T0, HOP_T1 = 400, 409      # arco principal (apex ~f404)
HOP_H = 14.0                   # px
BOUNCE_T0, BOUNCE_T1 = 409, 412
BOUNCE_H = 4.0
OPEN_T0, OPEN_T1 = 412, 421    # revelacao por oclusao (10 frames)
OPEN_GAP = 8.0                 # px de abertura final da rachadura
OPEN_ROT = 6.0                 # graus de rotacao de cada metade
SLIDE = 40.0                   # px de deslocamento de B na abertura

# ----------------------------- posicoes (coords. do quadro) ----------------
POS_A = (452.0, 621.0)         # migalha original, sob a ponta do bico
POS_B = (452.0, 619.0)         # B nasce DENTRO da carapaca de A (100% ocluida; tune_occlusion.py: POS_A+(0,-2), sprite regen)
SCALE_A = 40.0 / 582.0         # migalha ~40px de largura na cena (sprite 582px, regen F1bis)
SCALE_B = SCALE_A * 0.68       # B mais distante -> menor (tecnica 6; tune_occlusion.py, sprite regen)
ROT_B = 8.0                    # rotacao constante de B (diferente da de A)

# wobble: o "clipe de origem" da migalha (rotacao lenta sinusoidal)
WOB_T = 18.0                   # periodo (frames)
WOB_AMP = 1.8                  # graus
WOB_PHASE_A = 0.0
WOB_PHASE_B = 9.0              # defasagem: meio periodo (nunca em fase)

# ----------------------------- cor/sombra (medidos do plate) ---------------
# f406: chao claro BGR (171.6,179.8,185.8), lum 180,7; estudio branc BGR
# (248.7,249.3,248.6). Ganho = (ponto branco da cena / do estudio) x exposicao
# 0,97 (nivel de luz da cena ~= estudio) + saturacao 0,93 (luz difusa).
GRADE = {"B": 0.97 * 0.958, "G": 0.97 * 1.004, "R": 0.97 * 1.038, "sat": 0.93}
SHADOW = {
    "off": (3.0, 5.0),     # direcao da sombra (luz difusa: quase reta p/ baixo)
    "k_soft": 0.22,        # darkening difuso (cena tem delta ~16 sob o pombo)
    "sigma_soft": 4.5,
    "k_core": 0.38,        # nucleo de contato
    "sigma_core": 1.8,
}
SS = 2  # supersampling
FW, FH = 1280, 720
FFMPEG = os.path.join(ROOT, "tools", "bin", "ffmpeg")


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ----------------------------- sprites --------------------------------------
def load_rgba(path: str) -> np.ndarray:
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32)


def grade(rgba: np.ndarray, cfg: dict) -> np.ndarray:
    g = np.array([cfg["R"], cfg["G"], cfg["B"]], np.float32)
    out = rgba.copy()
    rgb = out[:, :, :3] * g
    mean = rgb.mean(axis=2, keepdims=True)
    out[:, :, :3] = np.clip(mean + (rgb - mean) * cfg["sat"], 0, 255)
    return out


def crack_mask(w: int, h: int, xs: list[int], ys: list[int], side: int,
               feather: float = 2.0) -> np.ndarray:
    """Mascara de cada metade ao longo de uma rachadura serrilhada."""
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
    s = sign * d
    return np.clip((s * side + feather) / (2 * feather), 0, 1).astype(np.float32)


def cut_halves(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Divide a migalha em duas metades em canvas de TAMANHO INTEIRO (mesmo
    referencial local) — o fecho das duas reconstrui a silhueta original.
    A rachadura e definida em coords. normalizadas (0-1) e escala ao canvas
    do sprite atual (a rachadura original foi desenhada p/ 653x436)."""
    h, w = rgba.shape[:2]
    xn, yn = [0.513, 0.490, 0.524, 0.502], [0.0, 0.321, 0.688, 1.0]
    xs = [int(x * (w - 1)) for x in xn]
    ys = [int(y * (h - 1)) for y in yn]
    left = rgba.copy()
    right = rgba.copy()
    left[:, :, 3] *= crack_mask(w, h, xs, ys, -1)
    right[:, :, 3] *= crack_mask(w, h, xs, ys, +1)
    return left, right


# ----------------------------- renderizacao --------------------------------
def render_object(sprite: np.ndarray, scale: float, rot_deg: float,
                  squash: tuple[float, float], ss: int = SS):
    """Canvas com padding; rotacao em torno do pivot = centro-inferior do
    sprite (ponto de contato com o chao). Retorna (canvas, pivot)."""
    h, w = sprite.shape[:2]
    sw, sh = max(2, int(round(w * scale * ss))), max(2, int(round(h * scale * ss)))
    im = cv2.resize(sprite, (sw, sh), interpolation=cv2.INTER_AREA)
    px, py = sw / 2.0, sh
    rad = np.deg2rad(rot_deg)
    c, s = np.cos(rad), np.sin(rad)
    corners = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], np.float64)
    tc = (corners - [px, py]) @ np.array([[c, s], [-s, c]]) + [px, py]
    x0, y0 = tc.min(axis=0)
    x1, y1 = tc.max(axis=0)
    rw, rh = int(np.ceil(x1 - x0)) + 2, int(np.ceil(y1 - y0)) + 2
    M = np.float32([[c, -s, px - c * px + s * py - x0 + 1],
                    [s, c, py - s * px - c * py - y0 + 1]])
    out = cv2.warpAffine(im, M, (rw, rh), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    pvx, pvy = px - x0 + 1, py - y0 + 1
    if abs(squash[0] - 1) > 1e-3 or abs(squash[1] - 1) > 1e-3:
        out = cv2.resize(out, (max(2, int(round(rw * squash[0]))),
                               max(2, int(round(rh * squash[1])))),
                         interpolation=cv2.INTER_AREA)
        pvx, pvy = pvx * squash[0], pvy * squash[1]
        rw, rh = out.shape[1], out.shape[0]
    out = cv2.resize(out, (max(2, int(round(rw / ss))),
                           max(2, int(round(rh / ss)))),
                     interpolation=cv2.INTER_AREA)
    return out, (pvx / ss, pvy / ss)


def paste_canvas(dst: np.ndarray, canvas: np.ndarray, pivot, anchor,
                 dy: float = 0.0, alpha_only: bool = False) -> None:
    """Cola canvas em dst: pivot cai no (anchor + dy). dst = frame RGB/float
    ou plano de alfa (alpha_only)."""
    ax, ay = anchor
    x0 = int(round(ax - pivot[0]))
    y0 = int(round(ay + dy - pivot[1]))
    h, w = canvas.shape[:2]
    x1, y1 = x0 + w, y0 + h
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(dst.shape[1], x1), min(dst.shape[0], y1)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    cs = canvas[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    if alpha_only:
        dst[fy0:fy1, fx0:fx1] = np.maximum(dst[fy0:fy1, fx0:fx1],
                                           cs[:, :, 3] / 255.0)
    else:
        sub = dst[fy0:fy1, fx0:fx1].astype(np.float32)
        a = cs[:, :, 3:4] / 255.0
        dst[fy0:fy1, fx0:fx1] = (sub * (1 - a) + cs[:, :, :3] * a)


def draw_shadow(frame: np.ndarray, a_plane: np.ndarray, anchor, dy: float,
                cfg: dict, obj_size: float) -> None:
    """Sombra = darkening multiplicativo do chao real. Nucleo de contato +
    difusa (amplia/enfraquece com a altura). O objeto levanta (dy<0); a
    sombra fica no chao."""
    lift = max(0.0, -dy)
    dx, dys = cfg["off"]
    ax, ay = anchor
    r = int(obj_size * (1.5 + lift / 14.0)) + 12
    wx0, wy0 = max(0, int(ax - r)), max(0, int(ay - int(obj_size * 0.5)))
    wx1, wy1 = min(FW, int(ax + r)), min(FH, int(ay + r))
    if wx1 <= wx0 or wy1 <= wy0:
        return
    sub_a = a_plane[wy0:wy1, wx0:wx1]
    if sub_a.max() < 1 / 255.0:
        return
    soft = cv2.GaussianBlur(sub_a, (0, 0),
                            cfg["sigma_soft"] * (1 + lift / 9.0))
    grow = 1 + lift / 20.0
    soft = cv2.resize(soft, (max(2, int(soft.shape[1] * grow)),
                             max(2, int(soft.shape[0] * grow))))
    # centraliza o soft (cresceu) em torno do centro da janela
    cy0 = (sub_a.shape[0] - soft.shape[0]) // 2
    cx0 = (sub_a.shape[1] - soft.shape[1]) // 2
    full_soft = np.zeros_like(sub_a)
    yA, yB = max(0, cy0), min(sub_a.shape[0], cy0 + soft.shape[0])
    xA, xB = max(0, cx0), min(sub_a.shape[1], cx0 + soft.shape[1])
    full_soft[yA:yB, xA:xB] = soft[yA - cy0:yB - cy0, xA - cx0:xB - cx0]
    core = sub_a.copy()
    core[:int(core.shape[0] * 0.72), :] = 0.0
    core = cv2.GaussianBlur(core, (0, 0), cfg["sigma_core"])
    k_soft = cfg["k_soft"] * max(0.15, 1 - lift / 16.0)
    k_core = cfg["k_core"] * max(0.15, 1 - lift / 12.0)
    sh = cv2.warpAffine(full_soft,
                        np.float32([[1, 0, dx * (1 + lift / 14.0)],
                                    [0, 1, dys * (1 + lift / 14.0)]]),
                        full_soft.shape[:2][::-1], borderValue=0.0)
    cr = cv2.warpAffine(core, np.float32([[1, 0, dx], [0, 1, dys]]),
                        core.shape[:2][::-1], borderValue=0.0)
    sub_f = frame[wy0:wy1, wx0:wx1].astype(np.float32)
    sub_f *= (1 - k_soft * sh[:, :, None])
    sub_f *= (1 - k_core * cr[:, :, None])
    frame[wy0:wy1, wx0:wx1] = np.clip(sub_f, 0, 255)


def union_canvas(c1, pv1, off1, c2, pv2, off2):
    """Junta dois canvas (ex.: metades de A) em um canvas local; o ancora
    (contato no chao) fica em (W/2, H-1). off = deslocamento extra de cada
    metade (gap da rachadura)."""
    W = int(max(pv1[0] + c1.shape[1] - pv1[0] + max(0.0, off1[0]),
                pv2[0] + c2.shape[1] - pv2[0] + max(0.0, off2[0]),
                pv1[0] + c1.shape[1] - pv1[0] + max(0.0, off2[0]),
                pv2[0] + c2.shape[1] - pv2[0] + max(0.0, off1[0]),
                c1.shape[1], c2.shape[1])) + 4
    H = int(max(c1.shape[0], c2.shape[0]) + max(0.0, off1[1], off2[1])) + 4
    canvas = np.zeros((H, W, 4), np.float32)
    for c, pv, off in ((c1, pv1, off1), (c2, pv2, off2)):
        x0 = int(round(W / 2 + off[0] - pv[0]))
        y0 = int(round(H - 1 + off[1] - pv[1]))
        x1, y1 = x0 + c.shape[1], y0 + c.shape[0]
        fx0, fy0 = max(0, x0), max(0, y0)
        fx1, fy1 = min(W, x1), min(H, y1)
        if fx1 <= fx0 or fy1 <= fy0:
            continue
        cs = c[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
        sub = canvas[fy0:fy1, fx0:fx1]
        a = cs[:, :, 3:4] / 255.0
        canvas[fy0:fy1, fx0:fx1] = sub * (1 - a) + cs * a
    a = canvas[:, :, 3]
    rows = np.any(a > 8, axis=1)
    cols = np.any(a > 8, axis=0)
    if not rows.any():
        return canvas
    y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
    x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
    return canvas[y0:y1 + 1, x0:x1 + 1]


# ----------------------------- evento --------------------------------------
def timeline(t: int) -> dict:
    if HOP_T0 <= t <= HOP_T1:
        u = (t - HOP_T0) / (HOP_T1 - HOP_T0)
        dy = -HOP_H * 4 * u * (1 - u)
    elif BOUNCE_T0 < t <= BOUNCE_T1:
        u = (t - BOUNCE_T0) / (BOUNCE_T1 - BOUNCE_T0)
        dy = -BOUNCE_H * 4 * u * (1 - u)
    else:
        dy = 0.0
    squash = (1.0, 1.0)
    if t == HIT:
        squash = (1.06, 0.90)
    elif t == HOP_T1:
        squash = (1.09, 0.86)
    p = ease((t - OPEN_T0) / (OPEN_T1 - OPEN_T0)) if t > OPEN_T0 else 0.0
    return {
        "A_dy": dy, "A_squash": squash,
        "gap": OPEN_GAP * p, "open_rot": OPEN_ROT * p, "B_dx": SLIDE * p,
        "wob_A": WOB_AMP * np.sin(2 * np.pi * (t - T0) / WOB_T + WOB_PHASE_A),
        "wob_B": WOB_AMP * np.sin(2 * np.pi * (t - T0) / WOB_T + WOB_PHASE_B),
    }


def main() -> int:
    for d in ("frames_1280x720", "faz2_zoom", "layers"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    mig = grade(load_rgba(os.path.join(SPR, "migalha_rgba.png")), GRADE)
    half_L, half_R = cut_halves(mig)

    samples = [380, 390, 398, 405, 411, 414, 417, 420, 421, 425, 430, 435, 440]
    coverage_log: dict[int, float] = {}
    aA = np.zeros((FH, FW), np.float32)
    aB = np.zeros((FH, FW), np.float32)

    for t in range(T0, T1 + 1):
        frame = cv2.cvtColor(cv2.imread(os.path.join(STAB, f"s{t}.png")),
                              cv2.COLOR_BGR2RGB).astype(np.float32)
        ev = timeline(t)

        # ---------------- objetos (render 2x SSAA) ----------------
        c_L, pv_L = render_object(half_L, SCALE_A,
                                  ev["wob_A"] - ev["open_rot"], ev["A_squash"])
        c_R, pv_R = render_object(half_R, SCALE_A,
                                  ev["wob_A"] + ev["open_rot"], ev["A_squash"])
        c_B, pv_B = render_object(mig, SCALE_B, ROT_B + ev["wob_B"], (1, 1))

        axA = POS_A
        axB = (POS_B[0] + ev["B_dx"], POS_B[1])
        offL = (-ev["gap"] / 2, 0.0)
        offR = (ev["gap"] / 2, 0.0)
        axAL = (POS_A[0] + offL[0], POS_A[1])
        axAR = (POS_A[0] + offR[0], POS_A[1])

        # ---------------- planos de alfa (espaco do mundo) --------------
        aA[:] = 0.0
        aB[:] = 0.0
        paste_canvas(aA, c_L, pv_L, axAL, ev["A_dy"], alpha_only=True)
        paste_canvas(aA, c_R, pv_R, axAR, ev["A_dy"], alpha_only=True)
        # B esta DENTRO da carapaca de A: move-se junto (dy de A)
        paste_canvas(aB, c_B, pv_B, axB, ev["A_dy"], alpha_only=True)

        # cobertura de B por A enquanto fechado (anti-pop: B nao pode vazar)
        if t <= OPEN_T0:
            visB = aB > 20 / 255.0
            if visB.sum() > 0:
                coverage_log[t] = round(
                    float(np.logical_and(visB, aA > 20 / 255.0).sum()
                          / visB.sum()), 4)

        # ---------------- sombras (distante primeiro) -------------------
        draw_shadow(frame, aB, axB, ev["A_dy"], SHADOW, c_B.shape[1])
        draw_shadow(frame, aA, POS_A, ev["A_dy"], SHADOW, c_L.shape[1] + c_R.shape[1] - 40)

        # ---------------- composicao (z: B atras, A na frente) ----------
        out = np.clip(frame, 0, 255).astype(np.uint8)
        paste_canvas(out, c_B, pv_B, axB, ev["A_dy"])
        paste_canvas(out, c_L, pv_L, axAL, ev["A_dy"])
        paste_canvas(out, c_R, pv_R, axAR, ev["A_dy"])

        # ---------------- dump p/ verificacao ----------------
        if t in samples:
            canvasA = union_canvas(c_L, pv_L, offL, c_R, pv_R, offR)
            cv2.imwrite(os.path.join(OUT, "layers", f"f{t}_A.png"),
                        cv2.cvtColor(canvasA.astype(np.uint8),
                                     cv2.COLOR_RGBA2BGRA))
            a = c_B[:, :, 3]
            rows = np.any(a > 8, axis=1)
            cols = np.any(a > 8, axis=0)
            y0, y1 = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
            x0, x1 = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
            cropB = c_B[y0:y1 + 1, x0:x1 + 1]
            cv2.imwrite(os.path.join(OUT, "layers", f"f{t}_B.png"),
                        cv2.cvtColor(cropB.astype(np.uint8),
                                     cv2.COLOR_RGBA2BGRA))
            with open(os.path.join(OUT, "layers", f"f{t}_meta.json"), "w") as fh:
                json.dump({
                    "t": t,
                    "A": {"rot": round(ev["wob_A"] - ev["open_rot"], 2),
                          "scale": SCALE_A, "wob_phase": WOB_PHASE_A,
                          "pos": list(POS_A), "dy": ev["A_dy"],
                          "gap": ev["gap"], "open_rot": ev["open_rot"]},
                    "B": {"rot": round(ROT_B + ev["wob_B"], 2),
                          "scale": SCALE_B, "wob_phase": WOB_PHASE_B,
                          "pos": list(axB),
                          "alpha_mean_own": float(c_B[c_B[:, :, 3] > 20, 3].mean()),
                          "alpha_max": float(c_B[:, :, 3].max())},
                }, fh, indent=1)

        cv2.imwrite(os.path.join(OUT, "frames_1280x720", f"f{t}.png"),
                    cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        zoom = cv2.resize(out[500:700, 300:640], (864, 504),
                          interpolation=cv2.INTER_CUBIC)
        cv2.putText(zoom, f"f{t}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (255, 60, 40), 2)
        cv2.imwrite(os.path.join(OUT, "faz2_zoom", f"f{t}.png"),
                    cv2.cvtColor(zoom, cv2.COLOR_RGB2BGR))

    # ------------------------- videos + evento.json -----------------------
    os.system(f'{FFMPEG} -hide_banner -loglevel error -framerate 24 -start_number {T0} '
              f'-i {OUT}/frames_1280x720/f%03d.png -c:v libx264 -pix_fmt '
              f'yuv420p -crf 17 -movflags +faststart {OUT}/fase2_full.mp4 -y')
    os.system(f'{FFMPEG} -hide_banner -loglevel error -framerate 24 -start_number {T0} '
              f'-i {OUT}/faz2_zoom/f%03d.png -c:v libx264 -pix_fmt yuv420p '
              f'-crf 17 -movflags +faststart {OUT}/fase2_zoom.mp4 -y')

    evento = {
        "janela": [T0, T1], "fps": 24, "bicada_visual": HIT,
        "hit_migalha": HIT, "salto_apex": 404, "pouso": HOP_T1,
        "revelacao_inicio": OPEN_T0, "revelacao_fim": OPEN_T1,
        "revelacao_frames": OPEN_T1 - OPEN_T0,
        "ancoras_fase3": "bicada=kick | pouso=hit pequeno | "
                         "revelacao_inicio=transiente+atrito | fim=hit",
    }
    with open(os.path.join(OUT, "evento.json"), "w") as fh:
        json.dump({"evento": evento,
                   "cobertura_B_por_A": coverage_log,
                   "grade": GRADE, "sombra": SHADOW,
                   "posicoes": {"A": list(POS_A), "B_inicial": list(POS_B),
                                "B_final": [POS_B[0] + SLIDE, POS_B[1]],
                                "escala_A": SCALE_A, "escala_B": SCALE_B,
                                "rot_B": ROT_B,
                                "wob": {"T": WOB_T, "amp": WOB_AMP,
                                        "fase_A": WOB_PHASE_A,
                                        "fase_B": WOB_PHASE_B}}},
                  fh, indent=1, ensure_ascii=False)
    cov_min = min(coverage_log.values()) if coverage_log else 1.0
    print(f"[ok] {T1 - T0 + 1} frames -> assets/out/fase2/")
    print(f"[cobertura B por A, t<={OPEN_T0}] min={cov_min} (1.0 = 100% ocluida)")
    if cov_min < 0.98:
        print("[AVISO] B vazando antes da abertura — ajustar POS_B/escala")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
