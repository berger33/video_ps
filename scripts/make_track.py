#!/usr/bin/env python3
"""FASE 3 — trilha original estilo Cyriak (~112 BPM, 60s), royalty-free.

Arco de energia MACRO bem marcado p/ sincronia:
  0-8   intro quieta (kick leve + plucks esparsos)
  8-24  médio (basso + hats)
  24-40  alto (snare + melodia densa + pad)
  40-48  PICO (tudo + fills + pad duplo)
  48-56  queda (kick leve + baixo esparso)
  56-60  mínimo (1 nota por compasso + kick final) -> loop fecha em silêncio
Onsets percussivos claros p/ sincronia micro. Determinístico (seed fixa).
Saída: assets/src/trilha.wav (44.1kHz, 16-bit).
"""
import os
import numpy as np
import wave

SR = 44100
DUR = 60.0
BPM = 112.0
BEAT = 60.0 / BPM
rng = np.random.default_rng(7)

y = np.zeros(int(SR * DUR), np.float64)


def add(sig, t0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= len(y):
        return
    i1 = min(i0 + len(sig), len(y))
    y[i0:i1] += sig[: i1 - i0] * gain


def env(n, a=0.002, dec=0.15):
    t = np.arange(n) / SR
    return np.clip(t / a, 0, 1) * np.exp(-t / dec)


def kick(t0, g=0.9):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    f = 40 + 95 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    add(np.sin(ph) * np.exp(-t / 0.09), t0, g)


def hat(t0, g=0.25):
    n = int(0.05 * SR)
    nz = rng.standard_normal(n)
    nz = np.diff(nz, prepend=0)
    add(nz * np.exp(-np.arange(n) / SR / 0.015), t0, g)


def snare(t0, g=0.5):
    n = int(0.14 * SR)
    t = np.arange(n) / SR
    add((rng.standard_normal(n) * 0.7 + np.sin(2 * np.pi * 190 * t) * 0.5)
        * np.exp(-t / 0.06), t0, g)


def tone(freq, t0, dur=0.28, kind="tri", g=0.3, vib=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1 + vib * np.sin(2 * np.pi * 6 * t) * 0.01)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = (2 / np.pi * np.arcsin(np.sin(ph))) if kind == "tri" \
        else np.sign(np.sin(ph)) * 0.6
    add(s * env(n, dec=dur / 3), t0, g)


def bass(freq, t0, dur=0.45, g=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    s = np.sign(np.sin(ph)) * 0.35 + np.sin(ph) * 0.65
    add(s * np.clip(t / 0.005, 0, 1) * np.exp(-t / (dur / 2)), t0, g)


def pad(freqs, t0, dur, g=0.1):
    """Sustentado detunado: levanta o RMS de forma contínua (arco macro)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for i, f in enumerate(freqs):
        det = 1 + 0.003 * (i - 1)
        s += np.sin(2 * np.pi * f * det * t) * 0.5
    e = np.clip(t / 0.8, 0, 1) * np.clip((dur - t) / 0.8, 0, 1)
    add(s * e, t0, g)


PENT = [220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 523.25]
CHORDS = [[110.0, 165.0, 220.0], [98.0, 147.0, 196.0],
          [87.31, 130.8, 174.6], [98.0, 147.0, 196.0]]
mel_rng = np.random.default_rng(11)


def sec_of(t):
    if t < 8:
        return 1
    if t < 24:
        return 2
    if t < 40:
        return 3
    if t < 48:
        return 4
    if t < 56:
        return 5
    return 6


G = {  # ganhos por seção: kick, hat, snare, bass, mel, pad
    1: dict(k=0.35, h=0.0, s=0.0, b=0.0, m=0.20, p=0.0),
    2: dict(k=0.70, h=0.16, s=0.0, b=0.28, m=0.22, p=0.05),
    3: dict(k=0.85, h=0.22, s=0.40, b=0.34, m=0.26, p=0.10),
    4: dict(k=1.00, h=0.30, s=0.50, b=0.40, m=0.30, p=0.16),
    5: dict(k=0.50, h=0.0, s=0.0, b=0.20, m=0.18, p=0.0),
    6: dict(k=0.30, h=0.0, s=0.0, b=0.0, m=0.16, p=0.0),
}

nb = int(DUR / BEAT)
for b in range(nb):
    t = b * BEAT
    g = G[sec_of(t)]
    if sec_of(t) <= 5:
        kick(t, g=g["k"])
    if g["h"]:
        hat(t + BEAT / 2, g=g["h"])
        if sec_of(t) >= 3:
            hat(t + BEAT * 0.25, g=g["h"] * 0.5)
    if sec_of(t) == 4:
        hat(t + BEAT * 0.75, g=g["h"] * 0.9)          # fill de pico
    if g["s"] and b % 2 == 1:
        snare(t, g=g["s"])
    if g["b"]:
        root = CHORDS[(b // 4) % 4][0]
        bass(root, t, dur=BEAT * 0.9, g=g["b"])
    if g["p"] and b % 8 == 0:
        pad(CHORDS[(b // 4) % 4], t, dur=BEAT * 8, g=g["p"])
    # melodia
    if sec_of(t) == 1:
        if b % 2 == 0:
            tone(PENT[mel_rng.integers(0, 5)], t, g=g["m"])
    elif sec_of(t) <= 5:
        if mel_rng.random() < (0.9 if sec_of(t) in (3, 4) else 0.6):
            note = PENT[mel_rng.integers(0, 7)]
            if mel_rng.random() < 0.07:
                note *= 2 ** (1 / 12)                # nota "errada" cômica
            tone(note, t, g=g["m"])
        if sec_of(t) == 4 and b % 2 == 0:
            tone(PENT[mel_rng.integers(2, 7)] * 2, t, kind="sq",
                 g=g["m"] * 0.5, vib=1)
    else:
        if b % 4 == 0:
            tone(PENT[0] / 2, t, dur=0.5, g=g["m"] + 0.06)
        if abs(t - 58.0) < BEAT / 2:
            kick(t, g=0.7)

y = np.tanh(y * 1.1)
y *= 0.85 / np.abs(y).max()

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "src", "trilha.wav")
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((y * 32767).astype(np.int16).tobytes())
print("trilha ok:", out, round(len(y) / SR, 2), "s")
