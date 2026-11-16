<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme/embedder-hero-dark.png">
    <img src="assets/readme/embedder-hero-light.png" alt="Embedder: magnet and NFC pockets for OrcaSlicer" width="800">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/bloodf/embedder/actions/workflows/ci.yml"><img src="https://github.com/bloodf/embedder/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/bloodf/embedder/releases/latest"><img src="https://img.shields.io/github/v/release/bloodf/embedder" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/bloodf/embedder" alt="License: GPL-3.0"></a>
  <img src="https://img.shields.io/badge/OrcaSlicer-2.5%2B-informational" alt="OrcaSlicer 2.5+">
</p>

# Embedder

Embedder is an OrcaSlicer 2.5 plugin for putting magnets and NFC stickers inside 3D prints. You pick
an insert size, click the face of the part where it goes, and Embedder cuts a pocket with the right
clearance. For a pocket that is sealed inside the print, it also adds a pause at the layer where the
cavity is about to close, so you can drop the insert in before the printer covers it.

It works on a copy of your project. Your original project is never changed. The plugin needs no extra
Python packages and does not use the network.

<p align="center">
  <img src="assets/features/feature-3d-placement.svg" width="72" alt="Click to place in 3D">
  <img src="assets/features/feature-magnets.svg" width="72" alt="Magnet sizes">
  <img src="assets/features/feature-nfc.svg" width="72" alt="NFC stickers">
  <img src="assets/features/feature-auto-pause.svg" width="72" alt="Automatic pause">
  <img src="assets/features/feature-pocket-modes.svg" width="72" alt="Embedded or open pockets">
  <img src="assets/features/feature-custom-sizes.svg" width="72" alt="Your own sizes">
  <img src="assets/features/feature-safe-copy.svg" width="72" alt="Original project untouched">
</p>

<!-- related-plugins:start -->
## Explore the other plugins

Complete your OrcaSlicer workflow: arrange, price, manage filament and print. Each plugin works on its own; installed together they share data where it helps.

<table>
  <tr>
    <td width="33%" valign="top">
      <a href="https://cloud.orcaslicer.com/p/5bf381fd42d4"><img src="docs/related-plugins/orca_organizer-icon.png" width="40" height="40" alt="Organizer"></a>
      <h3><a href="https://cloud.orcaslicer.com/p/5bf381fd42d4">Organizer</a></h3>
      <a href="https://cloud.orcaslicer.com/p/5bf381fd42d4"><img src="docs/related-plugins/orca_organizer-preview.jpg" width="280" alt="Organizer: preview"></a>
      <p>Arrange objects by their real outline and fill a build plate with more copies.</p>
      <p><a href="https://cloud.orcaslicer.com/p/5bf381fd42d4">Install from Orca Cloud →</a><br><a href="https://github.com/bloodf/orca_organizer">Source on GitHub →</a></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://cloud.orcaslicer.com/p/521c07cf6de2"><img src="docs/related-plugins/orca_print_calculator-icon.png" width="40" height="40" alt="Orca Print Calculator"></a>
      <h3><a href="https://cloud.orcaslicer.com/p/521c07cf6de2">Orca Print Calculator</a></h3>
      <a href="https://cloud.orcaslicer.com/p/521c07cf6de2"><img src="docs/related-plugins/orca_print_calculator-preview.png" width="280" alt="Orca Print Calculator: preview"></a>
      <p>Price every build plate: Spoolman filament cost, energy, labor, fees and a suggested selling price.</p>
      <p><a href="https://cloud.orcaslicer.com/p/521c07cf6de2">Install from Orca Cloud →</a><br><a href="https://github.com/bloodf/orca_print_calculator">Source on GitHub →</a></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://cloud.orcaslicer.com/p/50c35dcbd6f3"><img src="docs/related-plugins/spooler-icon.png" width="40" height="40" alt="Spooler"></a>
      <h3><a href="https://cloud.orcaslicer.com/p/50c35dcbd6f3">Spooler</a></h3>
      <a href="https://cloud.orcaslicer.com/p/50c35dcbd6f3"><img src="docs/related-plugins/spooler-preview.png" width="280" alt="Spooler: preview"></a>
      <p>Your Spoolman spools and filament presets in OrcaSlicer, with what is left on each spool.</p>
      <p><a href="https://cloud.orcaslicer.com/p/50c35dcbd6f3">Install from Orca Cloud →</a><br><a href="https://github.com/bloodf/spooler">Source on GitHub →</a></p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <a href="https://cloud.orcaslicer.com/p/55b8c347d443"><img src="docs/related-plugins/u1control-icon.svg" width="40" height="40" alt="U1 Control"></a>
      <h3><a href="https://cloud.orcaslicer.com/p/55b8c347d443">U1 Control</a></h3>
      <a href="https://cloud.orcaslicer.com/p/55b8c347d443"><img src="docs/related-plugins/u1control-preview.png" width="280" alt="U1 Control: preview"></a>
      <p>The Snapmaker U1 in OrcaSlicer: print setup, camera, toolheads, RFID, Spoolman and a file manager.</p>
      <p><a href="https://cloud.orcaslicer.com/p/55b8c347d443">Install from Orca Cloud →</a><br><a href="https://github.com/bloodf/u1control">Source on GitHub →</a></p>
    </td>
    <td width="33%" valign="top">
      <a href="https://cloud.orcaslicer.com/p/59c786285255"><img src="docs/related-plugins/kobracontrol-icon.svg" width="40" height="40" alt="Kobra Control"></a>
      <h3><a href="https://cloud.orcaslicer.com/p/59c786285255">Kobra Control</a></h3>
      <a href="https://cloud.orcaslicer.com/p/59c786285255"><img src="docs/related-plugins/kobracontrol-preview.png" width="280" alt="Kobra Control: preview"></a>
      <p>The Anycubic Kobra X in OrcaSlicer: Print and Send, the Device tab, ACE slots and a dashboard.</p>
      <p><a href="https://cloud.orcaslicer.com/p/59c786285255">Install from Orca Cloud →</a><br><a href="https://github.com/bloodf/kobracontrol">Source on GitHub →</a></p>
    </td>
    <td width="33%" valign="top"></td>
  </tr>
</table>

Illustrative project artwork. [Credits and licenses](docs/related-plugins/README.md).
<!-- related-plugins:end -->

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/how-it-works-dark.png">
  <img src="assets/diagrams/how-it-works-light.png" alt="Your project goes to Embedder, which writes a new project copy with pockets and pauses for the printer">
</picture>

OrcaSlicer 2.5 plugins cannot read or change the geometry of the open project, and they cannot draw
in Orca's 3D view. So Embedder does the work on a file:

1. **Load project** asks OrcaSlicer to export a copy of the open project (the current plate) into the
   plugin's storage folder. Embedder reads that copy and shows the parts in its own 3D view.
2. You pick an insert and click a face. Embedder works out the pocket and shows it on the part.
3. **Apply** writes a new project file next to the copy, with each pocket added as a negative part
   and, for embedded pockets, a pause on the layer slider. Then it asks OrcaSlicer to open that file.

The file that opens is a new project. To keep it, use **Save As**. The project you started from is
not touched. If you want to keep working on the new file, do it there; to change the pockets,
load that project again and re-apply.

## Features

### Click a face, pick a size

The Embedder tab has a 3D view of the objects on the current plate. Rotate the part, choose an
insert and a pocket type, and click the face. The pocket appears in the view before anything is
written. Clearance and cover thickness are settings you can tune for your printer.

Tick **Centre on the face** to put the pocket in the middle of the flat face you click instead of at the
exact spot, which is what you want for a lid, a base or a tile. The middle is taken over the whole flat
face around the click; when that middle falls outside the face (a ring, a U shape), the clicked spot is
kept.

To move a pocket, drag it in the 3D view: it slides over the surface and turns to the face under it.
Click a pocket, or its row under **Pockets to add**, to select it. The form then changes that pocket in
place (size, type, rotation, cover), the arrow keys step it 0.5 mm along its face (5 mm with Shift), R
turns it 15°, and Delete removes it. A pocket that an earlier Apply already wrote stays where it is: tick it
for removal and place it again.

Below the list of pockets, Embedder shows the inserts to have ready before you print, for example
"2 x 6x3 magnet, 1 x 25 mm NFC sticker". Open pockets count too, and so does every copy of an object.

### Embedded and open pockets

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/pocket-types-dark.png">
  <img src="assets/diagrams/pocket-types-light.png" alt="Embedded: the insert is sealed under a thin cover and the print pauses at the layer below the cover. Open: the pocket is open at the surface for press-fit after printing">
</picture>

| | Embedded | Open |
|---|---|---|
| Where | flat faces (top or bottom) and upright side faces | any face, including tilted ones |
| Shape | a vertical cavity, closed by the print itself | a hexagon or a vented box cut into the surface |
| Pause | yes, one layer before the cavity closes | none |
| Fit | the insert is dropped in during the pause and sealed in | pressed in after printing |

- **Embedded on a flat face:** a disc gets a hexagon, a block gets a box with corner vents. The pocket
  sits under a cover of material (1.0 mm for magnets, 0.6 mm for NFC by default).
- **Embedded on a side face:** the insert stands on edge behind the wall, in a vertical slot
  (diameter by thickness by diameter for a disc), and is dropped in from above.
- **Open:** cut along the inward direction of the face, flush with the surface.

Every pocket lets air and spare glue out, so the insert goes all the way down:

- **A disc sits in a hexagon.** It is as wide across the flats as a round pocket would be, so the six
  flats hold the disc and the six corners stay open.
- **A block sits in a box with a 1 mm round vent on each corner.** The box itself is the size of the
  block plus the clearance.
- **A side slot has the same corner vents.** The two next to the wall open along the wall only, so the
  wall keeps the thickness you asked for.

The tab shows both sizes: the fit, and how wide the pocket is with its corners or vents. A pocket added by
an older version keeps its shape until you remove it and add it again.

### The pause

For an embedded pocket the cavity floor and top are snapped to the layer grid, and the pause goes on
the first layer above the cavity top, so it runs just before the cover starts. Pockets that end at the
same height share one pause. The pause is OrcaSlicer's own per-layer pause: you see it on the layer
slider in the preview, and the printer runs the profile's pause G-code (`machine_pause_gcode`). Embedder
never picks M600 or any other command itself.

### Built-in insert presets

- **Disc magnets** (diameter x thickness, mm): 3x1, 4x2, 5x1, 5x2, 5x3, 6x2, 6x3, 8x2, 8x3, 10x2,
  10x3, 10x5, 12x3, 15x3, 20x3
- **Block magnets** (length x width x thickness, mm): 10x5x2, 10x5x3, 20x10x2, 20x10x5
- **Round NFC stickers** (diameter, 0.4 mm deep): 10, 13, 20, 22, 25, 30, 38 mm
- **NFC coins:** 25x1 and 30x2 mm
- **NFC card:** 85.6 x 54 x 0.9 mm
- **Your own:** any disc or block, saved by name and kept between sessions

### Warnings and limits

Embedded pockets are blocked, with the reason shown, when:

- the print sequence is "by object" (OrcaSlicer ignores layer pauses in that mode)
- the printer profile has no pause G-code
- the profile uses a raft, or the object has variable layer height or layer ranges
- copies of the object sit on another plate (the pause is written for one plate)
- the face is tilted (open pockets still work there)
- the pocket would reach below the bed, would have no printed layer under it, or the pause would fall
  before the second layer

When the object's copies differ by more than a Z rotation and a move, no pocket is offered at all: one
negative part cuts every copy.

Embedder warns, without blocking, when the cover is thin (less than two layers, or under 0.8 mm for a
side wall), when the pocket reaches outside the part, when an NFC pocket is within 10 mm of a magnet
pocket (the tag may not read), and when another custom G-code already sits on the pause layer (Embedder
leaves it alone and adds no pause there). That last warning shows as soon as you place the pocket, not only
after Apply.

Things to know:

- **Magnets can jump.** A magnet may snap to a steel nozzle or the print head. Put each magnet in with
  the right side up (check the pole before you place it), and look before you resume the print.
- **Changing the layer height after Apply moves the layers.** The pause is tied to a height. If you
  change the layer height in the new project, load it again and re-apply.
- **Cut objects with connectors** and **bare mesh objects** without a parts list are not supported, and
  neither is a hand-made 3MF without OrcaSlicer's part list (`model_settings.config`). Embedder says so when
  you click, before anything is written. Save the project from OrcaSlicer once to add the part list.
- **Old copies are cleaned up.** Each Apply writes a new copy into the plugin folder. Embedder always keeps
  the newest copy of each project and every copy written since OrcaSlicer started, since OrcaSlicer may
  have those open. After each Apply it deletes older copies beyond the 10 most recent, and any older than
  30 days. **Settings > Old project copies** shows how many can go and how much space they take, and
  **Clear old copies** deletes them all at once (after asking). Files you put in the folder yourself are
  never touched.
- **One Apply per load.** After Apply the new copy is the project; open it and load it again to add more.
- **Linux:** "Open in OrcaSlicer" starts the OrcaSlicer executable (or the AppImage) with the file, which
  may open a second OrcaSlicer window instead of reusing the running one. Close the old window, or open
  the file from File > Open.
- Embedder's pockets and pauses are marked (the part names start with "Embedder", the pause text with
  "Embedder:"). Loading a project that already has them lists them so you can remove or re-apply them.
  Pockets and pauses you made by hand are left alone.

## Requirements

- OrcaSlicer 2.5.0 or newer.
- A printer profile with a pause G-code (most have one) for embedded pockets.

## Install

Subscribe to Embedder on Orca Cloud, or download `embedder_any.whl` from the
[latest release](../../releases/latest). To build the wheel from the source instead:

```sh
python3 scripts/build.py     # writes dist/embedder_any.whl
```

For a downloaded or built wheel, use **File > Plugins > Install local plugin** in OrcaSlicer, pick the
wheel, then tick **Activate**. Allow the background thread when OrcaSlicer asks. The **Embedder** tab
appears next to Prepare, Preview and Device.

<p>
  <img src="assets/install/embedder-install-01.png" width="400" alt="Step 1, Install: File > Plugins > Install local plugin, then Activate">
  <img src="assets/install/embedder-install-02.png" width="400" alt="Step 2, Load: open the Embedder tab and load your project">
  <img src="assets/install/embedder-install-03.png" width="400" alt="Step 3, Place: pick a magnet or NFC size and click a face">
  <img src="assets/install/embedder-install-04.png" width="400" alt="Step 4, Print: slice the new copy; the printer pauses for each insert">
</p>

## Usage

1. Open your project in OrcaSlicer and pick the plate with the part.
2. Open the **Embedder** tab and press **Load project**.
3. Choose an insert from the list, or enter your own size. Choose **Embedded** or **Open**.
4. Rotate the part and click the face where the insert goes. Add more pockets the same way.
5. Press **Apply**. OrcaSlicer opens the new project. Use **Save As** to keep it.
6. Slice. In the preview, the pause shows on the layer slider just above each embedded pocket.
7. Start the print. When it pauses, put the insert in and resume.

## Privacy and security

Embedder does not use the network and has no cloud service. It reads the project copy OrcaSlicer
exports and writes new files only in its own storage folder. See [SECURITY.md](SECURITY.md).

## Documentation

- [Architecture](docs/architecture.md): modules, the page protocol and the pause rule
- [3MF notes](docs/3mf.md): how pockets and pauses are written into the project file
- [Releasing](docs/release.md): tags, GitHub release and Orca Cloud publishing
- [Orca Cloud description](docs/orca-cloud-description.md) and [related plugins block](docs/orca-cloud-related.md)
- [Brand image prompt](docs/brand-images-prompt.md)
- [Notice](NOTICE.md), [Contributing](CONTRIBUTING.md), [Changelog](CHANGELOG.md), [Code of conduct](CODE_OF_CONDUCT.md) and [Security](SECURITY.md)

Questions and ideas: [Discussions](https://github.com/bloodf/embedder/discussions). Bugs: [Issues](https://github.com/bloodf/embedder/issues).

## Credits

The 3MF reading and writing is adapted from [orca_organizer](https://github.com/bloodf/orca_organizer)
(GPL-3.0). The 3D view uses [three.js](https://threejs.org) (MIT). The page uses Vue and PrimeVue
through the shared Orca UI foundation 4.0.1, with its Lucide icons (ISC) and the Manrope typeface (SIL OFL 1.1). See [NOTICE.md](NOTICE.md).

The brand art and its fonts are credited in [NOTICE.md](NOTICE.md); the brief is
[docs/brand-images-prompt.md](docs/brand-images-prompt.md).

Embedder is an independent project and is not made or supported by the OrcaSlicer team.

License: [GPL-3.0-only](LICENSE).
