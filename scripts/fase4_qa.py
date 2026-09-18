#!/usr/bin/env python3
"""QA visual da FASE 4: contact sheet de momentos-chave + checagem de loop
(frame 0 vs ~frame 1799: 1 instância, mesma pose/posição) + probe de áudio."""
import os
import subprocess
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "assets", "build", "fase4")

gif = Image.open(os.path.join(D, "review_fase4.gif"))   # 15fps, 1/3 esc.
frames = {}
try:
    while True:
        frames[gif.tell()] = gif.convert("RGB")
        gif.seek(gif.tell() + 1)
except EOFError:
    pass
# gif tem 60 frames (1 por segundo do vídeo)
marks = [0, 3, 8, 15, 25, 42, 46, 52, 57, 59]
sel = []
for t in marks:
    i = min(t, len(frames) - 1)
    sel.append((t, frames[i]))
w, h = sel[0][1].size
cols = 5
rows = (len(sel) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * h))
for n, (t, im) in enumerate(sel):
    sheet.paste(im, ((n % cols) * w, (n // cols) * h))
sheet.save(os.path.join(D, "_qa_sheet.png"))
print("sheet ok", len(frames), "frames gif")

# loop: 1 instância nas pontas + mesma posição -> diff entre f0 e f~59.5
f0 = np.array(frames[0]); f1 = np.array(frames[len(frames) - 1])
print("diff pontas (mean abs):", round(float(np.abs(f0.astype(int)
      - f1.astype(int)).mean()), 2))

# áudio no mp4 final
import imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe()
probe = ff.replace("ffmpeg", "ffprobe") if "ffprobe" in ff else None
r = subprocess.run([ff, "-i", os.path.join(D, "video_ps_fase4.mp4")],
                   capture_output=True, text=True)
print("STREAMS:", [l for l in r.stderr.splitlines()
                   if "Stream" in l or "Duration" in l])
