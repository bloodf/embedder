# Notice

Embedder is licensed under the GNU General Public License v3.0 only (see [LICENSE](LICENSE)).

## Upstream projects

- **3MF handling** is adapted from [orca_organizer](https://github.com/bloodf/orca_organizer)
  (GPL-3.0, same author): reading an Orca 3MF package, following `p:path` components, transforms and
  plates, and the export, edit, reopen route through `plater().export_3mf_copy`. The code here is
  rewritten without numpy and edits the XML as text.
- **three.js** (MIT, copyright three.js authors) draws the 3D view. The licence text is in
  [ui/licenses/Three.txt](ui/licenses/Three.txt).
- **Vue** (MIT), **PrimeVue** (MIT) and **PrimeUIX** (MIT) come in through the shared Orca UI foundation,
  the `@orca-plugins/ui-foundation` dependency (github.com/bloodf/orca-ui-foundation), together with its icons from **Lucide** (ISC) and the **Manrope** typeface
  (SIL OFL 1.1), which the page embeds. The licence texts are in that packages `licenses/` (`ui/node_modules/@orca-plugins/ui-foundation/licenses/`)
  and travel in the wheel.

## Brand art and fonts

The logo, tab icon, diagrams and store, README, install, social and release images in
`assets/` and `src/embedder/ui/` are original artwork made for Embedder and are covered by this project's
licence. The fonts used in that artwork are free and open, under the SIL Open Font License 1.1, and sit
with their licence texts in [assets/fonts](assets/fonts):

- **Manrope**, copyright 2018 The Manrope Project Authors
  ([licence](assets/fonts/Manrope-OFL.txt)). It is also embedded in the SVGs that keep live text.
- **IBM Plex Mono**, copyright 2017 IBM Corp., Reserved Font Name "Plex"
  ([licence](assets/fonts/IBMPlexMono-OFL.txt)).

These copies of the fonts are only used for the artwork. The page embeds its own subset of Manrope through the
shared foundation (above).

The no-project illustration in the page, `ui/src/assets/embedder-insert.webp`, is the Embedder illustration of the
shared Orca UI foundation (`ui-foundation/assets/illustrations/`), copied unchanged; it is original artwork made for
this plugin family.

The page is built into one offline, minified HTML file that carries no licence comments. The licence texts of
everything bundled in it (Vue, PrimeVue, PrimeUIX, three.js, the Lucide icons and the Manrope typeface) ship in the
wheel, under `embedder-<version>.dist-info/licenses/`, and inside the plugin's own code, as `THIRD_PARTY_NOTICES` in
`embedder/_assets.py`, since OrcaSlicer installs the package without its dist-info.

## File format facts

The 3MF layout Embedder writes (negative parts and `custom_gcode_per_layer.xml`) was checked against
the OrcaSlicer 2.5.0 source (`bbs_3mf.cpp`, `CustomGCode.hpp`, `ToolOrdering.cpp`) and a real project
file. No OrcaSlicer code is copied. The notes are in [docs/3mf.md](docs/3mf.md).

## Affiliation and trademarks

Embedder is independent. It is not affiliated with, made by or supported by the OrcaSlicer project.
OrcaSlicer, 3MF, NFC and other names are trademarks of their owners. The brand art does not use or
imitate the NFC Forum N-Mark.
