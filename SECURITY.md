# Security

Embedder does not use the network and has no cloud service. It runs inside OrcaSlicer, reads a copy of
the project that OrcaSlicer exports, and writes new project files.

## What it touches

- **Project copy:** the file OrcaSlicer exports into the plugin's storage folder
  (`<storage>/jobs/<id>/source.3mf`). Embedder parses it in memory. Nothing is extracted to disk, and the
  zip is read with the standard library only.
- **Applied copies:** new `.3mf` files written in the plugin's storage folder, through a temporary file,
  never over an existing file. The project you opened is never written.
- **Settings:** `settings.json` in the storage folder, with your clearances, cover thickness, language
  and own insert presets. Values are checked against fixed ranges when they are read and written.
- **Opening a copy:** after Apply, the plugin asks the operating system to open the applied file in
  OrcaSlicer (`open -a` on macOS, the OrcaSlicer executable on Linux and Windows). It only opens a `.3mf`
  that sits directly in the storage folder, and refuses any other path from the page.
- **Threads:** the plugin asks OrcaSlicer for permission to run background threads, so parsing and writing
  do not block the interface.

## Your project file

Embedder reads whatever 3MF OrcaSlicer exports. A project can be large, so loading one takes time and
memory; meshes go to the page in 256 KiB chunks. Embedder checks sizes, indexes and numbers it takes from
the page, and refuses a pocket whose point is not on the clicked face.

Applied copies contain your whole project, including any model you did not mean to share. Treat them like
the original. When you report a bug, you can attach a project, but remove anything private first.

## What to check on the printer

A pause that holds a magnet in place is a physical process. Magnets can jump to a steel nozzle or move the
print head. Put each insert in the right way up and look at the print before you resume. Embedder does not
move the printer and does not send commands to it; the pause is OrcaSlicer's own layer pause, which runs
your printer profile's pause G-code.

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's private
[security advisory](https://github.com/bloodf/embedder/security/advisories/new) form and include
the version, what an attacker can do, and how to reproduce it. You'll get an answer within a week.
