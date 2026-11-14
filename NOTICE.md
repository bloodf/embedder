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
  vendored in `ui/shared/`. The licence texts are in [ui/shared/licenses](ui/shared/licenses).

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
