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
  vendored in `ui/shared/`, together with its icons from **Lucide** (ISC) and the **Manrope** typeface
  (SIL OFL 1.1), which the page embeds. The licence texts are in [ui/shared/licenses](ui/shared/licenses)
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

The page is built into one offline HTML file, and the licence notices of the bundled libraries are kept
in that file.

## File format facts

The 3MF layout Embedder writes (negative parts and `custom_gcode_per_layer.xml`) was checked against
the OrcaSlicer 2.5.0 source (`bbs_3mf.cpp`, `CustomGCode.hpp`, `ToolOrdering.cpp`) and a real project
file. No OrcaSlicer code is copied. The notes are in [docs/3mf.md](docs/3mf.md).

## Affiliation and trademarks

Embedder is independent. It is not affiliated with, made by or supported by the OrcaSlicer project.
OrcaSlicer, 3MF, NFC and other names are trademarks of their owners. The brand art does not use or
imitate the NFC Forum N-Mark.
