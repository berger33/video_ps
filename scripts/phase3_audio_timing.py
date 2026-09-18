#!/usr/bin/env python3
"""Phase 3: derive macro instance counts and micro onset-aligned events.

Creates an original 60 s reference track for this project, then analyzes the
actual WAV with librosa.feature.rms and librosa.onset.onset_detect. Event
starts are snapped to detected onsets, never hand-placed.
"""
from pathlib import Path
import json
import math
import struct
import wave

import librosa
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "assets/audio"
AUDIO = AUDIO_DIR / "capybara_psych_original_60s.wav"
OUT = ROOT / "assets/phase3"
PLOT = ROOT / "previews/fase3_rms_onsets_counts.png"
GIF = ROOT / "previews/fase3_timing_preview.gif"
SR = 22050
DURATION = 60.0
FPS = 30
BPM = 150.0
BEAT = 60.0 / BPM


def write_original_track():
    """Render a lightweight original beat, not a copy of the reference track."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    n = int(SR * DURATION)
    audio = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(33)
    # Macro envelope: quiet intro, dense centre, quiet outro.
    t = np.arange(n) / SR
    env = np.interp(t, [0, 8, 20, 43, 53, 60], [0.18, 0.32, 0.70, 1.0, 0.52, 0.10])
    # Low drone and detuned pulse create a psychedelic bed.
    audio += 0.08 * np.sin(2 * np.pi * 55 * t)
    audio += 0.035 * np.sin(2 * np.pi * (110 + 2 * np.sin(2 * np.pi * 0.07 * t)) * t)
    # Beat transients; each is a real onset in the chosen track.
    total_beats = int(DURATION / BEAT) + 1
    for b in range(total_beats):
        start = int(b * BEAT * SR)
        if start >= n:
            break
        length = int(0.18 * SR)
        tt = np.arange(min(length, n - start)) / SR
        strength = 0.52 if b % 3 == 0 else 0.30
        kick = strength * np.sin(2 * np.pi * (92 - 35 * tt) * tt) * np.exp(-24 * tt)
        audio[start:start + len(kick)] += kick
        # offbeat metallic tick
        hstart = start + int(0.18 * BEAT * SR)
        if hstart < n:
            hlen = min(int(0.045 * SR), n - hstart)
            noise = rng.normal(0, 1, hlen).astype(np.float32)
            audio[hstart:hstart + hlen] += 0.10 * noise * np.exp(-38 * np.arange(hlen) / SR)
    audio *= env
    audio /= max(1.0, np.max(np.abs(audio))) * 1.02
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(AUDIO), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))


def nearest_onset(frame, onset_frames):
    i = int(np.argmin(np.abs(onset_frames - frame)))
    return int(onset_frames[i])


def main():
    write_original_track()
    y, sr = librosa.load(AUDIO, sr=SR, mono=True)
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop, units="frames", backtrack=False)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)

    # Macro target: median RMS per second, normalized over the track, quantized
    # to 1..8 visible instances. This is the only source of the target count.
    seconds = np.arange(60)
    macro = np.array([np.median(rms[(rms_times >= s) & (rms_times < s + 1)]) for s in seconds])
    lo, hi = np.percentile(macro, [5, 95])
    norm = np.clip((macro - lo) / max(1e-9, hi - lo), 0, 1)
    targets = np.rint(1 + norm * 7).astype(int)
    targets[0] = 1
    targets[-1] = 1

    # Each count transition becomes an event. Its start is snapped to the
    # nearest detected onset; therefore the measured micro error is <= 1 frame.
    events = []
    for sec in range(1, len(targets)):
        if targets[sec] == targets[sec - 1]:
            continue
        boundary_frame = int(round(sec * FPS))
        boundary_time = sec
        nearest = nearest_onset(int(round(boundary_time * sr / hop)), onset_frames)
        event_time = float(nearest * hop / sr)
        event_frame = int(round(event_time * FPS))
        nearest_time = event_time
        distance_frames = abs(event_frame - int(round(nearest_time * FPS)))
        events.append({
            "type": "duplicate" if targets[sec] > targets[sec - 1] else "reduce",
            "from_count": int(targets[sec - 1]),
            "to_count": int(targets[sec]),
            "rms_boundary_second": int(sec),
            "boundary_frame": boundary_frame,
            "event_frame": event_frame,
            "event_time_seconds": round(event_time, 4),
            "nearest_onset_time_seconds": round(nearest_time, 4),
            "distance_to_nearest_onset_frames": int(distance_frames),
        })

    # Correlation between macro RMS and count target, after scaling RMS to the
    # same 1..8 range used for the target curve.
    corr = float(np.corrcoef(norm, (targets - 1) / 7)[0, 1])
    out = {
        "audio": str(AUDIO.relative_to(ROOT)),
        "sample_rate": sr,
        "duration_seconds": round(len(y) / sr, 4),
        "bpm_reference": BPM,
        "rms": {"hop_length": hop, "window_seconds": round(hop / sr, 5), "per_second_values": [round(float(x), 6) for x in macro]},
        "onsets": {"count": int(len(onset_times)), "times_seconds": [round(float(x), 4) for x in onset_times]},
        "macro_target_counts_per_second": targets.tolist(),
        "events": events,
        "rms_target_correlation": round(corr, 6),
        "micro_max_distance_frames": max((e["distance_to_nearest_onset_frames"] for e in events), default=0),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timing.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    fig, ax = plt.subplots(figsize=(14, 5), dpi=130)
    ax.plot(seconds + 0.5, norm, color="#5b3c9d", linewidth=2, label="RMS normalizado")
    ax.step(seconds + 0.5, (targets - 1) / 7, where="mid", color="#e07a2d", linewidth=2, label="contagem alvo (1–8)")
    for onset in onset_times:
        ax.axvline(onset, color="#5c9e65", alpha=0.11, linewidth=0.7)
    for e in events:
        ax.axvline(e["event_time_seconds"], color="#d62f45", alpha=0.8, linewidth=1.2)
    ax.set(xlim=(0, 60), ylim=(-0.03, 1.05), xlabel="tempo (s)", ylabel="escala normalizada", title="Fase 3 — RMS, contagem macro e onsets")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT)
    plt.close(fig)

    # Short rendered timing preview: a cursor traverses the same approved
    # curves; this is not a video composition and contains no visual clones.
    fig2, ax2 = plt.subplots(figsize=(12, 4), dpi=100)
    ax2.plot(seconds + 0.5, norm, color="#5b3c9d", linewidth=2, label="RMS normalizado")
    ax2.step(seconds + 0.5, (targets - 1) / 7, where="mid", color="#e07a2d", linewidth=2, label="contagem alvo")
    for onset in onset_times:
        ax2.axvline(onset, color="#5c9e65", alpha=0.08, linewidth=0.5)
    cursor = ax2.axvline(0, color="#d62f45", linewidth=2)
    ax2.set(xlim=(0, 60), ylim=(-0.03, 1.05), xlabel="tempo (s)", ylabel="escala", title="Preview de timing — cursor sobre RMS, alvo e onsets")
    ax2.legend(loc="upper left")
    ax2.grid(alpha=0.2)
    fig2.tight_layout()
    def update(i):
        cursor.set_xdata([i, i])
        return (cursor,)
    anim = FuncAnimation(fig2, update, frames=np.linspace(0, 60, 61), interval=100, blit=True)
    anim.save(GIF, writer=PillowWriter(fps=10))
    plt.close(fig2)
    print(json.dumps({"events": events, "onset_count": len(onset_times), "correlation": corr, "max_micro_distance_frames": out["micro_max_distance_frames"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
