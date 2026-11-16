# Contributing

Thanks for helping. Bug reports, projects that fail to load and pull requests are all welcome. Releases
are listed on the [releases page](../../releases) and on Orca Cloud.

## Reporting a problem

Open an issue with:

- the Embedder version (Settings page of the Embedder tab) and the OrcaSlicer version and OS
- the project (`.3mf`) if you can share it, or a small project that shows the same problem
- what you did, what you expected and what happened
- the plugin log: `<OrcaSlicer data folder>/log/python_*.log`

Remove anything private from a project before you attach it.

## Set up

You need Python 3.12 or newer. The plugin uses only the standard library, so there is nothing to
install for it.

```sh
git clone https://github.com/bloodf/embedder
cd embedder
python3 scripts/build.py                        # writes dist/embedder_any.whl
python3 -m unittest discover -s tests
```

Page tests need Node and Chrome or Chromium (`CHROME=...`). Run headless Chrome with
`--use-mock-keychain --password-store=basic`. The scenarios of the 3D view (selecting and dragging a pocket)
drive real mouse events in a second Chrome with software WebGL; the others run without WebGL.

To try a build in OrcaSlicer: **File > Plugins > Install local plugin**, pick
`dist/embedder_any.whl`, then **Activate**. Python errors and `print()` output go to
`<OrcaSlicer data folder>/log/python_*.log`.

## Layout

```text
src/embedder/          plugin sources
src/embedder/ui/       the built tab page and the tab icon
scripts/build.py       builds the single-file plugin
tests/                 unit tests, a fake `orca` module and 3MF fixtures built in the tests
ui/                    the Vue 3 + PrimeVue project for the tab, with the three.js viewer
assets/                README, store and social images
docs/                  reference documentation
```

## Rules for code

- **Standard library only** in the plugin. No dependencies.
- **Only `plugin.py` imports `orca`.** Keep everything else testable without OrcaSlicer.
- **Never write the user's project.** Embedder writes new copies in its own storage folder.
- **Python is the single source of geometry.** The page draws what Python returns.
- **3MF facts come from a source.** Check a format detail against OrcaSlicer's source or a real project
  before using it, and list it in `docs/3mf.md`. The plugin is GPL-3.0-only: do not copy code from
  projects with an incompatible licence.
- Keep functions small and files focused. Comment only what isn't obvious from the code.

## Tests

Write the test first. Every change needs a test that fails without it. `tests/fake_orca.py` has a fake
`orca` module, and the 3MF fixtures are built inside the tests. The page is a Vue 3 + PrimeVue project in
`ui/`: change it there, then `cd ui && npm ci --ignore-scripts && npm run build && npm test`. Run the
whole suite before you open a pull request.

If you change what a pocket or a pause looks like in the file, slice an applied copy with the OrcaSlicer
command line or the GUI and check the pocket and the pause in the G-code.

## Commits and pull requests

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(pocket): ...`, `fix(threemf): ...`, `docs: ...`, `test: ...`.
- One topic per pull request. Describe what changed, how you tested it, and whether you tried it in
  OrcaSlicer 2.5.
- Add a line under `## [Unreleased]` in `CHANGELOG.md`.

## Assets

Images live in `assets/` and the tab icon in `src/embedder/ui/icon.svg`. The art comes from the Embedder brand
kit, made from [docs/brand-images-prompt.md](docs/brand-images-prompt.md); each image has an SVG master and a PNG.
The icons inside the page come from the shared Orca UI foundation (`ui/shared/src/icons.ts`), and the no-project
illustration (`ui/src/assets/embedder-insert.webp`) is the foundation's Embedder illustration; neither is drawn
here. The app bar carries the brand kit's micro mark (`assets/embedder-micro-24.svg`), inlined in `ui/src/App.vue`.

Screenshots inside images are real renders of the built page, never drawn or edited by hand. The SVG masters
keep their 16:10 screenshot frames empty; the PNGs get the renders:

```sh
node ui/tests/page/shots.mjs                                   # dist/shots/*.png: the built page and the real plugin
uv run --no-project --with pillow python scripts/frames.py     # places them at the frames in assets/asset-manifest.json
```

`frames.py` also makes the store, social and install PNGs opaque on the background the manifest records for
each (`#181c22` or `#f5f6f8`), since they are uploaded or shown where the page colour is unknown, and resizes
the finished dark hero into `docs/related-plugins/embedder-preview.png` for the sibling plugins. Run on its own
output it gives the same bytes. Identity marks, feature tiles and UI icons stay transparent; where one is
shown in the README, use a `<picture>` with its light and dark variant.

`shots.mjs` drives headless Chrome (with `--use-mock-keychain --password-store=basic` and software WebGL)
against `ui/tests/page/shots_host.py`, which runs `plugin.py` under the test double of `orca` on a project
built in code, so every number on a screenshot is the plugin's own answer. Pillow is used only for this step;
it is not a dependency of the plugin. Orca Cloud images must stay under 2 MB (`frames.py` checks).

The fonts used in the artwork (Manrope and IBM Plex Mono, SIL Open Font License) live in `assets/fonts/`
next to their licence texts; the plugin does not ship them.

## License

By contributing you agree that your work is released under the [GPL-3.0-only](LICENSE) license.
