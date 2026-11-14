# 3MF notes

What Embedder writes into an OrcaSlicer 3MF project, and where each fact comes from. Sources are
OrcaSlicer v2.5.0: `src/libslic3r/Format/bbs_3mf.cpp`, `src/libslic3r/CustomGCode.hpp` and
`src/libslic3r/GCode/ToolOrdering.cpp`, plus a real project file and the spike described at the end.
The code is `src/embedder/threemf.py` (reading and writing) and `src/embedder/geometry.py` (transforms).

Embedder edits XML as text and copies every zip entry it does not edit byte for byte. Nothing is
extracted to disk. A copy is written through a temporary file next to the output, and an existing file
is never overwritten.

## Files that matter

| Entry | What it holds |
|---|---|
| `_rels/.rels` | points to the main model (`3D/3dmodel.model`) |
| `3D/3dmodel.model` | the build items and the top-level objects with their `<components>` |
| `3D/Objects/object_N.model` | mesh objects, referenced from components through `p:path` |
| `Metadata/model_settings.config` | per object and per part: name, subtype, matrix, extruder, `mesh_stat` |
| `Metadata/project_settings.config` | JSON: `layer_height`, `initial_layer_print_height`, `machine_pause_gcode`, `print_sequence`, `raft_layers`, `printable_area` |
| `Metadata/custom_gcode_per_layer.xml` | per-plate layer markers: pauses and other custom G-code |
| `Metadata/layer_heights_profile.txt` | variable layer height profile (present and non-empty means variable layers) |
| `Metadata/layer_config_ranges.xml` | per-object layer ranges (an `option` with `opt_key="layer_height"` means variable layers) |
| `Metadata/cut_information.xml` | cut connectors |

Embedder follows `p:path` on each component, because the sub-model file names vary between projects. Only
millimetre files are read (`unit="millimeter"`). When `project_settings.config` is absent or empty,
Embedder falls back to the live preset values the plugin reads from OrcaSlicer (`config_source` is then
`preset` instead of `project`).

## A negative part

Checked against a real Orca 3MF. A negative part has three pieces, all with the same id:

1. A mesh `<object id="N" type="other">` in the model file that holds the parent's parts (the file of the
   parent's first part), with vertices and triangles in the pocket's local frame. When the file declares the
   production namespace, the object gets a fresh `p:UUID`.
2. A `<component objectid="N" transform="...">` under the parent object in `3D/3dmodel.model`. It
   copies the `p:path` of the object's other components and gets a fresh UUID. The `transform` is 12
   numbers (3MF order: the first three columns of the matrix, then the translation) and holds the part's
   matrix.
3. A `<part id="N" subtype="negative_part">` in the parent's `<object>` block in
   `Metadata/model_settings.config`, with metadata `name`, `matrix` (16 numbers, row-major, the same matrix),
   `extruder` (the parent's) and a `<mesh_stat face_count=... />`.

The part id equals the component's `objectid`.

### Ids

New ids are the maximum of every `id` and `objectid` found in the main model, the sub-model files and
`model_settings.config`, plus one, counting up for each pocket added in one apply. New parts are appended
after the existing ones.

### Names

A part Embedder made is named `Embedder <label> (<mode>)`, for example `Embedder 6x3 magnet (embedded)`.
The name is how a later load recognises it (`^Embedder (.+) \((embedded|open)\)$`, subtype
`negative_part`) and offers to remove or re-apply it. Parts without that pattern are never touched.
Removing a part deletes its `<component>`, its mesh `<object>` and its `<part>` entry.

### The matrix

The pocket matrix is `inverse(item transform) x plate-to-world x pocket transform`: the pocket is planned in
the plate frame (what Orca shows, Z up from the bed) and converted into the object frame of the build
item the user clicked. If the result has a negative determinant (the instance is mirrored), the part's
matrix is multiplied by `scale(-1, 1, 1)`, so the stored matrix stays right-handed. Instances of one object
all get the same part, so Embedder only plans on objects whose instances differ by a Z rotation and a move
(`instances_differ` blocks the rest).

On a multi-plate project the plate's origin is offset by the bed size with a 20 percent gap
(`PLATE_GAP = 0.2`, from Orca's logical plate gap, 1.2 x the bed size). A build item belongs to the first
plate whose area its bounding box touches.

### Not supported

- An object that is a bare mesh without a parts list (`unsupported_object`).
- An object cut with connectors (`cut_object`).
- Nested components (`nested_components`) and files that are not millimetre (`bad_unit`).
- Parts whose subtype is not `normal_part`: pockets go on model parts only.

## The pause: `custom_gcode_per_layer.xml`

```xml
<custom_gcodes_per_layer>
<plate>
<plate_info id="1"/>
<layer top_z="19.2" type="1" extruder="1" color="" extra="Embedder: insert 1 x 6x3 magnet" gcode=""/>
<mode value="MultiExtruder"/>
</plate>
</custom_gcodes_per_layer>
```

- `type="1"` is `PausePrint` (`CustomGCode.hpp`). The `gcode` attribute stays empty. Orca emits the printer profile's own
  `machine_pause_gcode` for it, so the plugin never chooses `M600`, `M601` or `PAUSE`.
- `top_z` is the height of the layer the pause attaches to. The pause is emitted **before that layer prints**
  (`ToolOrdering::assign_custom_gcodes`).
- A `top_z` that is not on the layer grid snaps to the **nearest** layer. It is not dropped.
- The file is read only when the 3MF opens as a project, and the markers are **ignored when the print
  sequence is "by object"**. This is why Embedder blocks embedded pockets in that mode.
- Each `<plate>` carries `<plate_info id="N"/>` and a `<mode value="..."/>` line. If the file is missing,
  Embedder creates it, with the same zip metadata date as the main model.

On apply, Embedder replaces every entry on the plate whose `extra` starts with `Embedder:` and keeps all
the others (color changes and hand-made pauses stay). Entries are sorted by `top_z`. If a non-Embedder
entry already sits within 0.001 mm of a pause height, Embedder keeps it and adds no pause there (the
`existing_gcode_at_layer` warning).

### Where the pause goes

Pause height is the cavity top plus one layer height, the first layer that covers the insert. A cavity
whose top is at `T` stays open through the layer at `T`, and the layer at `T + h` is the first one solid
over it, so a pause at `T + h` stops the printer with the cavity fully open and the cover not yet
started.

## Evidence

**Spike, 2026-11-14, OrcaSlicer 2.5.0 command line.** A hand-built 3MF: a 20 mm cube, layer height 0.2,
with a negative cylinder (6 mm diameter, 3 mm thick pocket, 64 segments; component transform equal to the
part matrix, random uuid4 values, `mesh_stat` present) and a `<layer type="1" gcode="">` pause. The cavity
floor is at 1.2 mm and its top at 5.2 mm. The CLI sliced it with exit code 0:

- the hole shows on layers 1.4 to 5.2 and the cover is solid from 5.4;
- a pause with `top_z="5.4"` produced `; PAUSE_PRINTING` plus the profile's `machine_pause_gcode`
  right after `; Z_HEIGHT: 5.4`, before that layer prints;
- an off-grid `top_z="5.45"` snapped to 5.4. It was not dropped.

The rule holds: pause at cavity top plus one layer.

**End to end, Python core.** A 20 mm cube with an embedded 6x3 magnet on its top face, written by
`Session.apply` and sliced by the CLI (exit code 0): cavity floor 15.8 mm, cavity top 19.0 mm, no
extrusion near the pocket centre on layers 16.0 to 19.0, solid layers at 15.8 and 19.2, and one
`; PAUSE_PRINTING` with the profile's pause G-code right after `; Z_HEIGHT: 19.2`.

CLI quirks, not plugin issues: projects written by Bambu Studio need `--allow-newer-file`, and one printer
profile used as a donor fails CLI validation even unmodified (`retraction_distances_when_cut: 0 not in
range`).

Not yet checked: WebGL in Orca's tab, opening a storage copy with `open -a`, the size of the largest
`post_message` payload, and a live reopen of an applied copy in the OrcaSlicer GUI.
