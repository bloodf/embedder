# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.11.0] - 2026-11-28

### Changed
- **The pocket you just placed stays on screen.** After a click on a face, what goes in, where the print pauses, the cover, any warnings and **Add pocket** sit at the bottom of the form, which now scrolls inside its own panel. They used to end up below the window edge. The warnings come first, **Add pocket** turns into the main button once the pocket can be added, and the pocket's size, position and cavity are behind **Dimensions**.
- **Form, 3D view and list fit one screen** from 860 px wide. In two columns the list sits under the 3D view next to the form, so the staged pockets and **Apply** are in sight while you place. A banner above the panels no longer pushes their bottom edge out of the window.
- **Fridge magnets on the bottom** moved from the form to the pocket list, where its pockets appear. The buttons read `Auto`, `1`, `2`, `4`, and **All objects** is a tick box.
- **One hold warning per object.** The advice about magnet hold shows once above the list, naming the object, and each pocket it covers carries a small mark. It used to repeat as four lines on every row. The warnings are shorter.
- **Pockets are numbered** in the list and on the model, so two pockets of the same insert can be told apart.
- **The result names the project, not the file.** After Apply the page says "2 pockets added to a new copy of Fridge tile" and shows when the copy was saved. The file name with its time stamp and the storage folder are gone; the path appears only when OrcaSlicer cannot be asked to open the copy, and **Copy path** copies it without showing it. The pause line is written in the page language ("2 pcs Ø6 × 3 mm disc") instead of the comment that goes into the G-code. **Load project again** is on the result card too.
- **Settings are one page and save by themselves.** The six pages became four sections (Pockets, My presets, Old project copies, General) with no list to pick from. A change is saved a moment after you make it and a line at the bottom says "Saved", or "Couldn't save" with **Retry**. Save and Discard are gone. Preset sizes read as they do in the insert list ("20 × 10 × 3 mm block").
- **Errors are said in plain words.** "Embedder could not start" now says what to do, and what Python reported is behind **Technical details** with a copy button. A failed command says "Embedder ran into an unexpected problem" and offers **Copy details**. **Load project** is off while Embedder has not started.
- **No banner for quick commands.** "Still working: …" shows only when a command has been out for more than half a second, and never for the background reads of the preset list and the old copies. It used to flash at the top of the page on every command and push the page down.
- Pockets already in the project are rows with a bin and **Undo** instead of "Remove …" tick boxes, and they come first while nothing is staged.
- A custom size is the last choice of the insert list (**Custom size…**) instead of a tick box under it.
- Wording: "Pocket type" for Embedded/Open, "Polarity mark" (with a note that it does not change the pocket), "Load project again", "Cancel" in dialogs, "2 pcs" instead of "2 ×" next to a size, and the banner for a plate where embedded pockets are off reads as one sentence.
- The bar shows a state chip only while loading, when Embedder is not ready or after a copy was written. The hint in the 3D view sits on a plate of its own and leaves once a pocket is staged. Without the 3D view, the place form is as tall as its one row.

- Shared UI 5.14.0: the result uses the shared saved-copy card (with **Copy path**), Settings its one-page layout, the lists its rows, and the banners its delay and **Technical details**. Toasts now sit bottom-right.

### Fixed
- With pockets already in the project and nothing staged, the list's footer text ran through the "Embedder pockets in the project" heading in a 900 px tall window.
- "pause at Z 3.80 mm" no longer breaks between "Z" and the number.
- The footer of the list no longer reads "0 pockets to add, 0 to remove".
- A long project name no longer cuts the "Settings" tab short in a narrow window.

## [0.10.3] - 2026-11-28

### Changed
- Shared UI 5.13.1 with PrimeVue 5.0.6.

## [0.10.2] - 2026-11-28

### Changed
- Shared UI 5.13.0.

### Documentation
- The fridge magnet settings are in the architecture notes, the `auto_fridge` count range reads `1`..`8`, and the Portuguese README has the same Install steps as the English one.

## [0.10.1] - 2026-11-25

### Changed
- Shared UI 5.12.0.

## [0.10.0] - 2026-11-24

### Added
- **Magnet hold estimate** for auto fridge magnets: Embedder estimates how heavy the part is (from its volume, infill and filament density) and how much the magnets can hold through the cover, then adds magnets when it needs more. Larger counts go in an even grid. Pick the magnet grade (N35, N42, N52 or ferrite) and the fridge surface (steel, stainless or board) in the new Fridge magnets section of Settings. It is a rough estimate, not a guarantee: a warning shows when the magnets that fit may not hold the part, when they pull hard enough to crack the cover or scratch the fridge, or when the model or settings are missing something the estimate needs. Thanks @plbogen2 (#55).

### Fixed
- On Windows, applying again to a copy Embedder already made could fail with "No such file or directory" when OrcaSlicer's plugin folder is deep, because the file name kept growing past the 260-character path limit. The copy's name no longer repeats old Embedder suffixes and is shortened to fit; if no name fits, Apply says the storage folder path is too long. Thanks @plbogen2 (#56).

## [0.9.0] - 2026-11-22

### Added
- **Hex and square nut presets** (M3 to M6 hex nuts, M3 to M5 square nuts) and a "Nut" kind for your own sizes, so a nut can be trapped inside a print. Thanks @plbogen2 (#49).
- **Polarity note** for magnet pockets: mark a magnet "N up" or "S up" and the note shows in the pocket list and in the pause message, so you put each magnet in the right way round. Thanks @plbogen2 (#50).
- **Auto all objects** next to the auto fridge magnet buttons: places the bottom magnet pockets on every object of the plate in one click. An object printed more than once is planned once, since its pockets go into every copy. Thanks @plbogen2 (#51).

### Changed
- Shared UI 5.10.0.
- Auto fridge magnet keeps pockets away from the edge of the bottom face and, when a pocket would break through the surface, tries nearby solid spots before falling back to an open pocket. Thanks @plbogen2 (#48).
- Placing a pocket on large models is faster: finding the middle of a flat face and checking whether a pocket breaks the surface do less work. Thanks @plbogen2 (#47).

## [0.8.0] - 2026-11-22

### Added
- **Auto fridge magnet (bottom)** (`Auto`, `1×`, `2×`, `4×`) in the pocket form: finds the bottom of the selected object and stages symmetric magnet pockets there in one click. Thanks @plbogen2 (#45).

## [0.7.1] - 2026-11-21

### Changed
- Shared UI 5.6.2: fixes from the shared Orca UI foundation.

### Fixed
- An embedded pocket kept from an earlier Apply gets its pause at the right layer again. Its top was read back a hair too high, so on many heights the pause came one layer late, after the layer that closes the pocket.
- Placing and dragging a pocket, and loading the meshes of a big model, no longer freeze OrcaSlicer: that work now runs off its main thread.
- A project on plate 2 or later is refused when its printable area is unknown, instead of placing every object and pocket in the wrong spot.
- Choosing an object whose mesh is already loaded, while another one is still loading, no longer shows that object as loading or failed.
- A project whose extruder setting holds an unusual character is still written as a valid file.

## [0.7.0] - 2026-11-21

### Changed
- Shared UI 5.6.1: the page now takes the shared Orca UI foundation from its own repository; no visible change.

### Fixed
- A Load project that fails (OrcaSlicer does not write the copy, or the copy can't be read) no longer leaves the project on screen dead. It keeps working, where every click used to fail asking for another load.
- Big meshes reach the 3D view much faster, and OrcaSlicer no longer freezes while they are sent: each piece of a mesh used to copy the whole mesh first.
- A project with a broken mesh (a negative corner number, or a point outside a mesh) is refused as a broken file instead of failing with an internal error.
- A pause list without a plate number is read and rewritten as plate 1, so Apply no longer adds a second plate 1 list next to it.
- Apply no longer fails with an internal error on a project holding an empty Embedder pocket.
- The success banner and the Settings copy messages agree with their counts ("1 pocket added", "1 old copy"), in every language.

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
