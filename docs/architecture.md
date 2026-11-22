# Architecture

Embedder ships as a pure-Python wheel, `embedder_any.whl`, which OrcaSlicer loads as a plugin. The
sources live in `src/embedder/`, and `scripts/build.py` packs them. The tab's page is a Vue 3 + PrimeVue
project in `ui/`, built into one offline HTML file (`src/embedder/ui/app.html`) with a three.js viewer.

## Why it works on a copy

OrcaSlicer 2.5 plugins cannot read or edit live geometry, and cannot draw or pick in Orca's 3D view.
The one route is the host's `plater().export_3mf_copy(path)`: export a copy, edit the copy, ask Orca
to open it. So Embedder never changes the user's project. Every result is a new `.3mf` in the plugin's
storage folder. (`orca_organizer` uses the same route.)

## Modules

| Module | Job | Uses `orca`? |
|---|---|---|
| `plugin.py` | Capabilities, permissions, storage folder, settings store, page HTML, command dispatch, opening a file in OrcaSlicer | yes |
| `session.py` | One job: load a copy, serve meshes in chunks, plan pockets, write the applied copy | no |
| `pocket.py` | Pocket rules: layer grid, embedded and open shapes, blocks, warnings, pause heights and pause text | no |
| `threemf.py` | Read a 3MF project; write a copy with new negative parts, removed parts and pauses | no |
| `geometry.py` | 4x4 matrices, 3MF and config transform strings, hexagon and vented box meshes, face tilt | no |
| `presets.py` | Built-in insert table, validation of user presets | no |
| `settings.py` | Validated settings store (JSON file) | no |
| `ui/app.html` | The Embedder tab: one compiled Vue page, built from `ui/`. The wheel ships it as a plain file, `embedder/app.html`, read with `pkgutil.get_data` | - |

Only `plugin.py` imports `orca`, so everything else is tested without OrcaSlicer. All modules are
standard library only (Python 3.12 or newer).

## Capabilities and threads

One capability: a Pages capability named **Embedder**, shown as a tab next to Prepare, Preview and
Device. The plugin asks for the `threading` permission.

The page bridge runs on OrcaSlicer's UI thread. Two commands need that thread:

- `project.load` calls `export_3mf_copy` (UI thread only), then parses the copy on a worker thread.
- `project.open` asks the OS to open the applied file.

Parsing and writing run on the plugin's own threads (`_worker` in `plugin.py`), which reply later with
the request id. Everything the plugin writes stays in the storage folder.

**Posting from a worker thread.** The worker posts its `progress` messages and the late `reply` straight
through `post_message`. The host does not document `post_message` as thread-safe, so this choice rests on
the family's practice: u1control (released 0.5.0 to 0.6.0) and kobracontrol post every command reply and
status push from their service threads the same way, with no hop to the UI thread, and that has held up in
OrcaSlicer 2.5. Organizer is the one sibling that is stricter (worker posts are dropped and its page polls).
If a host release ever needs it, the fallback is the same polling: keep the result in the session and let
the page ask with a `job.status` command on the UI thread.

Old job folders are deleted on a short-lived thread, so a new load never waits for them; a worker that
was still reading a dropped job answers `stale_job`.

## Storage

```text
<storage>/settings.json                                 settings and user presets
<storage>/jobs/<job id>/source.3mf                      the exported copy of the open project
<storage>/<stem>-embedder-<YYYYmmdd-HHMMSS>-<id6>.3mf   an applied copy (-2, -3 if the name exists)
```

Starting a new load deletes the older job folders.

Applied copies are the files the user opens and saves, so some are always kept: the newest copy of each
project (a copy of a copy counts as the same project, by the name before the first `-embedder-`) and every
copy written since the plugin loaded (`Session.written`), since OrcaSlicer may have any of those open. The
others are "old copies". After each apply, old copies past the `KEEP_COPIES` (10) most recent, or older
than `KEEP_DAYS` (30), are deleted; the apply reply counts them in `pruned`. A copy that cannot be deleted
is tried again after the next apply. `copies.status` reports the old copies and `copies.clear` deletes all
of them. Only names of the applied-copy form directly in the storage folder are touched, never links.

## Page protocol

The page and the plugin exchange JSON through `orca.postMessage` and `post_message`.

Page to plugin:

| type | fields | effect |
|---|---|---|
| `cmd` | `id`, `cmd`, `args` | run a command below; the answer is a `reply` with the same `id` |
| `ui_language` | `value` | store the page's language choice (`auto`, `en`, `pt-BR`) |

Plugin to page:

| type | fields |
|---|---|
| `reply` | `id`, `result` or `error` (`{code, detail}`) |
| `progress` | `job`, `stage` (`meshes`), `done`, `total` while a project is parsed |

### Commands

| `cmd` | `args` | `result` |
|---|---|---|
| `hello` | | `{version, settings}` |
| `settings.get` | | the effective settings |
| `settings.save` | `settings` | the effective settings after validation |
| `presets.list` | | `{builtin, user}` |
| `presets.save` | `preset` | `{id, user}`; new user presets get an id that starts with `user-` |
| `presets.delete` | `id` | `{user}` |
| `project.load` | | the job description below (asynchronous) |
| `mesh.chunk` | `job`, `object`, `part`, `kind` (`pos` or `idx`), `i` | `{i, chunks, bytes, data}` (base64) |
| `pocket.plan` | see below | the planned pocket or a block |
| `pocket.auto_fridge` | `job`, `object`, `count` (`auto` or `1`..`8`), `spread`, plus the insert and pocket options | `{items: [{args, plan}, ...], count}` (asynchronous) |
| `project.apply` | `job`, `pockets`, `remove` | `{path, name, pockets, removed, pauses, warnings, pruned}` (asynchronous) |
| `project.open` | `path` | `{open: "asked" or "none"}` |
| `copies.status` | | `{count, bytes, kept}`: the old applied copies that may be deleted, and how many are kept |
| `copies.clear` | | `{removed, freed, failed}` plus the status afterwards |

`project.open` only accepts a `.3mf` that sits directly in the storage folder.

### Settings

| key | default | range |
|---|---|---|
| `ui_language` | `auto` | `auto`, `en`, `pt-BR` |
| `xy_clearance` | 0.2 mm | 0 to 1; added on each side of the insert's width or diameter |
| `z_clearance` | 0.2 mm | 0 to 1; added to the insert's thickness |
| `cover_magnet` | 1.0 mm | 0 to 10; material sealed over an embedded magnet |
| `cover_nfc` | 0.6 mm | 0 to 10; the same for an NFC tag |
| `user_presets` | `[]` | at most 200 valid presets |
| `pocket_shapes` | `{}` | preset id (1 to 40 characters) to the pocket shape picked for it, newest last; the newest 500 are kept, and `presets.delete` drops the preset's entry |

### Loading and meshes

`project.load` exports the copy, records the project path and the current plate, and reads a few live
preset values (`layer_height`, `initial_layer_print_height`, `machine_pause_gcode`, `print_sequence`,
`raft_layers`, `printable_area`) for projects that carry no settings of their own. The reply describes the
job: the job id, project name, plate, `settings`, global `blocks`, the `objects` on the plate (each with its
parts, vertex and triangle counts, chunk counts and an `embedded_block` code), the `existing` Embedder
parts and the `pauses` on the plate.

Meshes are sent in plate coordinates. The page pulls them in chunks of 256 KiB of raw bytes
(`CHUNK_BYTES`), base64-encoded, positions as float32 and indices as uint32, so one message stays small.
A reply to a stale job id fails with `stale_job`.

A build item's plate comes from `<plate>/<model_instance>` in `model_settings.config` (object id plus
instance number, in build order); only an instance missing there is placed by position, from the cached
bounding boxes of its parts.

### Planning

`pocket.plan` takes `job`, `object` (index into the job's objects), `part`, `tri` (the clicked triangle),
`point` (plate frame), `preset` (id) or `custom` (`{kind, shape, d, t}` or `{kind, shape, l, w, t}`),
`mode` (`open` or `embedded`), and optionally `pocket_shape` (`circle`, `hexagon`, `square` or `rectangle`; left out:
the insert's default, a hexagon for a disc and a rectangle for a block; anything else plans as blocked `bad_shape`),
`cover`, `spin` (degrees about the pocket axis), `center`
(`true`: move the point to the area-weighted middle of the flat face around `tri`, the coplanar triangles
joined to it through shared edges; the clicked point stays when that middle is off the face) and `others`
(the other pockets already placed, for the NFC-near-magnet check).

Python is the single source of geometry. The page only draws the primitive Python returns. The point must
lie within 1 mm of the triangle's plane. The reply carries the pocket's mode, face class, shape, size,
transform, the `point` it was planned at (the face's middle under `center`), cavity `floor` and `top`,
`pause_z`, the actual cover (never thinner than asked), label, kind, `copies` (instances of the object on the plate; each gets the insert), a preview mesh and `warnings`, or
a `blocked` object with a stable `code`. An embedded pocket whose pause height already carries someone
else's custom G-code gets the `existing_gcode_at_layer` warning here too, not only from apply.

Projects without `model_settings.config` (`no_model_settings`) and bare mesh objects (`unsupported_object`)
are refused while planning, so a pocket that apply could not write is never staged.

### Moving a pocket

Moving adds no command: a moved pocket is the same `pocket.plan` request with another `tri` and `point`, so
its size, cavity, pause, cover and warnings come from the same code as a click. `center` is dropped once a
pocket is moved by hand, or it would be pulled back to the middle of the face. The first arrow key on a centred
pocket steps from the `point` of its plan, where it is drawn, not from where it was clicked.

One pocket is "in hand" on the page: the new one being placed, or a pocket of the list that was selected (a
click on its marker in the 3D view or on its row). The form, the arrow keys (0.5 mm along the face, 5 mm
with Shift, in the direction the camera shows), R (15 degrees) and a drag all change the pocket in hand.

- **A click on a face always places a new pocket** and lets go of a selected one. A click on a pocket selects
  it; a click on nothing, Escape or **Done** lets go.
- **A drag** starts on a pocket (the camera controls are off while one is held) and follows the surface under
  the pointer, one raycast per frame. Between answers the page slides the preview it already has: the middle
  of its bounding box, brought onto its face, goes to the new point, turned from the old face normal to the
  new one (`anchorOf` and `slide` in `ui/src/core/pick.ts`). That is a move of Python's mesh, not a second
  source of geometry, and the next answer replaces it.
- **One `pocket.plan` is out at a time**, and while a pocket slides a new one goes at most every 100 ms. A
  change made in between is planned after that, so a drag or a held arrow key never queues requests. An
  answer that arrives during a drag is shown (shape, warnings, blocked reason) but is not final. The release
  always plans once more, and that answer stands. A request unanswered after 1.5 s no longer holds the next
  one back. **Add pocket** waits until the plan shown is the answer for where the pocket is, with no drag on and
  no plan out.
- **Letting go before the answer.** A pocket of the list let go (Escape, **Done**, another row, a click) while
  its last change is unplanned or unanswered is planned once more for its row, and the row takes that answer
  (or stays, saying why) even though the pocket is no longer in hand.
- **A blocked answer.** A new pocket keeps it, flagged and without **Add pocket**, exactly as after a click
  there. A pocket of the list goes back to where it was and the pocket panel says why, because the list only
  holds pockets Apply can write (`verdict` in `ui/src/app/logic.ts`). Warnings never stop a move.

Pockets that an earlier Apply already wrote (`existing`) are not movable: the project keeps only their name
and mesh, not the insert, face, cover and rotation a new plan needs. They can be ticked for removal.

### Applying

`project.apply` re-plans every pocket (never trusting the page's earlier answer), then writes the copy.
Pauses are recomputed from all embedded pockets on every apply, including the Embedder parts that stay
because they were not in `remove`. A negative part cuts every instance of its object, so the pause text
counts each pocket once per instance on the plate.

A successful apply ends the job: the new copy is the project now, and later `pocket.plan` or
`project.apply` calls for that job answer `stale_job`. The page shows the result and asks for
**Load project** again before more pockets, so a second apply never rebuilds from the old copy and drops
the first one's pockets. The output name is claimed atomically (a hard link from the temporary file, or an
exclusive create where links are not supported); a name already taken gets `-2`, `-3`, ...

### Error codes

Errors reach the page as `{code, detail}`. Codes seen from the session and plugin include `stale_job`,
`bad_request`, `bad_part`, `cut_object`, `no_model_settings`, `unsupported_object`, `bad_triangle`, `bad_point`, `pocket_blocked`, `export_failed`,
`open_failed`, `unknown_command` and `internal`, plus the 3MF codes in [3mf.md](3mf.md) and the preset
codes (`no_preset`, `unknown_preset`, `bad_dimension`, ...).

## Pockets and the pause rule

All coordinates are millimetres in the plate frame; world Z is print Z.

**Layer grid.** Layer tops are `first + k * height`, where `first` is the initial layer height and
`height` is the layer height (an object's own `layer_height` wins). `snap_down` and `snap_up` move a
height to the grid.

**Open pocket.** Any face. Depth is the insert thickness plus the Z clearance. The footprint is the
insert size plus the XY clearance on each side. The mesh reaches 1 mm outside the surface so the cut is
clean.

**Shapes and vents.** Every pocket leaves a way out for trapped air and spare glue; the fit of the insert is
the same as without it.

The shape is the request's `pocket_shape` or `pocket.default_shape(insert)`; `pocket.fit` sizes it, the smallest of
its kind that holds the insert plus clearance (see [pockets.md](pockets.md#pick-the-pocket-shape)).

- Hexagon (a disc's default): a hexagonal prism. The width across the flats is the diameter plus the XY clearance
  on each side (what a round pocket would measure), so the six flats locate the disc; the six corners, at
  `flat / cos 30°` across, stay open. Two corners lie on the pocket's local X, and the spin turns them. For a block
  the hexagon is the smaller of two: turned 30° (`Pocket.turned`, two flats across X holding the length) or corners
  on X (a long, thin block); between them they are the smallest at any turn.
- Rectangle (a block's default) and square: a box of the fit, with a round vent (`VENT_DIAMETER`, 1.0 mm) centred
  on each corner and running the whole depth. A vent is never wider than 90% of the box's shorter side, so two
  vents do not merge on a very narrow box.
- Circle: a 64-sided prism around the fit (`cylinder_mesh`: flat to flat equals the diameter, never undersized).
  No vents.
- Side slot (any insert on edge): a box with the same vents, except that the two corners on the wall side
  vent along the wall only. The face towards the wall stays flat, so the wall keeps the cover that was asked.

Each pocket is one closed solid (the outline of the box and its vents, pushed up), written as one negative
part. The page shows the fit (`size`) and the footprint with the corners or vents (`outer`).

**Embedded pocket, flat face.** Height is thickness plus Z clearance. On a top face the cavity ends one
cover thickness below the surface; on a bottom face it starts one cover thickness above it. The floor is
snapped to the grid on the cover side first (top face: the cavity top snaps down under the cover; bottom
face: the floor snaps up over it), so the cover is never thinner than asked, then the other end moves away
so the cavity is never shorter than the insert.

**Embedded pocket, side face.** A vertical slot behind the wall. Width is the insert's length (diameter
for a disc) plus clearance, depth is the thickness plus clearance, height is the diameter (disc) or
width (block) plus Z clearance, centred on the clicked height and snapped to the grid. The back of the
slot is one cover thickness behind the wall.

**Pause.** `pause_z = cavity top + layer height`: the first layer that closes the cavity. Pockets with the
same `pause_z` share one pause. The text is `Embedder: insert N x <label>, ...`.

**Blocks** (embedded only; open pockets are never blocked by these): `tilted_face`, `by_object`
(print sequence "by object", also read per plate), `no_pause_gcode`, `raft`, `variable_layer_height`
(a layer height profile, or a layer range on the object), `instances_other_plate` (an instance of the
object sits on another plate: the part would cut it, but the pause is written for this plate only).
Also `below_bed`, `no_floor` (no printed layer under the cavity), `pause_too_low` (pause before the
second layer) and `no_layer_height`. `instances_differ` (instances differ by more than a Z rotation and a
move) blocks both modes, because one part cuts every instance.

**Warnings:** `thin_cover` (cover under two layers on a top or bottom face, under 0.8 mm for a side wall),
`breaks_surface` (an embedded cavity leaves the part: probe columns through the centre and the rim are
ray-tested against the clicked part's mesh above the top, through the middle and under the floor; for a side
slot they must be inside the solid just above its floor and just under its top. The rim is twelve points round a
circle, the hexagon's six corners and the middle of its six flats, or the middle of the box's four edges and the furthest reach of each
corner vent), `nfc_near_magnet` (NFC pocket within 10 mm of a magnet pocket, measured from a circle's rim or the
furthest corner of any other pocket, vents included), `existing_gcode_at_layer` (someone else's custom G-code already on
the pause layer; no Embedder pause is added there).

**Face classes.** A face within 5 degrees of horizontal is flat (top or bottom), within 5 degrees of
vertical is a side face, anything else is tilted.

## Build and tests

`python3 scripts/build.py` writes `dist/embedder_any.whl` and `dist/SHA256SUMS`, and replaces the
`VERSION` placeholder in `plugin.py` with the version from `pyproject.toml`. Tests are in `tests/`:
`python3 -m unittest discover -s tests`. They use a fake `orca` module, 3MF fixtures built in the tests
and the built page in headless Chrome. Nothing talks to a real OrcaSlicer.
