#!/usr/bin/env python3
"""Fase 4 — trilha original "COO" (128 BPM, 75 s, loop exato).

Grelha musical (definida em `score_grid.py`, importada pelo compositor de vídeo):

    128 BPM · 4/4 · BEAT = 0.46875 s · BAR = 1.875 s · 40 compassos = 75.000 s

Todos os eventos são escritos com *índice circular* (`_add` escreve com
`% N`), portanto o buffer de 75 s é literalmente periódico: o compasso 41 é
o compasso 1. A reverb é convolução **circular** (IR de 1.8 s com cauda
decrescente) e entra no mesmo buffer, logo o rabo do compasso 40 desagua
no compasso 1 sem clique nem corte.

Instrumentação (síntese aditiva/subtrativa em numpy+scipy, sem samples):

    kick      sino com sweep 115→42 Hz + click
    sub       queda de sub nos impactos de multiplicação
    hat       ruído HP 16as oitavas, aberto nos contratempos
    clap      três rajadas de ruído BP (beats 2 e 4)
    bass      dente-de-serra + sub, LP com envelope (notas do acorde)
    lead      saw detunado com LP ressonante (ostíinato de 16as)
    pad       saws desafinados, ataque lento (Am–F–C–G por compasso)
    stab      acorde curto nos downbeats
    riser     ruído + saw com filtro a subir (compasso antes de cada pico)
    wind      leito de vento (ruído filtrado, periódico por construção)

O arranjo é **governado por `N(t)`** (a contagem de cópias do vídeo): cada
camada tem um limiar `MIN_N` — kick 4/4 a partir de 2 cópias, 8as a partir
de 4, baixo em movimento e lead a partir de 8, stab/16as a partir de 16,
clap e lead agudo a partir de 24. No colapso as camadas saem na ordem
inversa automaticamente, porque é a mesma função a descer. Bass, harmonia
e lead levam *ducking* do kick (`duck_envelope`) para não ensopar.
Risers resolvem exactamente no beat do degrau; no crescimento o impacto é
um sub-drop, no colapso é uma varredura descendente de sucção.

Uso (raiz do repo):
    .venv/bin/python scripts/compose_score.py            # WAV + FLAC
    .venv/bin/python scripts/compose_score.py --no-flac
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_grid import (  # noqa: E402
    BAR,
    BARS,
    BEAT,
    DURATION,
    OUT_AUDIO,
    PEAK_N,
    ROOT,
    SR,
    STEPS,
    SWITCH_TIMES,
    bar,
    n_at,
    scheduler_summary,
)

N = int(round(DURATION * SR))
RNG = np.random.default_rng(20260918)

# ---------------------------------------------------------------- acordes ---
# Am – F – C – G (A menor natural), um acorde por compasso, ciclo de 4.
CHORDS = {
    "Am": [220.00, 261.63, 329.63],          # A3 C4 E4
    "F": [174.61, 220.00, 261.63],           # F3 A3 C4
    "C": [196.00, 261.63, 329.63],           # G3 C4 E4
    "G": [196.00, 246.94, 293.66],           # G3 B3 D4
}
PROG = ["Am", "F", "C", "G"]
BASS_ROOT = {"Am": 55.00, "F": 43.65, "C": 65.41, "G": 49.00}  # A1 F1 C2 G1
LEAD_ORDER = {"Am": [220.00, 329.63, 440.00, 523.25],
              "F": [174.61, 261.63, 349.23, 440.00],
              "C": [196.00, 261.63, 392.00, 523.25],
              "G": [196.00, 246.94, 392.00, 493.88]}


def chord_at(b: int) -> str:
    return PROG[b % 4]


# ------------------------------------------------------------- utilitários ---
def _add(buf: np.ndarray, sig: np.ndarray, t0: float, gain: float = 1.0) -> None:
    """Soma `sig` no buffer com índice circular (loop exacto).

    `sig` pode atravessar o fim do buffer: nesse caso a cauda continua no
    início (é isso que faz o compasso 40 desaguar no compasso 1).
    """
    if sig.ndim == 1:
        sig = np.stack([sig, sig], axis=1)
    sig = (sig * gain).astype(np.float32)
    n = sig.shape[0]
    i0 = int(round(t0 * SR)) % N
    head = min(n, N - i0)
    buf[i0 : i0 + head] += sig[:head]
    if head < n:  # cauda dá a volta ao loop
        buf[: n - head] += sig[head:]


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _exp_env(n: int, tau: float, attack: float = 0.0015) -> np.ndarray:
    t = _t(n)
    env = np.exp(-t / tau)
    a = max(1, int(attack * SR))
    env[:a] *= np.linspace(0.0, 1.0, a) ** 0.6
    return env


def _saw(freq, n: int, phase: float = 0.0) -> np.ndarray:
    t = _t(n) + phase
    if np.isscalar(freq):
        ph = (t * freq) % 1.0
    else:
        ph = (np.cumsum(freq) / SR) % 1.0
    return 2.0 * ph - 1.0


def _sine(freq, n: int, phase: float = 0.0) -> np.ndarray:
    t = _t(n) + phase
    if np.isscalar(freq):
        return np.sin(2 * np.pi * freq * t)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR)


def lp(x, fc, order=2):
    sos = signal.butter(order, min(fc, SR * 0.45) / (SR / 2), btype="lowpass", output="sos")
    return signal.sosfilt(sos, x)


def hp(x, fc, order=2):
    sos = signal.butter(order, max(fc, 20.0) / (SR / 2), btype="highpass", output="sos")
    return signal.sosfilt(sos, x)


def bp(x, f0, f1, order=2):
    sos = signal.butter(order, [max(f0, 20.0) / (SR / 2), min(f1, SR * 0.45) / (SR / 2)], btype="bandpass", output="sos")
    return signal.sosfilt(sos, x)


def _noise(n: int) -> np.ndarray:
    return RNG.standard_normal(n)


def _pan(sig: np.ndarray, p: float) -> np.ndarray:
    """p ∈ [-1, 1] → [-1 esquerda, 1 direita]."""
    if sig.ndim == 1:
        sig = np.stack([sig, sig], axis=1)
    l = np.sqrt(0.5 * (1.0 - p))
    r = np.sqrt(0.5 * (1.0 + p))
    return np.stack([sig[:, 0] * l * np.sqrt(2), sig[:, 1] * r * np.sqrt(2)], axis=1)


# ------------------------------------------------------------ instrumentos ---
def kick(dur: float = 0.55) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    f = 42.0 + 78.0 * np.exp(-t / 0.038)
    body = _sine(f, n) * _exp_env(n, 0.155, attack=0.001)
    click = hp(_noise(n) * np.exp(-t / 0.0035), 2500.0) * 0.35
    return lp(body * 1.0 + click, 7000.0)


def sub_drop(dur: float = 1.4, f0: float = 90.0, f1: float = 32.0) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.35)
    return _sine(f, n) * _exp_env(n, 0.55, attack=0.004)


def hat(dur: float = 0.12, open_: bool = False) -> np.ndarray:
    n = int(dur * SR)
    tau = 0.16 if open_ else 0.028
    x = hp(_noise(n), 7200.0, order=2) * _exp_env(n, tau, attack=0.0008)
    x = bp(x, 6000.0, 16000.0)
    return x * (0.55 if open_ else 0.42)


def clap(dur: float = 0.4) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    env = np.zeros(n)
    for k, (off, amp) in enumerate([(0.000, 1.0), (0.009, 0.8), (0.019, 0.62), (0.030, 0.45)]):
        i0 = int(off * SR)
        env[i0:] += amp * np.exp(-(t[: n - i0]) / 0.055)
    body = bp(_noise(n) * env, 1100.0, 6500.0)
    return body * 0.5 + bp(_noise(n) * _exp_env(n, 0.02), 250.0, 900.0) * 0.25


def bass(freq: float, dur: float = 0.42, accent: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    saw = _saw(freq, n) * 0.55 + _sine(freq * 0.5, n) * 0.75
    x = lp(saw, 260.0 + 380.0 * accent, order=2) * _exp_env(n, 0.20, attack=0.003)
    return x * (0.7 + 0.3 * accent)


def lead(freq: float, dur: float = 0.30, detune: float = 0.007, cutoff: float = 2400.0) -> np.ndarray:
    n = int(dur * SR)
    x = (_saw(freq, n) + _saw(freq * (1 + detune), n, 0.31) + _saw(freq * (1 - detune), n, 0.72)) / 3.0
    x = lp(x, cutoff, order=2) * _exp_env(n, 0.10, attack=0.004)
    return x * 0.62


def pad(freqs: list[float], dur: float, bright: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    voices = []
    for k, f in enumerate(freqs):
        for d, ph in ((1.0, 0.0), (1.0035, 0.37), (0.9965, 0.71)):
            voices.append(_saw(f * d * (2.0 if k == 0 else 1.0), n, ph))
    x = np.stack(voices, axis=0).sum(axis=0) / len(voices)
    env = np.minimum(1.0, _t(n) / 0.45) * np.minimum(1.0, (dur - _t(n)) / 0.5)
    env = np.clip(env, 0.0, 1.0) ** 0.8
    return lp(x * env, 900.0 * bright, order=2)


def stab(freqs: list[float], dur: float = 0.55) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    voices = np.stack([_saw(f * d, n, ph) for f in freqs for d, ph in ((1.0, 0.0), (1.008, 0.4))], axis=0)
    x = voices.sum(axis=0) / len(voices)
    cutoff = 3200.0 * np.exp(-t / 0.18) + 480.0
    # LP variável: blocos com o estado do filtro a transitar entre blocos
    # (sem isso o sosfilt reinicia a zeros e abre um clique a cada bloco)
    out = np.zeros(n)
    step = 512
    zi = None
    for i in range(0, n, step):
        blk = x[i : i + step]
        sos = signal.butter(2, min(float(cutoff[i]), SR * 0.45) / (SR / 2), btype="lowpass", output="sos")
        if zi is None:
            zi = signal.sosfilt_zi(sos) * blk[0]
        out[i : i + step], zi = signal.sosfilt(sos, blk, zi=zi)
    return out * _exp_env(n, 0.22, attack=0.004) * 0.5


def riser(dur: float, f0: float = 220.0, f1: float = 2600.0) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    u = np.clip(t / dur, 0.0, 1.0)
    sweep = _sine(f0 * (f1 / f0) ** u, n)
    saw = _saw(f0 * 0.5 * (f1 / f0) ** u, n)
    noise = bp(_noise(n), 900.0, 7000.0)
    env = u**1.6
    x = (sweep * 0.35 + saw * 0.30 + noise * 0.35) * env
    return lp(x, 5200.0) * 0.55


def sweep_down(dur: float = 1.0, f0: float = 3200.0, f1: float = 170.0) -> np.ndarray:
    """Sucção do colapso: sino a descer + whoosh a fechar."""
    n = int(dur * SR)
    t = _t(n)
    u = np.clip(t / dur, 0.0, 1.0)
    tone = _sine(f0 * (f1 / f0) ** u, n) * np.exp(-t / 0.45)
    air = lp(_noise(n) * np.exp(-t / 0.30), 2600.0)
    return (tone * 0.55 + air * 0.45) * 0.6


def wind(dur: float = DURATION, seed: int = 991) -> np.ndarray:
    """Leito contínuo e periódico: ruído filtrado com LFO lento."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = _t(n)
    base = rng.standard_normal(n)
    base = lp(base, 420.0, order=2)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * t / (BAR * 8.0))
    base = base * lfo
    return _pan(base * 0.30, 0.0)


# ------------------------------------------------------------- arranjo ------
# Cada camada é governada DIRECTAMENTE por N(t) — a música sobe com a
# contagem de cópias e desce espelhada no colapso. É isso que garante duas
# coisas ao mesmo tempo: (a) "a trilha ganha camadas na mesma curva da
# contagem"; (b) o compasso 40 regressa à textura do compasso 1, que é a
# condição musical do loop perfeito.

MIN_N = {  # limiar de N a partir do qual a camada existe
    "kick4": 2,
    "hats8": 4,
    "bass": 4,
    "openhat": 8,
    "bass_motion": 8,
    "lead": 8,
    "stab": 16,
    "hat16": 16,
    "clap": 24,
    "lead_hi": 24,
}


def on(layer: str, b: int) -> bool:
    """Camada activa no compasso b? Regida por N a meio do compasso."""
    n_now = n_at(b * BAR + BAR * 0.5)
    if layer == "ticks":
        # 8as discretas: entram depois de a cena estabelecer e saem na
        # cauda do colapso (espelha a abertura, preserva a costura)
        return 4 <= b < 36
    return n_now >= MIN_N[layer]


def build_stems() -> tuple[dict[str, np.ndarray], list[float]]:
    """Soma cada família de instrumentos no seu próprio bus (para ducking)."""
    stems = {k: np.zeros((N, 2), dtype=np.float32) for k in ("drums", "bass", "harmony", "lead", "fx")}
    kick_times: list[float] = []

    # ---- leito de vento (periódico por construção) -----------------------
    _add(stems["fx"], lp(wind(), 1200.0), 0.0, 0.50)

    for b in range(BARS):
        t0 = bar(b)
        ch = chord_at(b)
        n_now = n_at(t0 + BAR * 0.5)
        bright = 0.62 + 0.75 * (n_now / PEAK_N)          # filtro abre com N
        dens = 0.85 + 0.35 * (n_now / PEAK_N)

        # ---- pad (compasso inteiro, cauda de meio compasso) --------------
        chord = CHORDS[ch]
        _add(stems["harmony"], _pan(pad(chord, BAR * 1.06, bright=bright), -0.55), t0, 0.40 * dens)
        _add(stems["harmony"], _pan(pad(chord, BAR * 1.06, bright=bright), 0.55), t0, 0.34 * dens)

        # ---- kick --------------------------------------------------------
        if on("kick4", b):
            for k in range(4):
                vel = 1.0 if k % 2 == 0 else 0.86
                _add(stems["drums"], _pan(kick(), 0.0), t0 + k * BEAT, 0.95 * vel)
                kick_times.append(t0 + k * BEAT)
        else:
            _add(stems["drums"], _pan(kick(), 0.0), t0, 1.0)
            kick_times.append(t0)

        # ---- hats --------------------------------------------------------
        if on("ticks", b):
            for k in range(8):
                tt = t0 + k * BEAT / 2.0
                vel = 0.34 if k % 2 else 0.26
                _add(stems["drums"], _pan(hat(0.05), 0.30 * (-1) ** k), tt, vel)
        if on("hats8", b):
            for k in range(8):
                vel = 0.62 if k % 2 else 0.44
                _add(stems["drums"], _pan(hat(), 0.28 * (-1) ** k), t0 + k * BEAT / 2.0, vel)
        if on("hat16", b):
            for k in range(16):
                if k % 2 == 0:
                    continue
                _add(stems["drums"], _pan(hat(0.06), 0.4 if (k // 2) % 2 else -0.4), t0 + k * BEAT / 4.0, 0.26)
        if on("openhat", b):
            for k in (1, 3):
                _add(stems["drums"], _pan(hat(open_=True), -0.30), t0 + k * BEAT + BEAT / 2.0, 0.30)

        # ---- bass --------------------------------------------------------
        if on("bass", b):
            root = BASS_ROOT[ch]
            if on("bass_motion", b):
                for off, note, acc in (
                    (BEAT * 0.5, root, 1.0),
                    (BEAT * 1.5, root * 1.5, 0.80),
                    (BEAT * 2.5, root, 0.92),
                    (BEAT * 3.0, root * 2.0, 0.72),
                ):
                    _add(stems["bass"], _pan(bass(note, dur=0.40, accent=acc), 0.0), t0 + off, 0.80 * acc)
            else:
                _add(stems["bass"], _pan(bass(root, dur=0.60, accent=0.95), 0.0), t0, 0.82)
                _add(stems["bass"], _pan(bass(root, dur=0.45, accent=0.70), 0.0), t0 + 2 * BEAT, 0.68)

        # ---- lead (ostíinato de 16as) ------------------------------------
        if on("lead", b):
            notes = LEAD_ORDER[ch]
            for k in range(16):
                if k % 4 == 3 and b % 2 == 1:
                    continue  # deixa respirar
                f = notes[(k // 2) % len(notes)]
                if k % 4 in (0, 2):
                    f *= 2.0
                pan = 0.35 * np.sin(2 * np.pi * k / 16.0)
                _add(stems["lead"], _pan(lead(f, dur=0.26, cutoff=2000.0 + 900.0 * bright), pan), t0 + k * BEAT / 4.0, 0.30 * dens)
        if on("lead_hi", b):
            notes = LEAD_ORDER[ch]
            for k in range(8):
                f = notes[(k + 1) % len(notes)] * 2.0
                _add(stems["lead"], _pan(lead(f, dur=0.22, cutoff=3800.0), -0.5), t0 + k * BEAT / 2.0 + BEAT / 4.0, 0.20)

        # ---- clap (beats 2 e 4) ------------------------------------------
        if on("clap", b):
            for k in (1, 3):
                _add(stems["drums"], _pan(clap(), 0.0), t0 + k * BEAT, 0.55)

        # ---- stab nos downbeats ------------------------------------------
        if on("stab", b) and b % 2 == 0:
            _add(stems["harmony"], _pan(stab(CHORDS[ch], dur=0.5), 0.0), t0, 0.40)

    return stems, kick_times


def build_events() -> np.ndarray:
    """Risers, impactos e varreduras — um por degrau de N(t), resolvendo no beat."""
    fx = np.zeros((N, 2), dtype=np.float32)
    for t_sw in SWITCH_TIMES:
        growing = n_at(t_sw + 1e-6) > n_at(t_sw - 1e-6)
        r_dur = BAR if t_sw < 45.0 else BAR * 1.6
        _add(fx, riser(r_dur), t_sw - r_dur, 0.46)
        if growing:
            _add(fx, sub_drop(dur=1.25, f0=95.0, f1=33.0), t_sw, 0.62)
            _add(fx, bp(_noise(int(0.5 * SR)) * _exp_env(int(0.5 * SR), 0.11), 3000.0, 9000.0), t_sw, 0.30)
        else:
            # colapso = sucção: varredura descendente + whoosh
            _add(fx, sweep_down(dur=1.1, f0=3200.0, f1=170.0), t_sw, 0.60)
            _add(fx, lp(_noise(int(0.9 * SR)) * _exp_env(int(0.9 * SR), 0.28, attack=0.02), 1400.0), t_sw, 0.34)
    return fx


def duck_envelope(kick_times: list[float], depth: float = 0.55, tau: float = 0.085, tail: float = 0.22) -> np.ndarray:
    """Sidechain simples: baixa bass/harmonia/lead no golpe do kick."""
    env = np.ones(N, dtype=np.float32)
    n_tail = int(tail * SR)
    shape = (1.0 - depth * np.exp(-np.arange(n_tail) / (tau * SR))).astype(np.float32)
    for t_k in kick_times:
        i0 = int(round(t_k * SR)) % N
        head = min(n_tail, N - i0)
        env[i0 : i0 + head] = np.minimum(env[i0 : i0 + head], shape[:head])
        if head < n_tail:
            env[: n_tail - head] = np.minimum(env[: n_tail - head], shape[head:])
    # suaviza os degraus de 1 sample entre janelas
    sos = signal.butter(2, 120.0 / (SR / 2), btype="lowpass", output="sos")
    return signal.sosfilt(sos, env).astype(np.float32)


def mix_stems(stems: dict[str, np.ndarray], fx: np.ndarray, kick_times: list[float]) -> np.ndarray:
    duck = duck_envelope(kick_times)[:, None]

    dry = (
        stems["drums"] * 1.00
        + stems["bass"] * 0.95 * duck
        + stems["harmony"] * 0.55 * duck
        + stems["lead"] * 0.62 * duck
        + (stems["fx"] + fx) * 0.55
    )
    send = (stems["harmony"] * 0.35 + stems["lead"] * 0.30 + fx * 0.45) * duck.squeeze(-1)[:, None]
    wet = _circular_reverb(send.astype(np.float32), ir_len=1.8, decay=3.1, mix=1.0) * 0.55
    x = dry + wet
    return x.astype(np.float32)


def master(x: np.ndarray, target_rms: float = 0.17) -> np.ndarray:
    """Limitador de soft-clip + alvo de RMS (–15.4 dBFS), 2 iterações."""
    g = 1.0
    for _ in range(2):
        y = np.tanh(x * g * 1.05) * 0.94
        rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
        if rms <= 1e-9:
            break
        g *= target_rms / rms
        g = float(np.clip(g, 0.05, 12.0))
    y = np.tanh(x * g * 1.05) * 0.94
    peak = float(np.max(np.abs(y)))
    if peak > 0.99:
        y = y * (0.99 / peak)
    return y.astype(np.float32)


def build() -> np.ndarray:
    stems, kick_times = build_stems()
    fx = build_events()
    return master(mix_stems(stems, fx, kick_times))


def _circular_reverb(x: np.ndarray, ir_len: float, decay: float, mix: float) -> np.ndarray:
    n_ir = int(ir_len * SR)
    t = _t(n_ir)
    ir = RNG.standard_normal((n_ir, 2)).astype(np.float32) * np.exp(-t / (ir_len / decay))[:, None]
    ir = lp(ir, 3600.0, order=2)
    ir[:, 0] *= 0.94
    ir[: int(0.012 * SR)] = 0.0  # pré-delay
    ir /= np.sqrt(np.sum(ir**2, axis=0, keepdims=True)) + 1e-9
    # convolução circular via FFT de comprimento N (o rebordo dá a volta)
    X = np.fft.rfft(x, axis=0)
    H = np.fft.rfft(ir, n=N, axis=0)
    wet = np.fft.irfft(X * H, n=N, axis=0).astype(np.float32)
    return wet * mix


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-flac", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    OUT_AUDIO.mkdir(parents=True, exist_ok=True)
    out_wav = Path(args.out) if args.out else OUT_AUDIO / "coo_score.wav"

    print("→ sintetizando 40 compassos @ 128 BPM ...")
    audio = build()
    assert audio.shape == (N, 2), audio.shape

    # relatório rápido de nível antes de gravar
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(audio)))
    dc = float(np.mean(audio))
    print(f"   RMS={rms:.4f} ({20*np.log10(rms+1e-9):+.1f} dBFS)  peak={peak:.4f}  DC={dc:+.2e}")

    sf.write(out_wav, audio, SR, subtype="PCM_16")
    print(f"   {out_wav.relative_to(ROOT)}")

    if not args.no_flac:
        flac = OUT_AUDIO / "coo_score.flac"
        sf.write(flac, audio, SR, subtype="PCM_16")
        print(f"   {flac.relative_to(ROOT)}")

    meta = {
        "bpm": 128,
        "beat_s": BEAT,
        "bar_s": BAR,
        "bars": 40,
        "duration_s": DURATION,
        "sample_rate": SR,
        "loop": "buffer de 75 s periódico por construção (índices circulares + reverb circular)",
        "rms": rms,
        "rms_dbfs": 20 * np.log10(rms + 1e-9),
        "peak": peak,
        "steps": scheduler_summary(),
        "layer_thresholds": MIN_N,
        "arrangement": "camadas com limiar MIN_N sobre N(t); colapso espelhado",
        "mix": "buses (drums/bass/harmony/lead/fx) + ducking do kick + reverb circular",
    }
    (OUT_AUDIO / "score_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
