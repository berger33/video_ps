#!/usr/bin/env python3
"""Fase 4 — verificação da trilha e da sincronia som↔imagem.

Não confia no que o compositor "quis" fazer: mede no WAV gravado.

    1. tempo/beat tracking (librosa) → BPM detectado vs 128
    2. força de onset em cada degrau de N(t) vs linha de base (picos reais)
    3. energia por compasso correlacionada com N(t) (camadas sobem juntas)
    4. continuidade do loop: descontinuidade no ponto de costura
    5. alinhamento de cada pop de vídeo ao beat detectado mais próximo

Saída: assets/audio/fase4_analysis.json + assets/audio/fase4_score_qa.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_grid import (  # noqa: E402
    BAR,
    BEAT,
    BPM,
    DURATION,
    FPS,
    OUT_AUDIO,
    ROOT,
    STEPS,
    SWITCH_TIMES,
    scheduler_summary,
)

WAV = OUT_AUDIO / "coo_score.wav"


def n_at(t: float) -> int:
    n = STEPS[0][1]
    for ts, nv in STEPS:
        if t + 1e-9 >= ts:
            n = nv
    return n


def main() -> int:
    y, sr = sf.read(WAV, always_2d=True)
    mono = y.mean(axis=1).astype(np.float32)
    print(f"WAV: {len(mono)/sr:.3f} s @ {sr} Hz · {y.shape[1]}ch")

    # ---------------------------------------------------------------- tempo --
    tempo, beats = librosa.beat.beat_track(y=mono, sr=sr, units="time", trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    onsets = librosa.onset.onset_detect(y=mono, sr=sr, units="time", backtrack=True)
    oenv = librosa.onset.onset_strength(y=mono, sr=sr)
    times = librosa.times_like(oenv, sr=sr)
    print(f"tempo detectado = {tempo:.3f} BPM (alvo {BPM}) · beats={len(beats)} · onsets={len(onsets)}")

    # ------------------------------------------------- nos degraus de N(t) ---
    def onset_at(t: float, win: float = 0.09) -> float:
        m = (times >= t - win) & (times <= t + win)
        return float(oenv[m].max()) if m.any() else 0.0

    base = float(np.median(oenv))
    p90 = float(np.percentile(oenv, 90))
    step_rows = []
    for t_sw, n in STEPS[1:]:
        s = onset_at(t_sw)
        nearest = float(np.min(np.abs(np.array(beats) - t_sw))) if len(beats) else float("nan")
        step_rows.append(
            {
                "t": t_sw,
                "n": n,
                "onset_strength": round(s, 3),
                "onset_over_baseline": round(s / max(base, 1e-9), 2),
                "onset_over_p90": round(s / max(p90, 1e-9), 2),
                "nearest_beat_offset_s": round(nearest, 4),
                "nearest_beat_offset_frames": round(nearest * FPS, 2),
                "on_downbeat": abs(((t_sw / BAR) % 1.0)) < 1e-6,
            }
        )
    med_ratio = float(np.median([r["onset_over_baseline"] for r in step_rows]))
    max_off_frames = float(max(abs(r["nearest_beat_offset_frames"]) for r in step_rows))
    print(f"onset nos degraus: mediana {med_ratio:.2f}x baseline · desvio máx do beat {max_off_frames:.2f} frames")

    # ------------------------------------------------ energia vs N(t) --------
    hop = 512
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=hop)[0]
    rms_t = librosa.times_like(rms, sr=sr, hop_length=hop)
    bar_rms, bar_n = [], []
    for b in range(40):
        m = (rms_t >= b * BAR) & (rms_t < (b + 1) * BAR)
        if m.any():
            bar_rms.append(float(rms[m].mean()))
            bar_n.append(n_at(b * BAR + BAR * 0.5))
    corr = float(np.corrcoef(bar_rms, bar_n)[0, 1])
    print(f"correlação energia(RMS) por compasso × N(t) = {corr:+.3f}")

    # ------------------------------------------------------ loop / costura ---
    seam = float(np.abs(y[0] - y[-1]).max())
    local_slope = float(np.abs(np.diff(mono[:64])).max())
    tail_rms = float(np.sqrt(np.mean(mono[-int(0.25 * sr) :] ** 2)))
    head_rms = float(np.sqrt(np.mean(mono[: int(0.25 * sr)] ** 2)))
    loop_ok = seam <= max(3.0 * local_slope, 0.05)
    print(f"costura do loop: |x[0]-x[-1]|={seam:.4f} · slope local={local_slope:.4f} · ok={loop_ok}")

    # ----------------------------------------------------------- pops vídeo --
    pops = [t for t, _ in STEPS[1:]]
    pop_rows = []
    for t in pops:
        nearest = float(np.min(np.abs(np.array(beats) - t))) if len(beats) else float("nan")
        pop_rows.append(
            {
                "t": t,
                "nearest_beat_offset_s": round(nearest, 4),
                "nearest_beat_offset_frames": round(nearest * FPS, 2),
                "onset_over_baseline": round(onset_at(t) / max(base, 1e-9), 2),
            }
        )

    report = {
        "wav": str(WAV.relative_to(ROOT)),
        "duration_s": round(len(mono) / sr, 4),
        "sample_rate": sr,
        "tempo_detected": round(tempo, 3),
        "tempo_target": BPM,
        "tempo_error_bpm": round(tempo - BPM, 3),
        "beats_detected": int(len(beats)),
        "onsets_detected": int(len(onsets)),
        "onset_baseline": round(base, 4),
        "onset_p90": round(p90, 4),
        "steps": step_rows,
        "median_onset_over_baseline": round(med_ratio, 2),
        "max_beat_offset_frames": round(max_off_frames, 2),
        "rms_per_bar_vs_n_corr": round(corr, 3),
        "loop_seam_abs": round(seam, 6),
        "loop_local_slope": round(local_slope, 6),
        "loop_ok": bool(loop_ok),
        "tail_rms": round(tail_rms, 5),
        "head_rms": round(head_rms, 5),
        "pops": pop_rows,
        "all_steps_on_bar_grid": all(r["on_downbeat"] or abs(((r["t"] / BAR) % 1.0) - 0.5) < 1e-6 for r in step_rows),
    }
    (OUT_AUDIO / "fase4_analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"→ {OUT_AUDIO.relative_to(ROOT)}/fase4_analysis.json")

    # ------------------------------------------------------------ figura QA --
    fig, axes = plt.subplots(4, 1, figsize=(16, 12), constrained_layout=True)

    ax = axes[0]
    t_axis = np.arange(len(mono)) / sr
    ax.plot(t_axis[::50], mono[::50], lw=0.4, color="#2b6cb0")
    ax.set_title("COO · trilha 128 BPM (75 s) — forma de onda")
    ax.set_xlim(0, DURATION)
    for i, (t, n) in enumerate(STEPS):
        ax.axvline(t, color="#c53030", lw=0.8, alpha=0.7)
        ax.text(t, 0.92, f"N={n}", fontsize=7, color="#c53030", rotation=90, va="top")

    ax = axes[1]
    S = librosa.amplitude_to_db(np.abs(librosa.stft(mono, n_fft=2048, hop_length=512)), ref=np.max)
    img = librosa.display.specshow(S, sr=sr, hop_length=512, x_axis="time", y_axis="log", ax=ax, cmap="magma")
    ax.set_title("espectrograma — entrada das camadas por degrau")
    for t, n in STEPS:
        ax.axvline(t, color="#63b3ed", lw=0.8, alpha=0.75)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")

    ax = axes[2]
    ax.plot(times, oenv, lw=0.6, color="#2f855a", label="onset strength")
    for t in beats:
        ax.axvline(t, color="#a0aec0", lw=0.4, alpha=0.5)
    for t, n in STEPS[1:]:
        ax.axvline(t, color="#c53030", lw=1.2, alpha=0.9)
    ax.set_xlim(0, DURATION)
    ax.set_title("onsets vs beats detectados (cinza) vs degraus N(t) (vermelho)")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[3]
    bars_x = np.arange(40)
    ax.bar(bars_x - 0.2, np.array(bar_rms) / max(bar_rms), width=0.4, label="RMS por compasso (norm.)", color="#2b6cb0")
    ax.plot(bars_x + 0.2, np.array(bar_n) / max(bar_n), "o-", ms=3, lw=1.0, color="#c53030", label="N(t) (norm.)")
    ax.set_title(f"energia por compasso × contagem de cópias — correlação {corr:+.3f}")
    ax.legend(fontsize=8)
    ax.set_xlabel("compasso")

    fig.savefig(OUT_AUDIO / "fase4_score_qa.png", dpi=110)
    print(f"→ {(OUT_AUDIO / 'fase4_score_qa.png').relative_to(ROOT)}")
    print(json.dumps({k: v for k, v in report.items() if k not in ("steps", "pops")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
