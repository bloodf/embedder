# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Shared Orca UI foundation 5.0.8 (Vue 3.5.46, lucide-static 1.77.0); no visible change.

## [0.6.3] - 2026-11-20

### Fixed
- Activating the plugin no longer makes OrcaSlicer ask for the Python audit event "open" with no file named. The tab icon module is now loaded with the plugin, so OrcaSlicer no longer sees a write to its Python cache without a path, which it can only show as a permission prompt with no target.
- Where file links are not supported, the copy of the project is written through its path, so OrcaSlicer can show which file a prompt is about.

## [0.6.2] - 2026-11-20

### Changed
- The page ships in the plugin as a plain `embedder/app.html` file next to the code, instead of a long string inside a Python file. Nothing changes in OrcaSlicer.

## [0.6.1] - 2026-11-19

### Fixed
- Fit in the 3D view now sees the whole part in a view taller than wide. It went by the view's height alone, so a narrow view cut the part at the sides.

## [0.6.0] - 2026-11-19

### Changed
- New look on the shared Orca UI foundation 5.0.2: the page uses OrcaSlicer's own greys, with its teal for Apply, the chosen option, focus and the pocket being placed. Embedder's teal is now only on its mark. The plan of a pocket is a plain grey block (amber when the pocket cannot be made), and the 3D view sits on a neutral grey.
- The notes under Pocket shape, Pocket, Centre on the face, the list of pockets and the pockets already in the project are behind an (i) beside each label. Why a control is off still shows under it.
- In a narrow window the name, the state and Load again stay on one line above the tabs.
- The README and Orca Cloud pictures show the new look, in English and Brazilian Portuguese.

## [0.5.0] - 2026-11-18

### Changed
- Settings is split into pages. In a narrow window the list of pages opens one page at a time, with a Back button. A link into Settings opens the right page, opening Settings on its own brings back the page you used last, and a page with a value to fix is marked in the list.

## [0.4.3] - 2026-11-17

### Added

- Pick the pocket's shape: **circle**, **hexagon**, **square** or **rectangle**, each with its icon, under **Pocket shape**
  in the form. A disc still starts in a hexagon and a block in a rectangle; a shape you pick is kept for that preset and
  comes back the next time you choose it. Each shape is the smallest that holds the insert with the XY clearance: a
  circle is the diameter (a block's diagonal), a hexagon is measured across its flats (a block's hexagon is the
  smallest that holds it, usually with two flats along its length), a square takes the longer side. The plan shows the size in the shape's own terms, for example "6.40 mm across flats · 3.20 mm deep". The
  shape turns with **Rotation**. Embedded on a side face the insert stands in its slot, so the picker is off there
  and says why. Requested by @bloodf.

## [0.4.2] - 2026-11-17

### Added

- Polish (pl) translation. Thanks to @xtronets for asking (u1control#20). Embedder follows OrcaSlicer when it runs in
  Polish (`pl_PL`), or pick **Polski** under **Settings > Language**. Every screen is in Polish, millimetres are
  written with a decimal comma (2,5 mm), and counts use Polish's three plural forms (1 obiekt, 2 obiekty, 5 obiektów).

## [0.4.1] - 2026-11-17

### Changed

- The plugin icon is the new brand tile. The Embedder tab in OrcaSlicer shows the store tile instead of the white
  line mark.
- The page fills the whole tab at every height, also after the window is resized: no more grey under a short page.
- Settings are tabs: one section at a time, and the save bar stays on screen at any window height.
- Notifications appear bottom-left and each one can be closed; warnings and notices on the page can be dismissed.
- Notifications wait while OrcaSlicer is in another tab or app; errors stay until closed.
- A closed notice shows again when its problem goes away and comes back, when the plugin fails to start again, and for every new copy written.

## [0.4.0] - 2026-11-16

### Added

- Pockets can be moved in the 3D view. Drag a pocket and it slides over the surface under the pointer, turning to
  the face it is on; the camera stays still while you drag. When you let go, the pocket is worked out again for
  that spot (size, cavity, pause layer, cover and warnings), the same way as after a click. Escape during a
  drag puts it back.
- Click a pocket in the 3D view, or its row under **Pockets to add**, to select it. The form then shows that
  pocket and changes it in place: insert size, pocket type, rotation, cover and **Centre on the face**. Press
  **Done**, Escape or click beside the part to let go of it. A click on a face still places a new pocket.
- With a pocket selected and the 3D view focused, the arrow keys move it 0.5 mm along its face (5 mm with
  Shift), R and Shift+R turn it 15°, and Delete removes it. A screen reader hears the new position.
- While you drag, the pocket turns amber when it has a warning and red where it cannot be made, and the panel
  says why. A new pocket left on such a spot stays there, marked, as it would after a click. A pocket that is
  already on the list goes back to where it was, and the pocket panel gives the reason.
- The pocket panel shows where the pocket is on the plate (X, Y, Z) and how far it is turned.
- The page speaks Spanish, German and Simplified Chinese next to English and Brazilian Portuguese. On Automatic it
  follows OrcaSlicer's language (`es`, `de`, `zh_CN`; `zh_TW` shows Simplified Chinese; anything else shows
  English), and **Settings > Language** lists all five. Shared words follow OrcaSlicer's own translations (cama,
  Platte, 盘, capa, Schicht, 层). German uses "Sie"; Chinese uses full-width punctuation and the system's Chinese font.

### Changed

- Moving a pocket by hand unticks **Centre on the face** for it. Tick it again to send the pocket back to the
  middle of its face.
- The line under the 3D view now also says that a pocket can be dragged.
- Insert names in the pocket list, the plan, the pauses and **Have ready at the printer** are written in the page
  language, the same way as in the insert menu ("Ø6 × 3 mm disc" rather than "6x3 magnet").
- Error messages no longer repeat the plugin's English explanation after the translated sentence. A file path,
  OrcaSlicer's own error text and the name of the object are still shown, and an Apply refused for one pocket says
  which pocket and why. The pause text written into the project ("Embedder: insert 2 x 6x3 magnet") stays in
  English: it is G-code that OrcaSlicer shows as is.
- Number fields follow the page language. In Brazilian Portuguese, Portuguese "mesa" now names the plate.
- In a narrow window, where the form sits above the 3D view, the view no longer jumps when a click or a drag
  changes the pocket panel above it.

### Fixed

- Typing "2.5" into a millimetre field (custom insert size, cover, clearances) on a German, Spanish or Portuguese
  system gave 25, or the field's maximum. A point or a comma is now the decimal sign in every language, typed or
  pasted.

Pockets that an earlier Apply already wrote into the project cannot be moved. Tick one for removal, place it
again and apply.

## [0.3.0] - 2026-11-16

### Changed

- A pocket for a disc (a round magnet, an NFC sticker or coin) is now a hexagon instead of a circle. It is as
  wide across the flats as the round pocket was, so the six flats hold the disc in place, and the six corners
  stay open: air and spare glue get out, and the insert goes all the way down.
- A pocket for a block keeps its size and gets a 1 mm round vent on each of its four corners (smaller on a very
  narrow block), for the same reason. The vents run the whole depth of the pocket.
- The vertical slot behind a side face has the corner vents too. The two next to the wall open along the wall
  only, so the wall keeps the thickness you asked for.
- This applies to open and embedded pockets. Pause and cover heights are the same as before.
- The new pocket panel names the shape and shows two sizes: the fit, and how wide the pocket is with its
  corners or vents. The 3D view draws the pocket as it will be cut.
- The warning for a pocket that reaches outside the part now follows the new outline: a corner of the hexagon
  or a vent that comes through a thin wall is reported.

A pocket added by an older version keeps its round or plain box shape. To change it, tick it for removal, add
it again and apply.

## [0.2.1] - 2026-11-16

### Fixed

- Apply works on projects saved by OrcaSlicer 2.5.1. It stopped with "object not found where expected" on
  them, because OrcaSlicer 2.5.1 records one more detail on each object of a project.
- Apply and removing pockets also work on projects whose XML is written in other valid ways: attributes in
  another order, single quotes, or spaces around `=`. Everything Embedder does not change stays as it was.

## [0.2.0] - 2026-11-15

### Changed

- A new look for the Embedder tab, shared with the other plugins of the family: a teal app bar with the
  Embedder mark, the project's state and name, and Load again; coloured panels with icons; a clearer type
  scale and the Manrope typeface; light and dark themes that follow OrcaSlicer.
- The Embed tab is laid out in three columns when the window is wide: the new pocket on the left, the 3D view
  in the middle, the pockets to add on the right. It drops to two columns, then one, as the window narrows,
  and the 3D view always fills the height it is given.
- The new pocket panel shows the planned pocket (size, cavity, pause and cover) in a highlighted block, with
  Add pocket at its foot. Magnets and NFC tags carry their own colours in the insert list and the pocket list.
- The pocket list says what to have ready at the printer and at which heights the print will pause, with
  Apply and a summary of what it will write at its foot.
- After Apply, the result shows the pause height first, then where the copy was written and Open in
  OrcaSlicer.
- Settings are grouped in panels with an index, and unsaved changes are named in one save bar.
- The no-project screen has a new illustration.

### Fixed

- A long pocket in the list no longer wraps onto a second line that starts with a stray "· Embedded".

## [0.1.1] - 2026-11-15

### Changed

- The Embedder brand artwork: logo, wordmark and lockups, README heroes, feature icons, the how-it-works
  and pocket-types diagrams, install cards, Orca Cloud store images, social images and a release banner.
  The README, Orca Cloud and install images show real screenshots of the Embedder tab.
- New tab icon, UI icons and empty-state images in the Embedder tab. They follow the light and dark theme;
  the cover row of a planned pocket and Save as preset now carry their icons.

## [0.1.0] - 2026-11-14

### Added

- Embedder tab for OrcaSlicer 2.5: load the open project's current plate, view its parts in 3D and
  click a face to place an insert.
- Built-in insert presets: 15 disc magnets, 4 block magnets, 7 round NFC stickers, 2 NFC coins and
  an NFC card. Save your own disc or block sizes as presets.
- Open pockets on any face, cut along the inward face normal.
- Embedded pockets on flat and upright faces, sealed under a cover, with a native OrcaSlicer pause
  on the first layer above the cavity. Pockets that end at the same height share one pause.
- Settings for XY clearance, Z clearance and cover thickness (magnets and NFC), with English and
  Brazilian Portuguese interface languages.
- Blocks for embedded pockets when the print sequence is "by object", the printer profile has no
  pause G-code, a raft or variable layer height is used, instances differ, or the face is tilted.
  Warnings for thin covers, NFC pockets near magnets and existing custom G-code on the pause layer.
- Apply writes a new project copy with the pockets as negative parts and opens it in OrcaSlicer.
  The original project is never changed. Earlier Embedder pockets and pauses in a project can be
  removed or re-applied.
- Centre on the face: a pocket can go in the middle of the flat face that was clicked.
- The pocket list shows the inserts to have ready (every pocket, open ones too, once per copy).
- Old applied copies are cleaned up: the newest copy of each project and this session's copies are kept,
  older ones beyond 10 or older than 30 days are deleted after Apply, and Settings has a Clear old copies
  button that shows the space it frees.
- The warning about someone else's custom G-code on the pause layer now shows while placing a pocket.

### Fixed

- A project copy without `Metadata/model_settings.config` loads instead of failing with an internal error;
  malformed numbers in the project files report "bad package".
- Very long project names (non-Latin scripts) no longer make the new copy's file name too long on Linux.
- Staged pockets are planned again after a settings change or a deleted preset, so the list and the pauses
  match what Apply writes; a pocket that no longer fits is taken off the list with a notice.
- A language choice that cannot be saved is logged instead of raising into OrcaSlicer.
- Projects without OrcaSlicer's part list (`model_settings.config`) and bare mesh objects are refused, with
  a translated reason, when a pocket is placed instead of failing at Apply with an internal error.
- Every error code the plugin sends has a translation.
