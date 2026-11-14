# Releasing

A release is a GitHub release for the tag `vX.Y.Z`. Publishing the release runs
`.github/workflows/publish-orcacloud.yml`, which repeats the CI checks on the tagged commit, builds the wheel,
attaches `embedder_any.whl` and `SHA256SUMS` to the GitHub release, and publishes the same wheel to Orca Cloud.

Why a release and not a tag push or `workflow_dispatch`: Orca Cloud only accepts the GitHub OIDC token of a run
triggered by a published release (official guide, <https://cloud.orcaslicer.com/wiki/>, "Publishing a plugin from
GitHub": `on: release: types: [published]`, `id-token: write`, audience `orcacloud`, HTTP 201 is success).

## What the workflow enforces

- The tag is `vX.Y.Z` (numeric) and equals `version` in `pyproject.toml`; `scripts/build.py --release-tag` checks it again.
- Node 24 and Chrome are provisioned (same setup as `ci.yml`); `ui/` is rebuilt with `npm ci --ignore-scripts &&
  npm run build` and the run fails if `src/embedder/ui/app.html` or `ui/build.json` differ from the commit.
- The whole suite runs with `WORKERS=1`.
- `dist/SHA256SUMS` matches the wheel, and the wheel's metadata and `VERSION` equal the version.
- `CHANGELOG.md` has a non-empty `## [X.Y.Z] - date` section. It becomes the GitHub release notes (when empty) and
  the Orca Cloud changelog. Orca Cloud keeps at most 4000 characters, so `scripts/release_notes.py` cuts the copy it
  sends at a line boundary and adds a link to the release page.
- The OIDC token is masked in the log. No secret is stored in the repository.

## Prerequisites (outside the repository)

1. On Orca Cloud the Embedder plugin is connected to this repository under Edit plugin > GitHub publishing (one
   repository publishes to exactly one plugin). A 401 from the publish step means this is missing.
2. The version is higher than the one the hub lists (none yet for the first release).
3. GitHub Actions is enabled and the release is not a draft.
4. The store images from `docs/brand-images-prompt.md` are uploaded to the listing (`assets/orca-cloud/`), and the
   description comes from [orca-cloud-description.md](orca-cloud-description.md).

## Steps

1. On `main`, the commit to release has `pyproject.toml`, `ui/package.json` and `ui/package-lock.json` at the new
   version and a dated changelog section. Run the local gates below and note the commit hash.
2. Tag exactly that commit and push the tag: `git tag vX.Y.Z <commit> && git push origin vX.Y.Z`.
3. Publish the release, which starts the workflow:
   `python3 scripts/release_notes.py X.Y.Z --limit 0 | gh release create vX.Y.Z --verify-tag --title "Embedder X.Y.Z" --notes-file -`
4. Wait for the "Publish to Orca Cloud" run to finish (a queued run is not a publication). Re-running a run that
   already published is safe; fix the cause and re-run if a step failed.

## Verify afterwards

- The run is green and its last step printed HTTP 201 and "Published vX.Y.Z to Orca Cloud".
- The release lists `embedder_any.whl` and `SHA256SUMS`; the attached `SHA256SUMS` is the authority for what was
  published. Rebuilding the wheel on one machine is byte-identical (the build uses fixed zip timestamps and the
  committed page). The same commit built on another OS should match, since the wheel reads only committed files; a
  difference is something to explain.
- The hub page lists the new version and changelog.

## Local gates

```bash
(cd ui && npm ci --ignore-scripts && npm run build)    # must leave src/embedder/ui/app.html and ui/build.json unchanged
git diff --exit-code -- src/embedder/ui/app.html ui/build.json
export WORKERS=1
python3 scripts/build.py --release-tag vX.Y.Z          # dist/embedder_any.whl, dist/SHA256SUMS
python3 -m unittest discover -s tests                  # needs node on PATH and Chrome (or CHROME=...)
```

## What the tests cover, and what they do not

Every automated test is mock-only: a fake `orca` module, 3MF projects built inside the tests, and the built Vue
page in headless Chrome with a scripted bridge. Nothing talks to a real OrcaSlicer, and no test slices a file.
Behaviour inside a real OrcaSlicer 2.5 is verified by hand before a release: install the wheel, load a project,
place one embedded and one open pocket, apply, and confirm in the reopened copy that both negative parts are in the
object list, the pause shows on the layer slider one layer above the cavity top, the pause command is in the
exported G-code right before the cover layer, and the original project is unchanged.

The spike that checked the file format by slicing hand-built projects with the OrcaSlicer command line is
recorded in [3mf.md](3mf.md).
