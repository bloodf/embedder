"""Finish the brand PNGs that are uploaded, posted or shown in the README, from the kit's exports:

1. Store, social and install images are made opaque on the background asset-manifest.json records for them
   (`intended_background`): a transparent image shows its lettering on whatever page it lands on, and neither
   Orca Cloud nor GitHub's two themes can be relied on. Identity marks, feature tiles and UI icons stay
   transparent; the README picks their light or dark variant.
2. The real page renders (node ui/tests/page/shots.mjs) go into the empty 16:10 screenshot frames, at the
   coordinates in the manifest. The SVG masters keep their empty frames.
3. docs/related-plugins/embedder-preview.png (560x224, shown by the sibling plugins) is resized from the
   finished dark README hero.

Running it again over its own output gives the same bytes: flattening an opaque image changes nothing and the
renders are pasted with a hard-edged mask, so every pasted pixel is replaced, never blended with the last run.

Pillow is a dev-only tool here, not a dependency of the plugin:
    uv run --no-project --with pillow python scripts/frames.py [shots-dir]      default shots-dir: dist/shots
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MAX_STORE_BYTES = 2_000_000          # Orca Cloud refuses images of 2 MB or more
SUPERSAMPLE = 4                      # where the rounded-corner mask is measured before it is cut to 0 or 255
OPAQUE = ("assets/orca-cloud/", "assets/social/", "assets/install/")   # shipped images that must not be transparent
PREVIEW = ("assets/readme/embedder-hero-dark.png", "docs/related-plugins/embedder-preview.png", (560, 224))
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


def manifest():
    return json.loads((ROOT / "assets" / "asset-manifest.json").read_text("utf-8"))["assets"]


def hex_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def rounded_mask(size, radius):
    """Hard-edged (0 or 255), so a second run replaces exactly the pixels the first one did."""
    big = Image.new("L", (size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * SUPERSAMPLE, fill=255)
    return big.resize(size, Image.LANCZOS).point(lambda v: 255 if v >= 128 else 0)


def save(image, target):
    image.save(ROOT / target, optimize=True)
    size = (ROOT / target).stat().st_size
    if "orca-cloud" in target and size >= MAX_STORE_BYTES:
        raise SystemExit("%s is %d bytes; Orca Cloud takes less than 2 MB" % (target, size))
    return size


def flatten(target, background):
    """The image composited over its intended background, as opaque RGB; an opaque image comes back unchanged."""
    image = Image.open(ROOT / target).convert("RGBA")
    base = Image.new("RGBA", image.size, hex_rgb(background) + (255,))
    return save(Image.alpha_composite(base, image).convert("RGB"), target)


def place(target, shot, frame):
    x, y, w, h = frame["x"] + INSET, frame["y"] + INSET, frame["width"] - 2 * INSET, frame["height"] - 2 * INSET
    radius = RADIUS.get(target.split("/")[1], 16) - INSET
    base = Image.open(ROOT / target)
    render = Image.open(shot).convert(base.mode).resize((w, h), Image.LANCZOS)
    base.paste(render, (x, y), rounded_mask((w, h), radius))
    return save(base, target)


def preview():
    source, target, size = PREVIEW
    return save(Image.open(ROOT / source).convert("RGB").resize(size, Image.LANCZOS), target)


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "shots"
    assets = manifest()
    for a in assets:
        if a["png"].startswith(OPAQUE) and a["background"] == "transparent":
            print("%-48s on %s %7d bytes" % (a["png"], a["intended_background"], flatten(a["png"], a["intended_background"])))
    known = {a["png"]: a["screenshot_frames"] for a in assets if a["screenshot_frames"]}
    for target, name in PLACES.items():
        (frame,) = known[target]
        if frame["aspect_ratio"] != "16:10":
            raise SystemExit("%s: frame is not 16:10" % target)
        print("%-48s <- %-16s %7d bytes" % (target, name, place(target, shots / (name + ".png"), frame)))
    for target in sorted(set(known) - set(PLACES)):
        print("%-48s    left empty" % target)
    print("%-48s <- %-16s %7d bytes" % (PREVIEW[1], PREVIEW[0].split("/")[-1], preview()))


if __name__ == "__main__":
    main()
