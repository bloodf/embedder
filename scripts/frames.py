"""Place the real page renders (node ui/tests/page/shots.mjs) into the empty 16:10 screenshot frames of the brand
PNGs, at the frame coordinates recorded in assets/asset-manifest.json. The SVG masters keep their empty frames.

Pillow is a dev-only tool here, not a dependency of the plugin:
    uv run --no-project --with pillow python scripts/frames.py [shots-dir]      default shots-dir: dist/shots
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MAX_STORE_BYTES = 2_000_000          # Orca Cloud refuses images of 2 MB or more
SUPERSAMPLE = 4                      # smooth rounded corners on the mask
# brand PNG -> render. A frame without a genuine render of its step is left empty (install-01 shows OrcaSlicer's
# own plugin dialog, which the page cannot render).
PLACES = {
    "assets/readme/embedder-hero-dark.png": "placement-dark",
    "assets/readme/embedder-hero-light.png": "placement-light",
    "assets/orca-cloud/embedder-01-placement.png": "placement-dark",
    "assets/orca-cloud/embedder-02-magnets.png": "magnets-dark",
    "assets/orca-cloud/embedder-03-nfc.png": "nfc-dark",
    "assets/orca-cloud/embedder-04-pause.png": "pause-dark",
    "assets/orca-cloud/embedder-05-custom-sizes.png": "custom-dark",
    "assets/install/embedder-install-02.png": "load-light",
    "assets/install/embedder-install-03.png": "place-light",
    "assets/install/embedder-install-04.png": "applied-light",
    "assets/social/embedder-social-wide.png": "placement-dark",
    "assets/social/embedder-social-square.png": "pause-dark",
    "assets/social/embedder-social-vertical.png": "placement-dark",
}
INSET = 2                            # inside the frame's 2 px border
RADIUS = {"install": 12}             # frame corner radius by folder; 16 elsewhere (the SVG masters' rx)


def frames():
    manifest = json.loads((ROOT / "assets" / "asset-manifest.json").read_text("utf-8"))
    return {a["png"]: a["screenshot_frames"] for a in manifest["assets"] if a["screenshot_frames"]}


def rounded_mask(size, radius):
    big = Image.new("L", (size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * SUPERSAMPLE, fill=255)
    return big.resize(size, Image.LANCZOS)


def place(target, shot, frame):
    x, y, w, h = frame["x"] + INSET, frame["y"] + INSET, frame["width"] - 2 * INSET, frame["height"] - 2 * INSET
    radius = RADIUS.get(target.split("/")[1], 16) - INSET
    base = Image.open(ROOT / target).convert("RGBA")
    render = Image.open(shot).convert("RGBA").resize((w, h), Image.LANCZOS)
    base.paste(render, (x, y), rounded_mask((w, h), radius))
    base.save(ROOT / target, optimize=True)
    size = (ROOT / target).stat().st_size
    if "orca-cloud" in target and size >= MAX_STORE_BYTES:
        raise SystemExit("%s is %d bytes; Orca Cloud takes less than 2 MB" % (target, size))
    return size


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "shots"
    known = frames()
    for target, name in PLACES.items():
        (frame,) = known[target]
        if frame["aspect_ratio"] != "16:10":
            raise SystemExit("%s: frame is not 16:10" % target)
        print("%-48s <- %-16s %7d bytes" % (target, name, place(target, shots / (name + ".png"), frame)))
    for target in sorted(set(known) - set(PLACES)):
        print("%-48s    left empty" % target)


if __name__ == "__main__":
    main()
