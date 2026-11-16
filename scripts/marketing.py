"""Finish the marketing art in assets/marketing/source/ into the images the store, the README and GitHub use.

Each source image has one empty rounded panel for a screenshot. For every export this script
  1. crops the source to the export's aspect ratio (centred) and scales it to the export size,
  2. finds the panel from the pixels: the area of the panel's own colour around a point inside it, closed by its frame,
  3. scales a real render of the built page (node ui/tests/page/shots.mjs) to cover that area and pastes it only there,
     so the frame, the rounded corners and the rest of the image stay as they were,
  4. writes the PNG and records it under "exports" in assets/asset-manifest.json, next to the "sources" it came from.
The tile has no panel: it is cropped to its rounded square, the white outside the square made transparent, and scaled.

Running it again gives the same bytes. Pillow is a dev-only tool here, not a dependency of the plugin:

    uv run --no-project --with pillow python scripts/marketing.py [shots-dir]      default shots-dir: dist/shots
"""

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "assets/marketing/source/"
MANIFEST = ROOT / "assets" / "asset-manifest.json"
DATE = "2026-11-16"                 # the day the art was made and exported; a re-run on another day changes nothing
MAX_BYTES = 2_000_000               # Orca Cloud refuses images of 2 MB or more
SEED = (0.75, 0.50)                 # a point inside the panel of every source, as a fraction of width and height
TOLERANCE = 40                      # how far a pixel may be from the seed's colour (summed over RGB) and still be panel
WIDE, SQUARE, SOCIAL, TILE = (1600, 900), (900, 900), (1280, 640), (512, 512)

# export -> (source, size, render). The render is the page state the image's headline is about; an export without a
# source is the render itself, scaled (the README's plain screenshots).
EXPORTS = {"assets/orca-cloud/embedder-tile.png": ("embedder-workshop-tile.png", TILE, None)}
for _lang in ("en", "pt-BR"):
    for _name, _source, _size, _shot in (
            ("orca-cloud/embedder-main", "cover" if _lang == "en" else "main", WIDE, "panel-main-dark"),
            ("orca-cloud/embedder-main-square", "main-square", SQUARE, "small-main-dark"),
            ("orca-cloud/embedder-feature-01-placement", "feature-01-placement", WIDE, "panel-placement-dark"),
            ("orca-cloud/embedder-feature-02-magnets", "feature-02-magnets", WIDE, "panel-magnets-dark"),
            ("orca-cloud/embedder-feature-03-nfc", "feature-03-nfc", WIDE, "panel-nfc-dark"),
            ("orca-cloud/embedder-feature-04-pause", "feature-04-pause", WIDE, "panel-pause-dark"),
            ("social/embedder-social-preview", "social-preview", SOCIAL, "small-main-dark"),
            ("readme/embedder-hero-dark", "hero-dark", WIDE, "panel-main-dark"),
            ("readme/embedder-hero-light", "hero-light", WIDE, "panel-main-light"),
            ("readme/embedder-screen-pockets-dark", None, (1440, 900), "screen-pockets-dark"),
            ("readme/embedder-screen-pockets-light", None, (1440, 900), "screen-pockets-light"),
            ("readme/embedder-screen-applied-dark", None, (960, 600), "screen-applied-dark"),
            ("readme/embedder-screen-applied-light", None, (960, 600), "screen-applied-light")):
        EXPORTS["assets/%s-%s.png" % (_name, _lang)] = (
            _source and "embedder-workshop-%s-%s.png" % (_source, _lang), _size, "%s-%s" % (_shot, _lang))


def panel(image):
    """The mask of the empty panel (255 inside) and its box. The frame is far from the panel's colour, so it stops the fill."""
    seed = (int(image.width * SEED[0]), int(image.height * SEED[1]))
    marker = (255, 0, 255)
    filled = image.copy()
    ImageDraw.floodfill(filled, seed, marker, thresh=TOLERANCE)
    mask = ImageChops.difference(image, filled).convert("L").point(lambda v: 255 if v else 0)
    # specks of texture inside the panel that the fill went around belong to it too: all that the outside cannot reach
    outside = ImageOps.expand(mask, 1, 0)
    ImageDraw.floodfill(outside, (0, 0), 128)
    mask = outside.crop((1, 1, outside.width - 1, outside.height - 1)).point(lambda v: 0 if v == 128 else 255)
    box = mask.getbbox()
    w, h = box[2] - box[0], box[3] - box[1]
    covered = mask.crop(box).histogram()[255] / (w * h)
    if not (0.2 * image.width < w < 0.6 * image.width and 0.8 < w / h < 1.25 and covered > 0.97):
        raise SystemExit("no panel found: box %s, %.3f of it filled" % (box, covered))
    return mask, box


def composite(source, size, shot):
    art = ImageOps.fit(Image.open(source).convert("RGB"), size, Image.LANCZOS)
    mask, box = panel(art)
    w, h = box[2] - box[0], box[3] - box[1]
    render = ImageOps.fit(Image.open(shot).convert("RGB"), (w, h), Image.LANCZOS, centering=(0.5, 0.0))
    layer = art.copy()
    layer.paste(render, box[:2])
    return Image.composite(layer, art, mask), "crop to %d:%d, scale to %dx%d, %s.png in the panel at %s" % (
        size[0] // _gcd(size), size[1] // _gcd(size), size[0], size[1], Path(shot).stem, ",".join(map(str, box)))


def _gcd(size):
    a, b = size
    while b:
        a, b = b, a % b
    return a


def tile(source, size):
    """The rounded square alone: what the white around it can reach from the corners becomes transparent, and so does
    the square's outermost 3 px, where the art blends into that white."""
    art = Image.open(source).convert("RGB")
    reach = ImageOps.expand(art, 1, (255, 255, 255))
    ImageDraw.floodfill(reach, (0, 0), (255, 0, 255), thresh=120)
    inside = ImageChops.difference(ImageOps.expand(art, 1, (255, 255, 255)), reach).convert("L").point(lambda v: 0 if v else 255)
    inside = inside.crop((1, 1, inside.width - 1, inside.height - 1)).filter(ImageFilter.MinFilter(7))
    box = inside.getbbox()
    side = max(box[2] - box[0], box[3] - box[1])
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    square = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    out = art.convert("RGBA")
    out.putalpha(inside)
    return out.crop(square).resize(size, Image.LANCZOS), "crop to the rounded square at %s, white outside it made transparent, scale to %dx%d" % (
        ",".join(map(str, square)), size[0], size[1])


def screenshot(shot, size):
    return Image.open(shot).convert("RGB").resize(size, Image.LANCZOS), "scale to %dx%d" % size


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "shots"
    records = []
    for target, (source, size, shot) in EXPORTS.items():
        if not shot:
            image, operation = tile(ROOT / SOURCE / source, size)
        elif not source:
            image, operation = screenshot(shots / (shot + ".png"), size)
        else:
            image, operation = composite(ROOT / SOURCE / source, size, shots / (shot + ".png"))
        image.save(ROOT / target, optimize=True)
        nbytes = (ROOT / target).stat().st_size
        if nbytes >= MAX_BYTES:
            raise SystemExit("%s is %d bytes; Orca Cloud takes less than 2 MB" % (target, nbytes))
        records.append({"file": target, "source": SOURCE + source if source else "ui/tests/page/shots.mjs: %s.png" % shot,
                        "operation": operation, "width": size[0], "height": size[1], "bytes": nbytes, "date": DATE})
        print("%-58s %4dx%-4d %7d bytes" % (target, size[0], size[1], nbytes))
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    manifest["sources"] = [{"file": SOURCE + f.name, "width": Image.open(f).width, "height": Image.open(f).height,
                            "bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
                           for f in sorted((ROOT / SOURCE).glob("*.png"))]
    manifest["exports"] = records
    MANIFEST.write_text(json.dumps(manifest, indent=2), "utf-8")   # the layout the brand kit wrote it in


if __name__ == "__main__":
    main()
