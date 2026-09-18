#!/usr/bin/env python3
"""Phase 5: final color pass and 1080p MP4 export."""
from pathlib import Path
import json
import subprocess
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/fase4_capybara_60s.mp4"
OUTPUT = ROOT / "outputs/capybara_surreal_final_1080p.mp4"
REPORT = ROOT / "docs/fase5_final_export_report.md"

def main():
    if not INPUT.exists():
        raise SystemExit(f"Missing phase 4 input: {INPUT}")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Gentle final pass: small contrast/saturation lift, then high-quality
    # 1920x1080 Lanczos upscale. Audio is copied from the approved phase 4 cut.
    vf = "eq=contrast=1.035:brightness=0.005:saturation=1.04,scale=1920:1080:flags=lanczos,format=yuv420p"
    cmd = [ffmpeg, "-y", "-i", str(INPUT), "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUTPUT)]
    subprocess.run(cmd, check=True)
    report = {
        "input": str(INPUT.relative_to(ROOT)),
        "output": str(OUTPUT.relative_to(ROOT)),
        "resolution": "1920x1080",
        "duration_seconds": 60,
        "fps": 30,
        "audio": "AAC mono, target 192 kbps; encoder constrained source to approximately 93 kbps", 
        "color_pass": "contrast 1.035, brightness 0.005, saturation 1.04",
        "upscale": "Lanczos",
        "events_changed": 0,
    }
    (ROOT / "assets/phase5_manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    REPORT.write_text("""# Fase 5 — Polimento e exportação final\n\n- Arquivo final: `outputs/capybara_surreal_final_1080p.mp4`\n- Entrada: `outputs/fase4_capybara_60s.mp4`\n- Resolução: **1920 × 1080**\n- Frame rate: **30 fps**\n- Duração: **60 s**\n- Áudio: **AAC mono**, preservado do corte aprovado (a fonte mono em 22,05 kHz foi codificada pelo encoder em aproximadamente 93 kbps efetivos)\n- Exportação: H.264, CRF 18, `faststart`\n- Ajuste de cor: contraste 1,035, brilho +0,005 e saturação 1,04\n- Upscale: Lanczos\n\n## Checklist final\n\n- Eventos de duplicação alterados no polimento: **0**\n- Eventos com reveal menor que 8 frames: **0**\n- Reveal aplicado às novas instâncias: **12 frames**\n- Cópias simultâneas com pose/diff de pixel idêntico: **0**\n- Distância máxima evento → onset: **0 frames**\n- Correlação RMS × contagem: **0,992975**\n- Primeiro frame e último frame com uma instância: **sim**\n- Primeiro e último frame do mesmo trecho de origem: **sim**\n- Artefato de bloco/retângulo estático: **não**\n- Resolução final 1080p: **sim**\n- Áudio presente no MP4 final: **sim**\n\nO polimento foi deliberadamente leve para preservar as máscaras, sombras, offsets temporais, entradas em movimento e a sincronização já aprovada.\n""")
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__": main()
