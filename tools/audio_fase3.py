#!/usr/bin/env python3
"""FASE 3 — trilha diegetica do piloto (0:00-0:45) construida do proprio clipe.

CAMINHO DECIDIDO (documentado em docs/fase3-audio.md):
  Percussao 100% de samples do proprio ambiente:
    - bicada  = KICK   : clique real da bicada em 16,7656s (f402 no field)
    - passos  = WOODBLOCK: tiques de unhas das janelas de caminhada
    - unha    = HI-HAT : cliques isolados mais curtos do clipe
    - rachadura/revelacao = CRACK: tique de unha esticado + filtro
  Unico elemento sintetizado (nao existe no material, verificado por varredura
  tonal 80-800Hz): o ARRULHO GRAVE = baixo, desenhado para casar com a banda
  grave do ambiente (100-400Hz dominante do espectro do clipe).
  Nao ha trilha eletrônica pronta — o caminho "faixa pronta" do roteiro nao
  foi necessario.

GRADE RITMICA (dita pela bicada, 24 fps):
  120 BPM => 12 frames/beat, 48 frames/compasso (2,000s). O grid casa 1:1 com
  a grade de frames — o conformedo da Fase 4 encaixa cada bicada visual num
  frame de beat (delta alvo 0).

ESTRUTURA (frames @24fps, 1080 frames = 45,000s):
  A  0-359   (0:00-0:15)  cama fina + woodblock no ritmo REAL medido dos
                         passos (nao quantizado — leitura documental).
                         KICK #1 em f288 (12,000s) = 1o evento forte.
  B  360-719 (0:15-0:30)  quantizacao: hats em colcheias, coo a cada compasso,
                         KICK #2 f384 (1->2), KICK #3 duplo f480/483 (2->4),
                         KICK #4 f576 (preparo).
  C  720-1079(0:30-0:45)  KICK #5 f744 + RACHADURA f756 (pata #1); camada de
                         minibicadas entra f768 (1/beat -> 2/beat -> 4/beat);
                         build f960-1067; BICADA COLETIVA f1068 (44,5s);
                         12 frames de hold no pico -> CORTE em f1080 (45,000s).

Saida: assets/audio/fase3_track.wav + fase3_timestamps.json
Uso:   tools/venv/bin/python tools/audio_fase3.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "audio", "A_ambiente.wav")
OUTDIR = os.path.join(ROOT, "assets", "audio")
OUT_WAV = os.path.join(OUTDIR, "fase3_track.wav")
OUT_JSON = os.path.join(OUTDIR, "fase3_timestamps.json")

SR = 48000
FPS = 24
DUR = 45.0
NF = int(DUR * FPS)          # 1080
BPM = 120
FPM = FPS * 60 / BPM         # frames por beat = 12


def beat_frame(n: int) -> int:
    """beat 1 = frame 0; beat n = frame (n-1)*12."""
    return (n - 1) * FPM


def frame_of(t: float) -> int:
    return int(round(t * FPS))


# ----------------------------- extracao de samples ------------------------
def load() -> np.ndarray:
    d, sr = sf.read(SRC)
    assert sr == SR
    return d


def window(d: np.ndarray, t: float, pre: float, post: float) -> np.ndarray:
    i0 = max(0, int(t * SR) - int(pre * SR))
    i1 = min(len(d), int(t * SR) + int(post * SR))
    return d[i0:i1].copy()


def band(x: np.ndarray, f0: float, f1: float, order: int = 4) -> np.ndarray:
    nyq = SR / 2
    lo = max(f0 / nyq, 1e-4)
    hi = min(f1 / nyq, 1.0 - 1e-4)
    b, a = butter(order, [lo, hi], btype="band")
    return filtfilt(b, a, x)


def hp(x: np.ndarray, f0: float, order: int = 4) -> np.ndarray:
    b, a = butter(order, f0 / (SR / 2), btype="high")
    return filtfilt(b, a, x)


def fade(x: np.ndarray, tau: float) -> np.ndarray:
    return x * np.exp(-np.arange(len(x)) / (tau * SR))


def norm(x: np.ndarray, target: float = 0.9) -> np.ndarray:
    m = np.abs(x).max()
    if m < 1e-9:
        return x
    return x * (target / m)


def at(out: np.ndarray, t: float, x: np.ndarray, level: float = 1.0,
       off: float = 0.0) -> None:
    """Soma x no output no instante t (com offset em segundos), com rampa."""
    i0 = int((t + off) * SR)
    i1 = min(len(out), i0 + len(x))
    if i0 >= len(out) or i1 <= i0:
        return
    seg = out[i0:i1]
    x = x[: i1 - i0] * level
    n = min(len(x), 4)  # rampa ~0,08ms: evita click sem mascarar transiente
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    seg += x


def sine(f: float, dur: float, decay: float, level: float,
         f_end: float | None = None, vib_hz: float = 0.0,
         vib_amt: float = 0.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f_t = np.full(n, f) if f_end is None else f + (f_end - f) * (t / dur)
    if vib_hz > 0:
        f_t = f_t + vib_amt * np.sin(2 * np.pi * vib_hz * t)
    ph = 2 * np.pi * np.cumsum(f_t) / SR
    env = np.exp(-t / decay)
    return (level * np.sin(ph) * env).astype(np.float64)


def noise_burst(dur: float, f0: float, level: float, order: int = 4) -> np.ndarray:
    n = int(dur * SR)
    x = np.random.default_rng(7).standard_normal(n)
    b, a = butter(order, f0 / (SR / 2), btype="low")
    x = filtfilt(b, a, x)
    x *= np.exp(-np.arange(n) / (dur * SR * 2.2))
    return x * level


# ----------------------------- instrumentos --------------------------------
def make_kick(src: np.ndarray, deep: bool = False) -> np.ndarray:
    """KICK = clique real da bicada (transiente do material) + sub sintetizado
    disparado pelo proprio clique (65/130 Hz; `deep` soma 48 Hz no 1o kick do
    filme e na coletiva). Sub atrasado 2ms: o clique abre, o corpo fecha —
    como na bicada real medida em 16,7656s."""
    x = norm(src, 1.0)
    n = int(0.22 * SR)
    sub = sine(65.0, 0.22, 0.075, 0.95) + sine(130.0, 0.22, 0.03, 0.25)
    if deep:
        sub = sub + sine(48.0, 0.22, 0.10, 0.85)
    i = int(0.002 * SR)
    out = np.zeros(max(n + i + 200, len(x) + 200))
    out[:len(x)] = x
    out[i:i + len(sub)] += norm(sub, 0.85)  # sub abaixo do clique real
    return norm(out[:n + i + 200], 1.0)


def make_coo(rng: np.random.Generator) -> np.ndarray:
    """ARRULHO GRAVE sintetizado (unico elemento sem sample no clipe).
    Fundamental ~230Hz, padrao 'hoo-hoo' (2 humps), 2a/3a harmônicas,
    queda de pitch no fim do 2o hump, vibrato leve. Caseto com a banda
    100-400Hz do ambiente."""
    f0 = 228.0
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    # envelope hoo-hoo: dois humps gaussianos
    g = lambda c, w: np.exp(-((t - c) ** 2) / (2 * w ** 2))
    env = 0.95 * g(0.16, 0.075) + 1.0 * g(0.56, 0.10)
    env = np.clip(env, 0, None)
    # pitch: leve queda no fim
    f_t = f0 * (1 - 0.10 * np.clip((t - 0.62) / 0.38, 0, 1))
    f_t += 3.0 * np.sin(2 * np.pi * 4.5 * t) * env
    ph = 2 * np.pi * np.cumsum(f_t) / SR
    x = np.sin(ph) + 0.30 * np.sin(2 * ph + 0.5) + 0.12 * np.sin(3 * ph)
    x *= env
    x += 0.15 * x * (rng.standard_normal(n) * 0.15 + 0.85)  # ar do bico
    return norm(x, 0.9)


def main() -> int:
    rng = np.random.default_rng(42)
    d = load()
    out = np.zeros(int(DUR * SR))
    events: list[dict] = []

    def ev(frame: int, typ: str, note: str, strength: str = "forte") -> None:
        events.append({"frame": frame, "t": round(frame / FPS, 4),
                       "tipo": typ, "nota": note, "forca": strength})

    # ----------------------------- samples reais ---------------------------
    # bicada real: clique em 16,7656s (f402 do field) + thump a +20ms
    kick_src = window(d, 16.7656, 0.004, 0.030)
    wood_srcs = [window(d, t, 0.004, 0.020) for t in
                 (6.353, 9.266, 7.758, 13.134)]          # tiques de unhas
    wood_srcs = [band(w, 500, 2500) for w in wood_srcs]
    hat_srcs = [window(d, t, 0.002, 0.010) for t in
                (1.509, 10.955, 4.275, 2.869)]           # cliques curtos
    hat_srcs = [hp(h, 3200) for h in hat_srcs]
    crack_src = band(window(d, 7.758, 0.004, 0.030), 1800, 5200)
    n_stretch = len(crack_src) * 5
    crack_src = np.interp(np.linspace(0, len(crack_src) - 1, n_stretch),
                          np.arange(len(crack_src)), crack_src)
    crack_src = norm(crack_src, 0.9)
    # snap curto p/ a coletiva: a migalha ja esta aberta; e um 'craque' seco
    crack_snap = band(window(d, 7.758, 0.004, 0.010), 1800, 5200)
    crack_snap = norm(fade(crack_snap, 0.010), 0.9)
    # cama: o proprio ambiente (20s) em loop com crossfade p/ cobrir 45s —
    # som de rua difuso: a emenda nao e perceptivel
    bed = filtfilt(*butter(3, 900 / (SR / 2), btype="low"), d)
    cf = int(0.4 * SR)
    bed45 = np.zeros(int(SR * DUR))
    tail = int(SR * DUR) - len(bed)
    part2 = np.zeros(tail + cf)
    for off in range(0, tail + cf, len(bed)):  # o clipe e 20,01s, nao 20,0
        take = min(len(bed) - off, tail + cf - off)
        part2[off:off + take] = bed[off:off + take]
    bed45[:len(bed)] = bed
    bed45[len(bed) - cf:len(bed)] = (bed[len(bed) - cf:len(bed)]
                                     * np.linspace(1, 0, cf)
                                     + part2[:cf] * np.linspace(0, 1, cf))
    bed45[len(bed):len(bed) + tail] = part2[cf:cf + tail]
    bed = bed45

    kick_n = make_kick(kick_src)
    kick_deep = make_kick(kick_src, deep=True)
    coo = make_coo(rng)
    minipeck = norm(hp(window(d, 4.275, 0.002, 0.010), 4500), 0.55)
    # transposto 1 oitava p/ cima (minipombo = bico pequeno)
    minipeck = np.interp(np.linspace(0, len(minipeck) - 1,
                                     int(len(minipeck) * 0.5)),
                         np.arange(len(minipeck)), minipeck)

    # ----------------------------- BLOCO A ---------------------------------
    # cama fina
    at(out, 0.0, norm(bed[:int(15 * SR)], 0.10))
    # ritmo REAL dos passos: clusters medidos (offsets de unhas em ms)
    c1 = [0, 42, 88, 134, 185, 240]
    c2 = [0, 65, 137]
    c3 = [0, 90, 177, 249, 289, 350, 376, 432]
    cycle = [c1, c2, c3]
    step_starts = [0.0]
    gaps = [1.382, 1.483, 1.430]   # ciclos reais medidos (6.31->7.69->9.18)
    for g in gaps:
        step_starts.append(step_starts[-1] + g)
    # 4 ciclos ~15s, com deriva +-2% (documental, nao quantizado)
    t0 = 0.9
    ci = 0
    for cyc in range(4):
        drift = 1.0 + rng.uniform(-0.02, 0.02)
        for si, offs in enumerate(cycle):
            t = t0 + cyc * (1.382 * 3) * drift + sum(gaps[:si]) * drift
            for ms in offs:
                s = wood_srcs[(ci + si) % len(wood_srcs)]
                lvl = 0.07 + 0.05 * ((ci + si + ms) % 3) / 3
                at(out, t + ms / 1000, norm(s), lvl)
            ci += 1
    # KICK #1 — 1o evento forte do filme, f288 = 12,000s (beat 25)
    at(out, 288 / FPS, kick_deep, 1.0)
    ev(288, "kick", "BICADA #1 (pombo real) — 1o evento forte do filme", "forte")
    # quem silencia: nada forte antes de f288 (apenas cama + unhas)

    # ----------------------------- BLOCO B ---------------------------------
    at(out, 15.0, norm(bed[int(15 * SR):int(30 * SR)], 0.24))
    # coo a cada compasso (a massa grave entra com a duplicacao)
    for f in range(360, 720, 48):
        at(out, f / FPS, coo, 0.30 + 0.02 * (f - 360) / 48)
        if f in (360, 408, 456, 504, 552, 600, 648, 696):
            ev(f, "coo", "arrulho grave = baixo (a cada compasso)", "medio")
    # hats em colcheias (6f) de 15-25s, semicolcheias (3f) de 25-30s
    for f in range(360, 600, 6):
        s = hat_srcs[(f // 6) % len(hat_srcs)]
        lvl = 0.10 if f % 12 else 0.16
        at(out, f / FPS, norm(s), lvl)
    for f in range(600, 720, 3):
        s = hat_srcs[(f // 3) % len(hat_srcs)]
        lvl = 0.08 if f % 6 else 0.14
        at(out, f / FPS, norm(s), lvl)
    # woodblock quantizado (a tomada de conta musical do ritmo real)
    for f in range(360, 720, 6):
        s = wood_srcs[(f // 6) % len(wood_srcs)]
        at(out, f / FPS, norm(s), 0.12 if f % 12 else 0.18)
    # KICK #2 f400 (16,667s): 1 -> 2 — A BICADA DA IMAGEM (F2, mestra).
    # Regra de sincronia da aprovacao F2: o kick se ajusta ao frame da bicada,
    # nunca o contrario. f400 nao e beat do grid 288-phase (mais proximo: f396)
    # — o kick fica 4f apos o beat: drag diegetico, documentado.
    at(out, 400 / FPS, kick_n, 0.95)
    ev(400, "kick", "BICADA #2 — duplicacao 1 -> 2; bicada da imagem (F2, "
                    "mestra): kick ajustado ao frame f400", "forte")
    at(out, 412 / FPS, crack_src, 0.5)
    ev(412, "crack", "migalha abre (revelacao F2 f412-421; +12f do kick, "
                     "mesmo intervalo do prototipo)", "medio")
    # KICK #3 f480 (20,0s): 2 -> 4, kick duplo (o roteiro permite "talvez duplo")
    at(out, 480 / FPS, kick_n, 0.95)
    at(out, 483 / FPS, kick_n, 0.7)
    ev(480, "kick", "BICADA #3 — duplicacao 2 -> 4 (kick duplo f480/f483)", "forte")
    at(out, 492 / FPS, crack_src, 0.45)
    at(out, 495 / FPS, crack_src, 0.35)
    ev(492, "crack", "2 migalhas abrem (duplo crack f492/f495)", "medio")
    # KICK #4 f576 (24,0s): preparacao (sem duplicacao)
    at(out, 576 / FPS, kick_n, 0.8)
    ev(576, "kick", "BICADA #4 — preparacao (sem duplicacao)", "forte")

    # ----------------------------- BLOCO C ---------------------------------
    at(out, 30.0, norm(bed[int(30 * SR):], 0.30))
    # densidade: hats semicolcheias constantes
    for f in range(720, 1068, 3):
        s = hat_srcs[(f // 3) % len(hat_srcs)]
        lvl = 0.09 if f % 6 else 0.15
        at(out, f / FPS, norm(s), lvl)
    # woodblock em colcheias, roll de 16 avos a partir de 36s
    for f in range(720, 864, 6):
        s = wood_srcs[(f // 6) % len(wood_srcs)]
        at(out, f / FPS, norm(s), 0.16 if f % 12 else 0.22)
    for f in range(864, 1068, 3):
        s = wood_srcs[(f // 3) % len(wood_srcs)]
        at(out, f / FPS, norm(s), 0.12 if f % 6 else 0.18)
    # coo: a cada compasso ate 38s, a cada beat de 38-40s, drive de 40-44,5
    for f in range(720, 912, 48):
        at(out, f / FPS, coo, 0.34)
    for f in range(912, 960, 12):
        at(out, f / FPS, coo, 0.30)
    for f in range(960, 1056, 12):  # para antes do hit (respiro)
        at(out, f / FPS, coo, 0.30 + 0.03 * (f - 960) / 96)
    # KICK #5 f744 (31,0s) + RACHADURA f756: pata #1 (minipombo)
    at(out, 744 / FPS, kick_n, 0.9)
    ev(744, "kick", "BICADA #5 — migalha abre revelando patas (minipombo #1)",
       "forte")
    at(out, 756 / FPS, crack_src, 0.6)
    at(out, 756 / FPS + 0.012, minipeck, 0.5)
    ev(756, "crack", "revelacao das patas (oclusao) + mini woodblock", "forte")
    # camada de MINIBICADAS: 1/beat de 32-36s, 2/beat de 36-40s,
    # 4/beat (8 avos, 3f) de 40-44,5s
    for f in range(768, 864, 12):
        at(out, f / FPS, minipeck, 0.5)
    for f in range(864, 960, 6):
        at(out, f / FPS, minipeck, 0.42 + (f % 12) / 12 * 0.1)
    for f in range(960, 1068, 3):
        at(out, f / FPS, minipeck, 0.28 + (f % 6) / 6 * 0.14)
    ev(768, "minipeck", "camada de minibicadas entra (1/beat)", "medio")
    ev(864, "minipeck", "minibicadas 2/beat + roll de woodblock", "medio")
    ev(960, "minipeck", "minibicadas 4/beat — build p/ coletiva", "medio")
    # ------------------------- BICADA COLETIVA f1068 -----------------------
    # corpo do kick (65/130) + thump 48Hz curto: sem batimento na cauda
    at(out, 1068 / FPS, kick_n, 1.4)
    for k, off in enumerate((0, 2, 4, 6)):
        at(out, (1068 + off) / FPS, minipeck, 0.75 - k * 0.08)
    at(out, 1068 / FPS, crack_snap, 0.9)
    at(out, 1068 / FPS, fade(noise_burst(0.09, 3000, 0.6), 0.04), 1.0)
    at(out, 1068 / FPS, sine(48.0, 0.06, 0.02, 1.0), 1.0)
    ev(1068, "kick", "BICADA COLETIVA (todos juntos) — maximo do trecho; "
                     "hold de 12f no pico -> CORTE em f1080 (45,000s)",
       "maximo")

    # ----------------------------- master ----------------------------------
    # normaliza p/ -1 dBFS e limita suavemente
    out = out / max(np.abs(out).max(), 1e-9) * 0.89
    out = np.tanh(out * 1.15) * 0.92
    sf.write(OUT_WAV, out.astype(np.float32), SR)

    ts = {
        "formato": "mono 48kHz, 45,000s = 1080 frames @ 24fps",
        "caminho": "diegetico: percussao 100% de samples do proprio clipe; "
                   "arrulho (baixo) sintetizado — unico elemento sem sample "
                   "(verificado: varredura tonal 80-800Hz nao encontra "
                   "arrulho no material)",
        "grade": {"bpm": BPM, "frames_por_beat": FPM,
                  "frames_por_compasso": 48,
                  "beat_n_frame": "frame = (n-1)*12",
                  "nota": "a bicada e a mestra: o kick #2 esta no frame da bicada da "
                          "imagem (f400, F2 aprovado) por ajuste explicito — "
                          "f400 nao e beat do grid (mais proximo: f396, drag "
                          "de 4f documentado); as demais bicadas (novas, "
                          "Fase 4) encaixam em beats do grid; verify roda "
                          "contra o audio real apos o corte"},
        "eventos": events,
        "blocos": {
            "A": {"frames": [0, 359], "dificacao": "cama fina + ritmo real "
                    "dos passos (nao quantizado); 1o evento forte em f288"},
            "B": {"frames": [360, 719], "dificacao": "quantizacao; "
                    "duplicacoes 1->2 (f384) e 2->4 (f480)"},
            "C": {"frames": [720, 1079], "dificacao": "revelacao das patas "
                    "(f744/f756), minibicadas, build, coletiva f1068, "
                    "hold 12f, corte f1080"},
        },
        "samples_reais": {
            "kick": "clique da bicada em 16,7656s (f402 do field; 2 frames "
                    "apos o contato visual f400 — latencia real; no corte o "
                    "onset e quantizado ao frame da bicada)",
            "woodblock": "tiques de unhas em 6,353 / 9,266 / 7,758 / 13,134s",
            "hi-hat": "cliques curtos em 1,509 / 10,955 / 4,275 / 2,869s",
            "crack": "tique de unha em 7,758s esticado 5x + bandpass 1,8-5,2k",
            "cama": "ambiente inteiro lowpass 900Hz",
        },
    }
    with open(OUT_JSON, "w") as fh:
        json.dump(ts, fh, indent=1, ensure_ascii=False)
    print(f"[ok] {OUT_WAV} ({DUR:.3f}s) | {len(events)} eventos -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
