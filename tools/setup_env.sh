#!/usr/bin/env bash
# Setup idempotente do ambiente do projeto "Pombo//Protocolo".
#
# Por que existe: neste sandbox rodamos CPU-only (2 vCPU / 3 GB) e os pacotes
# instalados fora do workspace NAO persistem entre turnos, e o apt esta
# bloqueado (espelhos Debian inacessiveis; PyPI funciona). Entao:
#   - criamos um venv DENTRO do workspace (tools/venv, fora do Git)
#   - instalamos ffmpeg via wheel imageio-ffmpeg (binario estatico) e o
#     expomos como tools/bin/ffmpeg e tools/bin/ffprobe
#   - instaladas as libs de imagem/video usadas no pipeline
#
# Uso:  bash tools/setup_env.sh [--com-rembg]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/tools/venv"
BIN="$ROOT/tools/bin"
WITH_REMBG=0
[ "${1:-}" = "--com-rembg" ] && WITH_REMBG=1

mkdir -p "$BIN"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[setup] criando venv em $VENV"
  python3 -m venv "$VENV"
fi
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "[setup] atualizando pip/setuptools"
"$PIP" install --quiet --upgrade pip setuptools wheel

echo "[setup] instalando libs base"
"$PIP" install --quiet \
  numpy pillow imageio imageio-ffmpeg \
  opencv-python-headless scipy soundfile

if [ "$WITH_REMBG" = "1" ]; then
  echo "[setup] instalando rembg (matting por frame) + onnxruntime"
  "$PIP" install --quiet "rembg[cpu]" onnxruntime
fi

echo "[setup] linkando ffmpeg/ffprobe estaticos"
EXE="$("$PY" -c 'import imageio_ffmpeg,sys; sys.stdout.write(imageio_ffmpeg.get_ffmpeg_exe())')"
cp -f "$EXE" "$BIN/ffmpeg"
cp -f "$EXE" "$BIN/ffprobe"   # imageio-ffmpeg entrega um binario ffmpeg completo (com ffprobe embutido via -i)
chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"

echo "[setup] versoes:"
"$PY" -c "import numpy, PIL, cv2, scipy, imageio_ffmpeg; print('  numpy', numpy.__version__, '| pillow', PIL.__version__, '| opencv', cv2.__version__)"
"$BIN/ffmpeg" -version 2>/dev/null | head -1 | sed 's/^/  /'
echo "[setup] OK -> use $BIN/ffmpeg e $PY"
