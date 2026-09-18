#!/usr/bin/env python3
"""FASE 3 — sincronia de áudio (timing), sem aplicar ao vídeo ainda.

Macro: contagem-alvo por segundo derivada da curva RMS real (librosa).
Micro: cada ADD (e REMOVE) cai exatamente num onset detectado
(librosa.onset.onset_detect) -> distância <= 0.5 frame @30fps.

Saídas: assets/build/fase3/{events_fase3.json, curva_rms_count.png,
report_fase3.json}. Aprovar ANTES da Fase 4.
"""
import json
import os
import numpy as np
import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAV = os.path.join(ROOT, "assets", "src", "trilha.wav")
OUT = os.path.join(ROOT, "assets", "build", "fase3")
FPS = 30
NMAX = 9
os.makedirs(OUT, exist_ok=True)

y, sr = librosa.load(WAV, sr=None, mono=True)
dur = len(y) / sr

# ---------------- macro: RMS -> contagem-alvo
hop = 512
rms = librosa.feature.rms(y=y, hop_length=hop)[0]
t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
win = max(int(1.5 * sr / hop), 1)
smooth = np.convolve(rms, np.ones(win) / win, mode="same")
smn = (smooth - smooth.min()) / (smooth.max() - smooth.min())


def target_at(t):
    if t < 6 or t > 57:
        return 1
    return int(1 + round((NMAX - 1) * np.interp(t, t_rms, smn) ** 1.1))


# ---------------- micro: onsets
onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop)
onsets = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)

# ---------------- scheduler
events, count, last_add, last_rem = [], 1, -10.0, -10.0
for o in onsets:
    if o < 1.0:
        continue
    tgt = target_at(o)
    if count < tgt and o < 50 and (o - last_add) >= 0.6:
        fr = int(round(o * FPS))
        events.append(dict(type="ADD", t=round(o, 4), frame=fr,
                           onset_dist_frames=round(abs(o * FPS - fr), 3)))
        count += 1; last_add = o
    elif count > tgt and (o - last_rem) >= 0.45:
        fr = int(round(o * FPS))
        events.append(dict(type="REMOVE", t=round(o, 4), frame=fr,
                           onset_dist_frames=round(abs(o * FPS - fr), 3)))
        count -= 1; last_rem = o
# garantia: fechar em 1 instância até ~58.5s (usa onsets remanescentes)
k = 0
while count > 1 and k < len(onsets):
    o = onsets[-1 - k]; k += 1
    fr = int(round(o * FPS))
    if o < 50 or any(e["frame"] == fr for e in events):
        continue
    events.append(dict(type="REMOVE", t=round(float(o), 4), frame=fr,
                       onset_dist_frames=round(abs(o * FPS - fr), 3)))
    count -= 1
events.sort(key=lambda e: e["frame"])

# ---------------- métricas
adds = [e for e in events if e["type"] == "ADD"]
cnt = np.zeros(int(dur))
cur = 1; ei = 0
for s in range(int(dur)):
    while ei < len(events) and events[ei]["frame"] < (s + 0.5) * FPS:
        cur += 1 if events[ei]["type"] == "ADD" else -1
        ei += 1
    cnt[s] = cur
rms_sec = np.array([rms[(t_rms >= s) & (t_rms < s + 1)].mean()
                    for s in range(int(dur))])
rms_sec_n = (rms_sec - rms_sec.min()) / (rms_sec.max() - rms_sec.min())
corr = float(np.corrcoef(cnt[6:57], rms_sec_n[6:57])[0, 1])

report = {
    "duracao_s": round(dur, 2), "bpm": 112, "n_onsets": int(len(onsets)),
    "n_eventos": len(events), "n_adds": len(adds),
    "n_removes": len(events) - len(adds),
    "onset_dist_max_frames_ADD": float(
        max(e["onset_dist_frames"] for e in adds)),
    "onset_dist_max_frames_TODOS": float(
        max(e["onset_dist_frames"] for e in events)),
    "correlacao_count_x_rms_por_segundo": round(corr, 3),
    "count_max": int(cnt.max()), "count_final": int(cnt[-1]),
    "count_inicial": int(cnt[0]),
    "evento_0_s": events[0]["t"] if events else None,
}
with open(os.path.join(OUT, "report_fase3.json"), "w") as f:
    json.dump(report, f, indent=2)
with open(os.path.join(OUT, "events_fase3.json"), "w") as f:
    json.dump(events, f, indent=2)

# ---------------- plot RMS x contagem
fig, ax = plt.subplots(figsize=(12, 5))
ax.fill_between(t_rms, smn, alpha=0.35, color="tab:blue", label="RMS (norm.)")
ax.plot(t_rms, smn, color="tab:blue", lw=0.8)
ax2 = ax.twinx()
ts = np.arange(int(dur)) + 0.5
ax2.step(ts, cnt, where="mid", color="tab:red", lw=1.6,
         label="instâncias alvo/s")
for e in events:
    ax2.axvline(e["t"], color="green" if e["type"] == "ADD" else "orange",
                lw=0.6, alpha=0.7)
ax.set_xlabel("tempo (s)"); ax.set_ylabel("RMS normalizada")
ax2.set_ylabel("nº de instâncias")
ax.set_title("FASE 3 — curva RMS vs contagem de instâncias + eventos")
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "curva_rms_count.png"), dpi=110)

print(json.dumps(report, indent=2))
print("primeiros eventos:", events[:6])
print("últimos eventos:", events[-4:])
