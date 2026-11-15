// Behaviour tests of the built Embedder page (src/embedder/ui/app.html), in owned headless Chrome under a
// host-like CSP, with a scripted OrcaSlicer bridge. Each scenario gets a fresh page.
//   node tests/page/run.mjs [name-filter]          PAGE=<page with icons> is set by tests/test_ui_page.py
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch, MOCK_HOST, HELPERS, preparePage } from './cdp.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../..');

async function pageWithIcons() {
  if (process.env.PAGE) return readFile(process.env.PAGE, 'utf8');
  return execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import build; sys.stdout.write(build.page_html("app.html"))'],
    { cwd: repo, encoding: 'utf8', maxBuffer: 64 << 20 });
}

const PRELUDE = `
const SETTINGS = {ui_language: 'auto', xy_clearance: 0.2, z_clearance: 0.2, cover_magnet: 1, cover_nfc: 0.6, user_presets: []};
const PRESETS = {builtin: [
  {id: 'magnet-disc-6x3', name: '6x3 magnet', kind: 'magnet', shape: 'disc', d: 6, t: 3, builtin: true},
  {id: 'nfc-sticker-25', name: '25 mm NFC sticker', kind: 'nfc', shape: 'disc', d: 25, t: 0.4, builtin: true}], user: []};
// a 20 mm cube at x, y 90..110 (the same fixture as tests/unit/cube.ts), served in 48-byte chunks
const POS = new Float32Array([90,90,0, 110,90,0, 110,110,0, 90,110,0, 90,90,20, 110,90,20, 110,110,20, 90,110,20]);
const IDX = new Uint32Array([0,2,1, 0,3,2, 4,5,6, 4,6,7, 0,1,5, 0,5,4, 1,2,6, 1,6,5, 2,3,7, 2,7,6, 3,0,4, 3,4,7]);
const CHUNK = 48;
const part = (n) => ({part: n, id: String(n + 1), name: 'Cube', subtype: 'normal_part', embedder: false, vertices: 8, triangles: 12,
  pos_bytes: 96, idx_bytes: 144, pos_chunks: 2, idx_chunks: 3});
const object = (n, extra) => ({object: n, id: String(n + 1), name: n ? 'Lid' : 'Cube', item: n + 1, instance: 0, cut: false, embedded_block: null, parts: [part(0)], ...(extra || {})});
const PROJECT = {job: 'j1', name: 'cube', plate: 1, plates: 2, config_source: 'project', chunk_bytes: CHUNK,
  settings: {layer_height: 0.2, first_layer_height: 0.2, pause_gcode: true, print_sequence: 'by layer', raft_layers: 0},
  blocks: [], objects: [object(0), object(1)],
  existing: [{id: '9', object_id: '1', name: 'Embedder 6x3 magnet (embedded)', label: '6x3 magnet', mode: 'embedded'}], pauses: []};
const PLAN = {mode: 'embedded', face: 'top', shape: 'cylinder', size: [6.4, 6.4, 3.2], transform: [1,0,0,100, 0,1,0,100, 0,0,1,15.6, 0,0,0,1],
  floor: 15.6, top: 18.8, pause_z: 19, cover: 1.2, label: '6x3 magnet', kind: 'magnet',
  preview: {positions: [100,100,15.6, 103,100,15.6, 100,103,18.8], indices: [0, 1, 2]}, warnings: [], blocked: null};
async function ready() {
  await until(() => last('cmd', 'hello'), 'hello sent');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: SETTINGS});
  await until(() => last('cmd', 'presets.list'), 'presets asked');
  await reply(last('cmd', 'presets.list'), PRESETS);
}
async function tab(name) { await click(q('[data-tab="' + name + '"]')); }
const alerts = () => qa('[role=alert] .p-message').map(text).join(' | ');
const answered = new Set();
const open = name => cmds(name).filter(m => !answered.has(m.id));
const b64 = u => btoa(String.fromCharCode(...u));
/** Answer n mesh.chunk requests, checking that the page never has more than one in flight. */
async function serveChunks(n) {
  for (let k = 0; k < n; k++) {
    await until(() => open('mesh.chunk').length, 'chunk request ' + k);
    eq(open('mesh.chunk').length, 1, 'one chunk request at a time');
    const m = open('mesh.chunk')[0];
    answered.add(m.id);
    const src = new Uint8Array((m.args.kind === 'pos' ? POS : IDX).buffer);
    await reply(m, {i: m.args.i, chunks: Math.ceil(src.length / CHUNK), bytes: src.length, data: b64(src.subarray(m.args.i * CHUNK, (m.args.i + 1) * CHUNK))});
  }
}
async function loaded(project) {
  await ready();
  await click(byTest('load'));
  await until(() => last('cmd', 'project.load'), 'load sent');
  await reply(last('cmd', 'project.load'), project || PROJECT);
  await serveChunks(5);
  await until(() => !byTest('fallback-place').disabled, 'meshes ready');
}
async function place(plan) {
  const before = cmds('pocket.plan').length;
  await click(byTest('fallback-place'));
  await until(() => cmds('pocket.plan').length > before, 'plan sent');
  if (plan) await reply(last('cmd', 'pocket.plan'), plan);
  return last('cmd', 'pocket.plan');
}
`;

// The page tests never rely on WebGL: every scenario runs as in a WebView without it (the numeric fallback).
const NO_WEBGL = `
const __getContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (type, ...rest) { return /webgl/i.test(type) ? null : __getContext.call(this, type, ...rest); };
`;
const scenarios = [];
const test = (name, body, opts = {}) => scenarios.push({ name, body, ...opts });

test('hello is the first command; the version shows once it answers', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  eq(sent()[0].cmd, 'hello', 'first message');
  eq(last('cmd', 'hello').args, {}, 'hello has no arguments');
  await ready();
  eq(text(byTest('version')), '0.1.0', 'version shown');
`);

test('the Embed tab starts with the empty state', `
  await ready();
  assert(byTest('embed-empty'), 'empty state');
  assert(text(byTest('embed-empty')).includes('No project loaded'), 'empty title: ' + text(byTest('embed-empty')));
`);

test('the tabs switch panels', `
  await ready();
  await tab('settings'); assert(byTest('settings-form'), 'settings panel');
  await tab('embed'); assert(byTest('embed-empty'), 'embed panel');
`);

test('an error reply with a code does not break the page', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  await fail(last('cmd', 'hello'), {code: 'internal', detail: 'boom'});
  assert(byTest('embed-empty'), 'page still usable');
`);

test('Portuguese from the host language', `
  await ready();
  assert(text(byTest('embed-empty')).includes('Nenhum projeto carregado'), 'pt-BR title: ' + text(byTest('embed-empty')));
  eq(document.documentElement.lang, 'pt-BR', 'document language');
`, { lang: 'pt_BR' });

test('icons are drawn from the injected map', `
  await ready();
  assert(qa('.em-icon svg').length >= 2, 'tab icons drawn');
`);

test('theme follows the host colour while the page runs', `
  const root = document.documentElement;
  root.style.setProperty('--orca-bg', '#f4f4f4');
  await until(() => !root.classList.contains('orca-dark'), 'light', 15000);
  root.style.setProperty('--orca-bg', '#151515');
  await until(() => root.classList.contains('orca-dark'), 'dark after the host changed', 15000);
  eq(getComputedStyle(document.body).backgroundColor, 'rgb(24, 28, 34)', 'dark palette background');
`);

test('load shows the progress of reading the project', `
  await ready();
  await click(byTest('load'));
  await until(() => last('cmd', 'project.load'), 'load sent');
  eq(last('cmd', 'project.load').args, {}, 'load has no arguments');
  assert(text(byTest('loading')).includes('Exporting'), 'exporting first: ' + text(byTest('loading')));
  await post({type: 'progress', job: 'j1', stage: 'meshes', done: 1, total: 3});
  assert(text(byTest('loading')).includes('1 of 3'), 'progress text: ' + text(byTest('loading')));
  eq(q('[data-test=loading] [role=progressbar]').getAttribute('aria-valuenow'), '33', 'progress bar');
  await reply(last('cmd', 'project.load'), PROJECT);
  assert(!byTest('loading'), 'progress gone');
  eq(text(byTest('project-name')), 'cube', 'project name');
`);

test('meshes are pulled one chunk at a time, for the selected object only', `
  await loaded();
  const asked = cmds('mesh.chunk').map(m => m.args);
  eq(asked.map(a => a.kind + a.i), ['pos0', 'pos1', 'idx0', 'idx1', 'idx2'], 'chunk order');
  eq(asked[0], {job: 'j1', object: 0, part: 0, kind: 'pos', i: 0}, 'chunk request shape');
  assert(asked.every(a => a.object === 0), 'only the selected object');
`);

test('placing sends a plan request; the preview is listed and staged with its pause', `
  await loaded();
  const m = await place(PLAN);
  const a = m.args;
  eq([a.job, a.object, a.part, a.mode, a.preset], ['j1', 0, 0, 'embedded', 'magnet-disc-6x3'], 'plan arguments');
  assert(a.tri === 2 || a.tri === 3, 'top triangle: ' + a.tri);
  assert(Math.abs(a.point[0] - 100) < 1e-3 && Math.abs(a.point[1] - 100) < 1e-3 && Math.abs(a.point[2] - 20) < 1e-3, 'point at the top centre: ' + a.point);
  eq(Object.keys(a).sort(), ['job', 'mode', 'object', 'part', 'point', 'preset', 'tri'], 'no unset options sent');
  assert(text(byTest('plan-pause')).includes('19'), 'pause shown: ' + text(byTest('plan')));
  await click(byTest('add'));
  assert(text(byTest('staged')).includes('6x3 magnet'), 'staged: ' + text(byTest('staged')));
  assert(text(byTest('pauses')).includes('Pause at Z 19.00 mm: insert 1 x 6x3 magnet'), 'pause summary: ' + text(byTest('pauses')));
  const again = await place(null);
  eq(again.args.others.length, 1, 'staged pockets go along for the proximity check');
`);

test('a blocked embedded plan says why and offers Open', `
  await loaded();
  await place({blocked: {code: 'tilted_face', detail: 'tilted'}, preview: null, mode: 'embedded'});
  assert(text(byTest('plan-blocked')).includes('the face is tilted'), 'reason: ' + text(byTest('plan-blocked')));
  assert(text(byTest('embedded-block')).includes('Use Open'), 'mode hint: ' + text(byTest('embedded-block')));
  const embedded = qa('[data-test=mode] button').find(b => text(b) === 'Embedded');
  assert(embedded && embedded.disabled, 'Embedded disabled');
  assert(!byTest('add'), 'nothing to add');
`);

test('a project-level block shows the banner and starts in Open', `
  const blocked = {...PROJECT, blocks: ['by_object'], objects: [object(0, {embedded_block: 'by_object'})]};
  await loaded(blocked);
  assert(text(byTest('blocks')).includes('By object'), 'banner: ' + text(byTest('blocks')));
  const m = await place(null);
  eq(m.args.mode, 'open', 'Open by default');
`);

test('warnings are shown in words', `
  await loaded();
  await place({...PLAN, warnings: ['thin_cover', 'nfc_near_magnet']});
  const w = qa('[data-test=plan-warning]').map(text);
  eq(w.length, 2, 'two warnings');
  assert(w[0].includes('thinner than two layers') && w[1].includes('within 10 mm'), 'texts: ' + w);
`);

test('apply writes a copy with the staged and removed pockets; open asks OrcaSlicer', `
  await loaded();
  const m = await place(PLAN);
  await click(byTest('add'));
  await click(q('#rm-9'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  const { job, ...pocket } = m.args;
  eq(last('cmd', 'project.apply').args, {job: 'j1', pockets: [pocket], remove: ['9']}, 'apply arguments');
  const path = '/storage/cube-embedder-20261114-120000-j1.3mf';
  await reply(last('cmd', 'project.apply'), {path, name: 'cube-embedder-20261114-120000-j1.3mf', pockets: 1, removed: 1,
    pauses: [{top_z: 19, extra: 'Embedder: insert 1 x 6x3 magnet'}], warnings: ['existing_gcode_at_layer']});
  assert(text(byTest('result')).includes('1 pockets added, 1 removed'), 'result: ' + text(byTest('result')));
  assert(text(byTest('result')).includes('Save Project As'), 'save-as note');
  assert(text(byTest('result')).includes('Your own custom G-code'), 'apply warning');
  eq(text(byTest('result-path')), path, 'path shown');
  assert(!byTest('apply') && !byTest('viewer') && !byTest('no3d') && !byTest('preset'), 'the job is over: no more staging on this copy');
  assert(text(byTest('result')).includes('Load project'), 'result asks for a new load: ' + text(byTest('result')));
  await click(byTest('open'));
  await until(() => last('cmd', 'project.open'), 'open sent');
  eq(last('cmd', 'project.open').args, {path}, 'open arguments');
  await reply(last('cmd', 'project.open'), {open: 'asked'});
  assert(text(byTest('opened')).includes('asked to open'), 'opened: ' + text(byTest('opened')));
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 2, 'loads again');
`);

test('a stale job error tells the user to load again', `
  await loaded();
  const m = await place(null);
  await fail(m, {code: 'stale_job', detail: 'the project was loaded again; load it once more'});
  assert(alerts().includes('The project was loaded again. Load it once more'), 'alert: ' + alerts());
  assert(byTest('plan-empty') && !byTest('add'), 'no preview kept, the panel asks for a face again');
`);

test('without WebGL the page says so and keeps the face form', `
  await loaded();
  assert(text(byTest('no3d')).includes('not available'), 'notice: ' + text(byTest('no3d')));
  eq(qa('[data-test=no3d] .em-spot svg').length, 1, 'illustration');
  assert(!byTest('viewer'), 'no 3D view');
`);

test('settings show the saved values and the user presets', `
  await ready();
  await tab('settings');
  eq(q('#set-xy_clearance').value, '0.2 mm', 'clearance shown');
  assert(byTest('settings-save').disabled, 'nothing to save yet');
  assert(byTest('presets-empty'), 'no user presets');
`);

test('saving settings plans the staged pockets again; one that no longer fits is dropped, saying so', `
  await loaded();
  const m = await place(PLAN);
  await click(byTest('add'));
  const lid = await place(null);
  await reply(lid, {...PLAN, label: 'Lid magnet'});
  await click(byTest('add'));
  await tab('settings');
  await type(q('#set-xy_clearance'), '0.4');
  q('#set-xy_clearance').blur();
  await settle();
  const before = cmds('pocket.plan').length;
  await click(byTest('settings-save'));
  await until(() => last('cmd', 'settings.save'), 'save sent');
  await reply(last('cmd', 'settings.save'), {...SETTINGS, xy_clearance: 0.4});
  await until(() => cmds('pocket.plan').length > before, 'first staged pocket planned again');
  const { job, ...pocket } = m.args;
  const first = last('cmd', 'pocket.plan');
  eq([first.args.object, first.args.tri, first.args.preset, first.args.others.length], [pocket.object, pocket.tri, pocket.preset, 1], 'same pocket, the other one along');
  await reply(first, {...PLAN, size: [6.8, 6.8, 3.2]});
  await until(() => cmds('pocket.plan').length > before + 1, 'second staged pocket planned again');
  await fail(last('cmd', 'pocket.plan'), {code: 'unknown_preset', detail: 'user-x'});
  await until(() => alerts().includes('no longer fit'), 'drop notice');
  assert(alerts().includes('Lid magnet'), 'names the dropped pocket: ' + alerts());
  await tab('embed');
  assert(text(byTest('staged')).includes('6x3 magnet') && !text(byTest('staged')).includes('Lid magnet'), 'staged: ' + text(byTest('staged')));
`);

// ------------------------------------------------------------------ runner
const workers = Number(process.env.WORKERS ?? 4);
if (!Number.isSafeInteger(workers) || workers < 1) throw new Error('WORKERS must be a positive integer');
const filter = process.argv[2];
const chosen = scenarios.filter(s => !filter || s.name.includes(filter));
const page = await pageWithIcons();
const dir = await mkdtemp(join(tmpdir(), 'embedder-page-'));
const browser = await launch();
let failed = 0;
const results = [];
try {
  await Promise.all(Array.from({ length: Math.min(workers, chosen.length) }, async (_, worker) => {
    for (let k = worker; k < chosen.length; k += workers) {
      const sc = chosen[k];
      const boot = { version: 'test', lang: sc.lang ?? 'en', pref: sc.pref ?? 'auto' };
      const file = join(dir, `p${k}.html`);
      await writeFile(file, preparePage(page, boot));
      const p = await browser.newPage();
      const started = Date.now();
      try {
        await p.size(1280, 900);
        await p.init(MOCK_HOST + NO_WEBGL + 'try { localStorage.clear(); } catch {}');
        await p.goto(pathToFileURL(file).href);
        const body = `(async () => { ${HELPERS} ${PRELUDE}
          await until(() => document.querySelector('#app > *'), 'app mounted');
          ${sc.body}
          await settle();
          return { violations: __t.violations, rejections: __t.rejections, errors: __t.errors };
        })()`;
        const probe = await p.evaluate(body);
        if (probe.violations.length || probe.rejections.length || probe.errors.length) throw new Error('page problems: ' + JSON.stringify(probe));
        results.push({ name: sc.name, ok: true, ms: Date.now() - started });
        console.log(`ok   ${sc.name}`);
      } catch (e) {
        failed++;
        results.push({ name: sc.name, ok: false, error: String(e.message || e) });
        console.log(`FAIL ${sc.name}\n     ${String(e.message || e).split('\n')[0]}`);
      } finally {
        await p.close();
      }
    }
  }));
} finally {
  await browser.close();
  await rm(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
if (process.env.RESULTS) await writeFile(process.env.RESULTS, JSON.stringify(results, null, 2));
console.log(`${chosen.length - failed}/${chosen.length} page scenarios passed`);
if (failed || !chosen.length) process.exit(1);
console.log('PASS');
