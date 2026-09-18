#!/usr/bin/env python3
"""Prepare the public-domain capybara walking study for compositing.

Requires ImageMagick's `convert` command. The source is a 9-frame, 10 FPS
public-domain Muybridge study distributed by Wikimedia Commons. The plate's
white background is converted to transparency by luminance thresholding; this
is intentionally an explicit matting step, not a later visual filter.
"""
from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/capybara_walking_pd.gif"
OUT = ROOT / "assets/prepared"
FRAMES = OUT / "frames"
MASKS = OUT / "masks"
PREVIEW = ROOT / "previews/fase1_capybara_matte.gif"


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    if shutil.which("convert") is None:
        raise SystemExit("ImageMagick 'convert' is required")
    if not SOURCE.exists():
        raise SystemExit(f"Missing source: {SOURCE}")
    for directory in (FRAMES, MASKS):
        directory.mkdir(parents=True, exist_ok=True)
        for old in directory.glob("*.png"):
            old.unlink()
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    # Coalesce preserves the full canvas for every frame, which is important
    # for a stable anchor and for per-frame masks.
    run("convert", SOURCE, "-coalesce", FRAMES / "frame_%02d.png")
    frames = sorted(FRAMES.glob("frame_*.png"))
    if not frames:
        raise SystemExit("No frames extracted")

    for frame in frames:
        mask = MASKS / frame.name
        # Dark ink/animal becomes white foreground; paper becomes black.
        # The slight blur restores a soft alpha edge after thresholding.
        run(
            "convert", frame,
            "-colorspace", "Gray", "-threshold", "72%", "-negate",
            "-blur", "0x0.35", mask,
        )

    # A transparent RGBA cycle for later compositing.
    rgba_pattern = OUT / "rgba_%02d.png"
    for frame, mask in zip(frames, sorted(MASKS.glob("frame_*.png"))):
        out = OUT / f"rgba_{frame.stem.split('_')[-1]}.png"
        run("convert", frame, mask, "-alpha", "off", "-compose", "CopyOpacity", "-composite", out)

    # Human-review preview: a neutral field makes the matte boundary visible.
    preview_frames = []
    for rgba in sorted(OUT.glob("rgba_*.png")):
        review = OUT / f"review_{rgba.stem.split('_')[-1]}.png"
        run(
            "convert", "-size", "846x610", "xc:#a4bd88", rgba,
            "-compose", "Over", "-composite", review,
        )
        preview_frames.append(review)
    run("convert", "-delay", "10", "-loop", "0", *preview_frames, PREVIEW)
    # The single 0.9 s cycle is looped six times to create a reviewable 5.4 s
    # source clip while retaining the original 9-frame motion cycle and masks.
    matted_clip = OUT / "capybara_matted_5s.gif"
    run("convert", "-delay", "10", "-loop", "6", *sorted(OUT.glob("rgba_*.png")), matted_clip)
    for review in preview_frames:
        review.unlink()

    manifest = {
        "source": "Animal Locomotion Pl.746 - Capybara Walking.gif",
        "source_url": "https://commons.wikimedia.org/wiki/File:Animal_Locomotion_Pl.746_-_Capybara_Walking.gif",
        "license": "Public domain",
        "author": "Eadweard Muybridge; animation reconstruction by Avelludo",
        "frames": len(frames),
        "source_fps": 10,
        "cycle_duration_seconds": len(frames) / 10,
        "matting": {
            "method": "luminance threshold on white plate background, inverted to alpha, 0.35px edge blur",
            "mask_count": len(list(MASKS.glob("*.png"))),
            "mask_format": "8-bit grayscale PNG; white=subject, black=background",
        },
        "review_notes": [
            "Camera is fixed and the walking cycle is explicit.",
            "The source is a historical black-and-white study, not natural-color footage.",
            "This is suitable as a timing/matting prototype; a natural-color field clip can replace it after visual review without changing the pipeline contract.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Preview: {PREVIEW}")


if __name__ == "__main__":
    main()
