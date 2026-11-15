# Brand and image set prompt

**Status: delivered.** Every asset in the table below is in the repository (59 SVG masters and their PNGs),
plus the fonts in `assets/fonts/` and the frame coordinates in `assets/asset-manifest.json`. The screenshot
frames of the README heroes, the five Orca Cloud gallery images, install cards 2 to 4 and the three social
images hold real renders of the page (see CONTRIBUTING.md, Assets). Install card 1 shows OrcaSlicer's own
Plugins dialog, which the page cannot render, so its frame stays empty until a capture from OrcaSlicer exists.
The prompt below is kept as the brief for future changes.

Paste the prompt below into an image model (ChatGPT with image generation or similar). Ask for the
assets one at a time if it tries to cram everything into one image. Ask for SVG code for the mark,
wordmark, icons, diagrams and anything with text, so they stay sharp.

Where each asset goes in this repo:

| Asset | File |
|---|---|
| Symbol / app icon | `assets/embedder-icon.svg` (and `.png`) |
| Symbol, one colour | `assets/embedder-symbol-white.*`, `assets/embedder-symbol-dark.*` |
| Wordmark and lockup | `assets/embedder-wordmark.*`, `assets/embedder-wordmark-dark.*` |
| Micro marks | `assets/embedder-micro-{16,20,24}.*`, `assets/embedder-micro-dark-{16,20,24}.*` |
| Brand sheet | `assets/embedder-brand-sheet.*` |
| Tab icon (24x24) | `src/embedder/ui/icon.svg` |

Since 0.2.0 the page takes its UI icons from the shared Orca UI foundation and its empty-state picture
from the foundation's Embedder illustration, so the UI icon set and the empty-state spots described
below (items 7 and 8) are no longer shipped; they are kept here as the record of how the kit was made.

| Asset | File |
|---|---|
| README hero, light and dark | `assets/readme/embedder-hero-light.*`, `assets/readme/embedder-hero-dark.*` |
| Feature icons | `assets/features/feature-*.svg` |
| How it works diagram | `assets/diagrams/how-it-works-{light,dark}.*` |
| Pocket types diagram | `assets/diagrams/pocket-types-{light,dark}.*` |
| Orca Cloud frames and main images | `assets/orca-cloud/*` (each under 2 MB) |
| 512x512 store tile | `assets/orca-cloud/embedder-tile.*` |
| Install steps | `assets/install/embedder-install-0{1..4}.*` |
| Social images | `assets/social/embedder-social-{wide,square,vertical}.*` |
| GitHub social preview | `assets/social/embedder-social-preview.png` (Repository Settings > Social preview) |
| Release banner | `assets/releases/embedder-release-template.*` |

The related-plugin thumbnails (`docs/related-plugins/embedder-icon.png` 80x80 and
`embedder-preview.png` 560 px wide) are resized from the app icon and the dark hero, not generated.

---

```text
You are a senior brand designer. Create an original brand identity and image set for
"Embedder", an open-source plugin for OrcaSlicer (a 3D-printing slicer). The repository
name is "embedder".

WHAT IT DOES AND FOR WHOM
Embedder puts magnets and NFC stickers inside 3D prints. In a tab inside OrcaSlicer 2.5+,
the maker picks an insert size from a built-in list (disc and block magnets, round NFC
stickers, NFC cards) or saves their own, rotates the part in a 3D view and clicks the face
where the insert goes. Embedder cuts a pocket with the right clearance and adds a pause at
the exact layer before the pocket closes, so the printer stops, the maker drops the insert
in, and the print seals it inside. Pockets can also be left open for press-fit after
printing. It writes a new copy of the project and never changes the original. Audience:
hobbyist and prosumer makers. Personality: precise, calm, direct, "it just works". Not
corporate, not toy-like.

CONCEPT DIRECTION
Original. Express "something placed inside the layers": for example a cross-section of
three or four stacked printed layers with a pocket holding a solid disc, the layers above
closing over it; or a disc seated in a notch with a two-bar pause mark as the gap. A hint
of a radio arc may stand for NFC, but the symbol must also read without it. Do NOT use a
horseshoe magnet, lightning bolts or a north/south red-blue bar. Do not use or imitate the
NFC Forum N-Mark, or the logos, colours or icons of OrcaSlicer, Bambu Lab, Anycubic,
Snapmaker or any other brand. The sibling plugins already own these shapes, so avoid them:
a filament spool ring, four coloured bars over a U, a price tag.

HARD CONSTRAINTS
- Flat vector, strictly geometric, 8 px grid, consistent stroke weights. No photorealism,
  no 3D, no glow, no noise, no AI-art texture, no people or robots, no invented UI.
- The symbol must stay recognisable at 16x16 px and 20x20 px.
- Must work on dark and light backgrounds, and in one colour.
- Text in images must be spelled exactly "Embedder" for the wordmark and "embedder" for the
  repo name (lowercase). No other words unless I give them.
- Fonts must be free and open (Google Fonts); name them. Convert text to paths in SVG
  unless I say "live text".

PALETTE (family palette, use these values, do not invent others)
Primary (teal accent): #79d8c7 on dark, #00675b on light.
Dark: background #181c22, surface #222831, text #edf1f5, muted #b6c0cd, border #566273.
Light: background #f5f6f8, surface #ffffff, text #202731, muted #526171, border #ccd3dc.
Status (only where a state is shown): danger #b42318 light / #ffaaa4 dark; warning #805300
light / #f3cc70 dark; success #0b6b3a light / #7fdbab dark.
Insert accents: pick exactly two hues that stay clear of the teal, one for magnets and one
for NFC, each with a dark-background and a light-background value, and state their hex
codes. Use them only to tell the two insert types apart. Check that every text and
background pair reaches WCAG AA contrast.

DELIVERABLES (each as its own image, exact sizes, transparent background unless stated)
1. Brand sheet, 1600x1000, background #181c22: symbol, wordmark, horizontal lockup, palette
   swatches with hex codes, typography sample, and a do / don't row.
2. Symbol / app icon, full colour, 1024x1024 on a rounded-square tile (corner radius about
   22%), tile colour from the palette. Also as clean SVG code: viewBox 0 0 256 256, no
   embedded raster, no external fonts, no scripts.
3. Symbol, single colour, 1024x1024, two versions (white on transparent, #202731 on
   transparent), plus SVG code.
4. Wordmark and horizontal lockup (symbol + "Embedder"), 1000x280, two versions (for dark
   and for light backgrounds), plus SVG code with the text converted to paths.
5. Micro marks: the symbol redrawn for 16x16, 20x20 and 24x24 px, pixel-snapped, for dark
   and for light backgrounds. SVG code for each.
6. Tab icon: monochrome line icon on a 24x24 grid, 1.5 px strokes, round caps and joins,
   no fills thicker than the stroke, readable at 20 px. SVG code with width="24"
   height="24" viewBox="0 0 24 24", stroke="#FEFEFE", fill="none".
7. UI icon set, eleven SVGs: 24x24 grid, 1.5 px strokes, round caps and joins,
   stroke="currentColor", fill="none", no width/height attributes, consistent with the
   tab icon, readable at 16 px next to text. Each name and what it marks in the tab:
   - magnet: magnet presets and magnet pockets (a disc seen at an angle, not a horseshoe)
   - nfc: NFC presets and NFC pockets (a flat tag with one or two radio arcs)
   - pause: the pause height ("Pause at Z ... mm")
   - layers: layer height and cover thickness
   - fit-view: fit the part in the 3D view
   - add: add a pocket or save a preset
   - delete: remove a pocket or a saved preset
   - check: plan is valid, apply finished
   - warning: a warning on a pocket or a blocked plan
   - folder: open the new copy in OrcaSlicer
   - settings: clearances and defaults
   Save each as `src/embedder/ui/icons/<name>.svg`, with exactly these names.
8. Empty-state illustrations, three SVGs, 160x120, single-stroke line art, 2 px strokes,
   stroke="currentColor", secondary lines at 40% opacity, no fills, no text:
   no project loaded yet (`spot-no-project.svg`: a build plate with a dashed part outline),
   3D view unavailable (`spot-no-3d.svg`: a part with a crossed-out orbit arc; the tab then
   shows number fields instead), copy written and opened in the slicer (`spot-done.svg`:
   a layered part with a sealed insert and a check).
9. README hero, 1600x640, two versions (background #181c22 and #ffffff): left the lockup,
   the line "Magnet and NFC pockets for OrcaSlicer" and the line
   "Click a face · Pick a size · Pause at the right layer"; right an empty rounded
   16:10 frame, thin border, labelled nothing (a screenshot goes there).
10. Feature icons, seven 96x96 tiles (rounded square, corner radius 16, tinted palette
    background, no text), one SVG each, consistent. In this order, saved to these files:
    click-to-place in 3D (`assets/features/feature-3d-placement.svg`), magnet sizes
    (`feature-magnets.svg`), NFC stickers (`feature-nfc.svg`), automatic pause
    (`feature-auto-pause.svg`), embedded or open pockets (`feature-pocket-modes.svg`),
    your own sizes (`feature-custom-sizes.svg`), original project untouched
    (`feature-safe-copy.svg`).
11. How it works diagram, 1600x900, live text, light and dark. Boxes and arrows, left to
    right: "Your project" -> "Embedder" -> "New project copy" -> "Printer". Arrow labels
    exactly: "export", "pockets + pause", "slice & print". Under the last box:
    "pauses for each insert". Footer: "Your original project is never changed".
12. Pocket types diagram, 1600x900, live text, light and dark. Two side-by-side layer
    cross-sections. Left, titled "Embedded": an insert sealed under a thin cover, a
    dashed line at the layer below the cover labelled "pause here". Right, titled "Open":
    a pocket open at the surface, labelled "press-fit after printing". Small labels
    exactly: "cover", "clearance", "insert".
13. Orca Cloud store frames: five images, 1600x900 each, live text, headline and sub-line
    on the left 40%, an empty rounded 16:10 frame (thin border) on the right 60%:
    "Click where it goes" / "Rotate the part and click a face.";
    "Magnet sizes built in" / "Common disc and block magnets, with clearance.";
    "NFC stickers too" / "Round tags and cards under a thin cover.";
    "Pause at the right layer" / "The print stops right before the pocket closes.";
    "Your own sizes" / "Save any insert as a preset."
    Plus the main image (1600x900) and a square crop (900x900): lockup centred, the line
    "Magnets and NFC, built into your prints · OrcaSlicer 2.5+". Each file under 2 MB.
14. Install steps, four cards 800x500, live text, same template: big step number in the
    primary colour, title, one line, empty rounded screenshot frame (bottom 60%):
    1 "Install" / "File > Plugins > Install local plugin, then Activate."
    2 "Load" / "Open the Embedder tab and load your project."
    3 "Place" / "Pick a magnet or NFC size and click a face."
    4 "Print" / "Slice the new copy. The printer pauses for each insert."
15. Social images: (a) wide 1200x675, (b) square 1080x1080, (c) vertical 1080x1350 with the
    seven feature icons in a grid. Lockup, the line "Magnet and NFC pockets for
    OrcaSlicer" and the line "Free and open source".
16. GitHub social preview, 1280x640, background #181c22, lockup centred, the line
    "Magnets and NFC, built into your prints" below, a low-contrast pattern of stacked
    layer lines in the background; keep a 40 px safe margin.
17. Release banner template, 1280x320, background #181c22, live text: lockup on the left,
    placeholder "vX.Y.Z" on the right in the primary colour.
18. Plugin store tile, 512x512: the app icon with generous padding on a palette background.

OUTPUT FORMAT
For every deliverable: the image, then (where asked) the SVG code in a code block, then one
line on how it is meant to be used. For each image also list the text strings present, the
hex codes used and the contrast ratios of text. Finish with a short brand guide: clear
space, minimum sizes, colour usage, and three things never to do with the logo. After all
items, give me a single table: filename, size, background, text strings, where used.
```

## Screenshots

Any UI screenshot inside these images is a real capture of the Embedder tab in OrcaSlicer (or of
the built page `src/embedder/ui/app.html` open in a browser), not generated art. The image model must not draw fake UI. Wherever a screenshot belongs (hero, store
frames, install cards, social images), leave a clearly marked empty rounded frame, with a thin
border and no content, at the stated position and 16:10 ratio, so the renderer can place the real
page there.
