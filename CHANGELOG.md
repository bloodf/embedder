# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
