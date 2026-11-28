// Behaviour tests of the built Embedder page (src/embedder/ui/app.html), in owned headless Chrome under a
// host-like CSP, with a scripted OrcaSlicer bridge. Each scenario gets a fresh page.
//   node tests/page/run.mjs [name-filter]          PAGE=<the page as the wheel carries it> is set by tests/test_ui_page.py
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch, MOCK_HOST, HELPERS, preparePage } from './cdp.mjs';
import { en } from '../../src/core/messages.ts';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../..');

async function builtPage() {
  if (process.env.PAGE) return readFile(process.env.PAGE, 'utf8');
  const args = ['-c', 'import sys; sys.path.insert(0, "scripts"); import build; sys.stdout.write(build.page_html("app.html"))'];
  const opts = { cwd: repo, encoding: 'utf8', maxBuffer: 64 << 20 };
  try {
    return execFileSync('python3', args, opts);
  } catch {
    return execFileSync('python', args, opts);
  }
}

// English sentences of the page (the words before a placeholder, long enough to be a phrase) that must not show
// in another language.
const ENGLISH = Object.entries(en).filter(([k]) => !k.startsWith('lang.')).map(([, v]) => v.split('{')[0].trim())
  .filter(v => v.length >= 8 && v.includes(' '));

const PRELUDE = `
const ENGLISH = ${JSON.stringify(ENGLISH)};
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
const PLAN = {mode: 'embedded', face: 'top', shape: 'hexagon', size: [6.4, 6.4, 3.2], outer: [7.390083, 6.4], transform: [1,0,0,100, 0,1,0,100, 0,0,1,15.6, 0,0,0,1],
  floor: 15.6, top: 18.8, pause_z: 19, cover: 1.2, label: '6x3 magnet', kind: 'magnet',
  preview: {positions: [100,100,15.6, 103,100,15.6, 100,103,18.8], indices: [0, 1, 2]}, warnings: [], blocked: null};
async function ready() {
  await until(() => last('cmd', 'hello'), 'hello sent');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: SETTINGS});
  await until(() => last('cmd', 'presets.list'), 'presets asked');
  await reply(last('cmd', 'presets.list'), PRESETS);
}
async function tab(name) { await click(q('[data-tab="' + name + '"]')); }
/** The rows of a list as [name, second line] pairs. */
const rows = name => qa('[data-test=' + name + '] li').map(li => qa('.em-row-id > *', li).map(text));
const notes = () => text(byTest('plan-note'));
/** Pick an option of a list by its words. */
async function choose(select, label) {
  await click(select);
  await until(() => qa('[role=option]').some(o => text(o) === label), 'option ' + label);
  await click(qa('[role=option]').find(o => text(o) === label));
}
/** A size of one's own: the last choice of the insert list. */
async function custom() {
  await click(byTest('preset'));
  await until(() => byTest('custom'), 'the last choice of the list');
  await click(byTest('custom').closest('[role=option]'));
}
/** The toasts as one line each (title, then the rest), and what the alert banners say. */
const toastText = el => [q('.oui-toast-text > strong', el), q('.oui-toast-body', el)].map(text).filter(Boolean).join(' ');
const toasts = () => qa('.oui-toasts .oui-toast');
const alerts = () => [...qa('.oui-toast[role=alert]').map(toastText), ...qa('[role=alert] .oui-banner').map(text)].join(' | ');
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

// ---- the 3D view (scenarios with { gl: true }): real mouse events on the canvas, software WebGL
const canvas = () => q('[data-test=viewer] canvas');
const stage = () => byTest('stage');
async function loaded3d(project) {
  await ready();
  await click(byTest('load'));
  await until(() => last('cmd', 'project.load'), 'load sent');
  await reply(last('cmd', 'project.load'), project || PROJECT);
  await serveChunks(5);
  await until(() => canvas() && text(q('[data-test=viewer] .oui-panel-meta')).includes('mm'), 'the cube is in the 3D view');
  canvas().scrollIntoView({ block: 'center' });   // real mouse events only reach what is in the window
  await settle();
}
// Spots of the view as fractions of its shorter side from its centre (the camera is fitted to the shorter side): two on
// the cube's top face, one on its front wall, one beside it.
const TOP_A = [0, -0.195], TOP_B = [0.08, -0.195], FRONT = [0, 0], NOTHING = [0, -0.47];
function spot(s) {
  const r = canvas().getBoundingClientRect(), u = Math.min(r.width, r.height);
  return { x: r.left + r.width / 2 + s[0] * u, y: r.top + r.height / 2 + s[1] * u };
}
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
/** A plan as the plugin would answer these arguments: a 5 mm box sunk 2 mm under the point, on the face of its triangle. */
function planAt(args, extra) {
  const n = [[0, 0, -1], [0, 0, 1], [0, -1, 0], [1, 0, 0], [0, 1, 0], [-1, 0, 0]][args.tri >> 1];
  const c = args.point.map((v, i) => v - 2 * n[i]), positions = [];
  for (const z of [-2.5, 2.5]) for (const y of [-2.5, 2.5]) for (const x of [-2.5, 2.5]) positions.push(c[0] + x, c[1] + y, c[2] + z);
  return {...PLAN, mode: args.mode, face: n[2] > 0 ? 'top' : n[2] < 0 ? 'bottom' : 'side',
    preview: {positions, indices: [0,1,3, 0,3,2, 4,7,5, 4,6,7, 0,5,1, 0,4,5, 2,3,7, 2,7,6, 0,2,6, 0,6,4, 1,5,7, 1,7,3]}, ...(extra || {})};
}
const TILTED = {blocked: {code: 'tilted_face', detail: 'tilted'}, preview: null, mode: 'embedded'};
/** Answer every plan request still open, and the ones those answers set off, with make(args). Returns the last one answered. */
async function answerPlans(make) {
  let m, done = null;
  while ((m = open('pocket.plan')[0])) { answered.add(m.id); await reply(m, make(m.args)); done = m; }
  return done;
}
/** A real click on the 3D view; the plan request it sent (still open), or null when it planned nothing. */
async function clickAt(s) {
  const n = cmds('pocket.plan').length, p = spot(s);
  await pointer('mouseMoved', p.x, p.y);
  await pointer('mousePressed', p.x, p.y);
  await pointer('mouseReleased', p.x, p.y);
  return cmds('pocket.plan').length > n ? last('cmd', 'pocket.plan') : null;
}
/** Click a face and answer its plan. */
async function place3d(s, extra) {
  const m = await clickAt(s);
  assert(m, 'a click on a face plans a pocket');
  await answerPlans(args => planAt(args, extra));
  return m;
}
/** Press on one spot and move to another in a few steps, the button still down. */
async function dragTo(from, to) {
  const a = spot(from), b = spot(to);
  await pointer('mousePressed', a.x, a.y);
  for (let k = 1; k <= 4; k++) await pointer('mouseMoved', a.x + ((b.x - a.x) * k) / 4, a.y + ((b.y - a.y) * k) / 4, true);
}
const drop = s => pointer('mouseReleased', spot(s).x, spot(s).y);
`;

// Most page tests do not rely on WebGL: they run as in a WebView without it (the numeric fallback). The scenarios of the
// 3D view itself ({ gl: true }) get a second Chrome with software WebGL.
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
  assert(!byTest('state'), 'no chip in the bar while nothing is out of the ordinary');
  await tab('settings');
  eq(text(byTest('version')), '0.1.0', 'version shown under Settings, General');
  assert(byTest('version').getClientRects().length, 'version visible');
`);

test('the Embed tab starts with the empty state', `
  await ready();
  assert(byTest('embed-empty'), 'empty state');
  assert(text(byTest('embed-empty')).includes('No project loaded'), 'empty title: ' + text(byTest('embed-empty')));
`);

test('the tabs switch panels', `
  await ready();
  const shown = name => byTest(name).getClientRects().length > 0;
  assert(shown('embed-empty') && !shown('settings-form'), 'Embed first');
  await tab('settings'); assert(shown('settings-form') && !shown('embed-empty'), 'settings panel');
  eq(q('[data-tab=settings]').getAttribute('aria-selected'), 'true', 'tab selected');
  eq(q('#em-view-settings').getAttribute('aria-labelledby'), q('[data-tab=settings]').id, 'the panel is named by its tab');
  await tab('embed'); assert(shown('embed-empty') && !shown('settings-form'), 'embed panel');
  q('[data-tab=embed]').focus();
  await press('ArrowRight');
  assert(shown('settings-form') && document.activeElement === q('[data-tab=settings]'), 'arrow keys move between the tabs');
`);

test('an error reply with a code does not break the page', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  await fail(last('cmd', 'hello'), {code: 'internal', detail: 'boom'});
  assert(byTest('embed-empty'), 'page still usable');
  eq(text(byTest('state')), 'Not ready', 'the bar says so');
  assert(alerts().includes('Embedder could not start. Restart OrcaSlicer.'), 'and what to do: ' + alerts());
  assert(!document.body.innerText.includes('boom'), 'what Python said is not on the page');
  assert(byTest('load').disabled && byTest('load').getAttribute('aria-describedby') === 'em-hello-error', 'Load project is off and points at the reason');
  eq(byTest('hello-details').getAttribute('aria-expanded'), 'false', 'the technical details are closed');
  await click(byTest('hello-details'));
  eq(text(q('[data-test=hello-detail] code')), 'internal: boom', 'and say what Python said when asked for');
  assert(btn('Copy details', byTest('hello-detail')), 'with a way to copy them into a report');
  await click(byTest('hello-retry'));
  await until(() => cmds('hello').length === 2, 'asks again');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: SETTINGS});
  assert(!byTest('hello-error'), 'the error goes once the plugin answers');
  assert(!byTest('state') && !byTest('load').disabled, 'the chip goes too, and Load project is on again');
`);

test('Portuguese from the host language', `
  await ready();
  assert(text(byTest('embed-empty')).includes('Nenhum projeto carregado'), 'pt-BR title: ' + text(byTest('embed-empty')));
  eq(document.documentElement.lang, 'pt-BR', 'document language');
`, { lang: 'pt_BR' });

for (const [lang, host, title] of [['es', 'es', 'Ningún proyecto cargado'], ['de', 'de', 'Kein Projekt geladen'], ['zh-CN', 'zh_CN', '未加载项目'], ['pl', 'pl_PL', 'Nie wczytano projektu']]) {
  test(`${lang} from the host language, with no English left on the main screens`, `
  const english = () => ENGLISH.filter(s => document.body.innerText.includes(s));
  await ready();
  assert(text(byTest('embed-empty')).includes(${JSON.stringify(title)}), 'title: ' + text(byTest('embed-empty')));
  eq(document.documentElement.lang, '${lang}', 'document language');
  eq(english(), [], 'empty state');
  await loaded();
  await place(PLAN);
  await click(byTest('add'));
  await settle();
  eq(english(), [], 'a pocket placed and staged');
  assert(!document.body.innerText.includes('6x3 magnet'), 'the insert label is translated');
  await tab('settings');
  await settle();
  eq(english(), [], 'settings');
`, { lang: host });
}

test('German decimals: "1.5" typed or pasted into a millimetre field is one and a half, not 15', `
  await ready();
  await tab('settings');
  const field = q('#set-cover_magnet');
  await type(field, '1.5'); field.blur(); await settle();
  eq(field.value, '1,5 mm', 'typed with a point');
  await type(field, '2,5'); field.blur(); await settle();
  eq(field.value, '2,5 mm', 'typed with a comma');
  field.focus(); field.select();
  const data = new DataTransfer(); data.setData('text/plain', '0.8');
  field.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
  field.blur(); await settle();
  eq(field.value, '0,8 mm', 'pasted with a point');
  // saved as it changes: answer each save as the plugin would, until the pasted value is the one sent
  const seen = new Set();
  for (;;) {
    await until(() => cmds('settings.save').some(m => !seen.has(m.id)), 'a save');
    const m = cmds('settings.save').find(x => !seen.has(x.id));
    seen.add(m.id);
    if (m.args.settings.cover_magnet === 0.8) break;
    await reply(m, {...SETTINGS, ...m.args.settings});
  }
`, { lang: 'de', intl: 'de-DE' });

test('Chinese input: a full-width 。 or ． typed into a millimetre field is the decimal point', `
  await ready();
  await tab('settings');
  const field = q('#set-cover_magnet');
  await type(field, '1。5'); field.blur(); await settle();
  eq(field.value, '1.5 mm', 'typed 。');
  await type(field, '2．5'); field.blur(); await settle();
  eq(field.value, '2.5 mm', 'typed ．');
`, { lang: 'zh_CN', intl: 'zh-CN' });

test('where a WebView cannot build a paste event, the field keeps its own paste', `
  await ready();
  await tab('settings');
  const field = q('#set-cover_magnet');
  window.DataTransfer = function () { throw new TypeError('Illegal constructor'); };
  field.focus(); field.select();
  const paste = new Event('paste', { bubbles: true, cancelable: true });
  paste.clipboardData = { getData: () => '0.8' };   // needs rewriting for de, so the directive tries to build its event
  field.dispatchEvent(paste);   // an exception in a listener would show in the page probe (window error)
  assert(paste.defaultPrevented, 'InputNumber took the paste, nothing was swallowed');
  field.blur(); await settle();
  eq(field.value, '8,0 mm', 'InputNumber read it as it always did (the point is a group sign in German)');
`, { lang: 'de', intl: 'de-DE' });

test('Spanish decimals in a custom size: "2.5" typed is two and a half', `
  await loaded();
  await custom();
  await type(q('#f-d'), '2.5'); q('#f-d').blur(); await settle();
  eq(q('#f-d').value, '2,5 mm', 'shown with a comma');
  await place(null);
  eq(last('cmd', 'pocket.plan').args.custom.d, 2.5, 'sent as two and a half');
`, { lang: 'es', intl: 'es-ES' });

test('icons come from the shared set; the bar carries the brand mark', `
  await ready();
  eq(qa('.oui-appbar [role=tab] svg.oui-icon').length, 2, 'tab icons drawn');
  eq(qa('.oui-appbar-mark svg rect').length, 6, 'the micro mark: six bars');
  eq(qa('.oui-appbar-mark svg circle').length, 1, 'and the insert');
  assert(q('[data-test=load] svg.oui-icon'), 'the primary action carries its icon');
  eq(q('[data-test=embed-empty] img').naturalWidth > 0, true, 'the illustration is in the page');
  assert(!q('#embedder-icons') && !document.documentElement.innerHTML.includes('__ICONS__'), 'no icon map is injected any more');
`);

test('the embedded typeface loads under the page policy', `
  await ready();
  await document.fonts.ready;
  assert(document.fonts.check('13px Manrope'), 'Manrope is available');
  assert(getComputedStyle(document.body).fontFamily.startsWith('Manrope'), 'and is the page font: ' + getComputedStyle(document.body).fontFamily);
  eq(getComputedStyle(document.body).fontSize, '13px', 'body size');
`);

test('theme follows the host colour while the page runs', `
  const root = document.documentElement;
  root.style.setProperty('--orca-bg', '#f4f4f4');
  await until(() => !root.classList.contains('orca-dark'), 'light', 15000);
  root.style.setProperty('--orca-bg', '#151515');
  await until(() => root.classList.contains('orca-dark'), 'dark after the host changed', 15000);
  eq(getComputedStyle(document.body).backgroundColor, 'rgb(36, 36, 40)', "dark palette background: OrcaSlicer's grey, not tinted");
  eq(document.documentElement.dataset.orcaUiAccent, 'teal', 'Embedder accent');
  eq(getComputedStyle(q('.oui-appbar')).backgroundColor, 'rgb(45, 45, 49)', 'the bar is neutral');
  eq(getComputedStyle(q('.oui-appbar-mark')).backgroundColor, 'rgb(0, 103, 91)', 'the accent is the mark tile');
  root.style.setProperty('--orca-bg', '#f4f4f4');
  await until(() => !root.classList.contains('orca-dark'), 'light again', 15000);
  eq(getComputedStyle(document.body).backgroundColor, 'rgb(240, 240, 240)', 'light palette background');
  eq(getComputedStyle(q('.oui-appbar')).backgroundColor, 'rgb(255, 255, 255)', 'neutral bar');
  eq(getComputedStyle(q('.oui-appbar-mark')).backgroundColor, 'rgb(0, 103, 91)', 'same mark tile in both themes');
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
  eq(text(byTest('project')), 'cube · plate 1 of 2 · 2 objects', 'project line in the bar');
  assert(!byTest('state'), 'a loaded project has no state chip: the project line says it');
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
  assert(!q('#em-plan-state').classList.contains('oui-on-band') && !q('#em-plan-state').dataset.tone, 'a planned pocket is a neutral block (ui-foundation 5: no accent fill)');
  assert(byTest('staged-empty') && byTest('apply').disabled && !byTest('summary'), 'nothing staged yet, and no "0 pockets" line');
  await click(byTest('add'));
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 19.00 mm']], 'one row: the name, then where and how on its second line');
  eq(qa('[data-test=row-n]').map(text), ['1'], 'numbered, so two pockets alike can be told apart');
  eq(text(byTest('staged-count')), '1', 'count in the panel header');
  eq(text(q('#em-pauses-l')), 'The print will pause', 'pause heading');
  eq(qa('[data-test=pauses] li').map(text), ['Z 19.00 mm: insert 1 pc Ø6 × 3 mm disc'], 'pause summary');
  eq(text(byTest('summary')), '1 pocket to add. Apply writes a new copy.', 'what Apply will do; nothing about removals when there are none');
  assert(byTest('add').disabled && byTest('plan-empty'), 'Add waits for the next face');
  const again = await place(null);
  eq(again.args.others.length, 1, 'staged pockets go along for the proximity check');
`);

test('the plan names the pocket shape, its fit in the shape\'s own terms and how wide it is with its vents', `
  await loaded();
  await place(PLAN);
  const facts = () => Object.fromEntries(qa('[data-test=plan] dt').map(dt => [text(dt), text(dt.nextElementSibling)]));
  eq(facts()['Pocket size'], '6.40 mm across flats · 3.20 mm deep', 'a hexagon by its flats');
  eq(text(byTest('plan-shape')), 'Hexagon · corners vent air and glue', 'a disc sits in a hexagon');
  eq(facts()['With vents'], '7.39 × 6.40 mm', 'corner to corner, flat to flat');
  eq(text(byTest('plan-outer')), '7.39 × 6.40 mm', 'the same cell by its hook');
  await place({...PLAN, shape: 'rectangle', size: [10.4, 5.4, 2.2], outer: [11.4, 6.4], label: '10x5x2 magnet'});
  eq([text(byTest('plan-shape')), text(byTest('plan-size')), text(byTest('plan-outer'))],
    ['Rectangle · corner vents for air and glue', '10.40 × 5.40 mm · 2.20 mm deep', '11.40 × 6.40 mm'], 'a block gets corner vents');
  await place({...PLAN, shape: 'square', size: [6.4, 6.4, 3.2], outer: [7.4, 7.4]});
  eq([text(byTest('plan-shape')), text(byTest('plan-size'))], ['Square · corner vents for air and glue', '6.40 mm sides · 3.20 mm deep'], 'a square by its side');
  await place({...PLAN, shape: 'circle', size: [6.4, 6.4, 3.2], outer: [6.41, 6.41]});
  eq([text(byTest('plan-shape')), text(byTest('plan-size'))], ['Circle · no vents', 'Ø6.40 mm · 3.20 mm deep'], 'a circle by its diameter');
  assert(!byTest('plan-outer'), 'a circle has no vents to add');
  await place({...PLAN, face: 'side', shape: 'slot', size: [6.4, 3.4, 6.2], outer: [7.4, 3.9]});
  eq([text(byTest('plan-shape')), text(byTest('plan-outer'))], ['Slot · corner vents for air and glue', '7.40 × 3.90 mm'], 'an insert on edge too');
  const {shape, outer, ...plain} = PLAN;
  await place(plain);
  assert(byTest('plan-pause') && !byTest('plan-shape') && !byTest('plan-outer'), 'a plan without them shows the rest');
`);

test('the pocket shape starts at the insert\'s own, a pick is planned and kept per preset', `
  const saved = {...SETTINGS, pocket_shapes: {'nfc-sticker-25': 'circle'}};
  await until(() => last('cmd', 'hello'), 'hello sent');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: saved});
  await until(() => last('cmd', 'presets.list'), 'presets asked');
  await reply(last('cmd', 'presets.list'), PRESETS);
  await click(byTest('load'));
  await until(() => last('cmd', 'project.load'), 'load sent');
  await reply(last('cmd', 'project.load'), PROJECT);
  await serveChunks(5);
  const picked = () => qa('[data-test=pocket-shape] button').filter(b => b.getAttribute('aria-pressed') === 'true').map(text);
  eq(qa('[data-test=pocket-shape] button').map(text), ['Circle', 'Hexagon', 'Square', 'Rectangle'], 'four shapes, each named');
  eq(qa('[data-test=pocket-shape] button svg').length, 4, 'and each drawn');
  eq(picked(), ['Hexagon'], 'a disc starts in a hexagon');
  eq(text(q('#cut-help')), 'Hexagon for this insert unless you pick another. A pick is kept for its preset.', 'the default said');
  assert(q('#cut-help').closest('.oui-hint-bubble[role=tooltip]') && q('.em-form .oui-hint-btn[aria-label="Pocket shape"]'), 'what the picker does is behind its (i), not a line under it');
  eq(q('[data-test=pocket-shape]').getAttribute('aria-labelledby'), 'cut-l', 'labelled');
  const first = await place(PLAN);
  assert(!('pocket_shape' in first.args), 'the default is not sent');
  const before = cmds('pocket.plan').length;
  const square = qa('[data-test=pocket-shape] button').find(b => text(b) === 'Square');
  square.focus();
  assert(document.activeElement === square, 'a shape takes the keyboard focus');
  await click(square);
  await until(() => cmds('pocket.plan').length > before, 'the new shape is planned');
  eq(last('cmd', 'pocket.plan').args.pocket_shape, 'square', 'sent as pocket_shape');
  await reply(last('cmd', 'pocket.plan'), {...PLAN, shape: 'square'});
  await until(() => last('cmd', 'settings.save'), 'kept for the preset');
  eq(last('cmd', 'settings.save').args.settings.pocket_shapes, {'nfc-sticker-25': 'circle', 'magnet-disc-6x3': 'square'}, 'added to the ones kept');
  await reply(last('cmd', 'settings.save'), {...saved, pocket_shapes: {'nfc-sticker-25': 'circle', 'magnet-disc-6x3': 'square'}});
  eq(picked(), ['Square'], 'shown as picked');
  eq(toasts().length, 0, 'kept quietly');
  const n = cmds('settings.save').length;
  const button = name => qa('[data-test=pocket-shape] button').find(b => text(b) === name);
  await click(button('Circle'));
  await click(button('Rectangle'));
  await until(() => cmds('settings.save').length === n + 1, 'the first quick pick is saved');
  eq(last('cmd', 'settings.save').args.settings.pocket_shapes['magnet-disc-6x3'], 'circle', 'first the first');
  await reply(last('cmd', 'settings.save'), {...saved, pocket_shapes: {'nfc-sticker-25': 'circle', 'magnet-disc-6x3': 'circle'}});
  await until(() => cmds('settings.save').length === n + 2, 'the second quick pick is not lost');
  eq(last('cmd', 'settings.save').args.settings.pocket_shapes, {'nfc-sticker-25': 'circle', 'magnet-disc-6x3': 'rectangle'}, 'then the newest');
  await reply(last('cmd', 'settings.save'), {...saved, pocket_shapes: {'nfc-sticker-25': 'circle', 'magnet-disc-6x3': 'rectangle'}});
  await sleep(100);
  eq(cmds('settings.save').length, n + 2, 'and nothing more');
  eq(picked(), ['Rectangle'], 'the newest shown');
`);

test('embedded on a side face the shape picker is off and says why; Open turns it back on', `
  await loaded();
  await place({...PLAN, face: 'side', shape: 'slot', size: [6.4, 3.4, 6.2], outer: [7.4, 3.9]});
  assert(qa('[data-test=pocket-shape] button').every(b => b.disabled), 'every shape off');
  eq(text(byTest('pocket-shape-slot')), 'On a side face an embedded insert stands on edge in a slot. The shape applies to flat faces and open pockets.', 'why');
  assert(!byTest('pocket-shape-slot').closest('.oui-hint-bubble'), 'why the picker is off stays on screen');
  eq(q('[data-test=pocket-shape]').getAttribute('aria-describedby'), 'cut-help', 'the note describes the picker');
  const before = cmds('pocket.plan').length;
  await click(qa('[data-test=mode] button').find(b => text(b) === 'Open'));
  await until(() => cmds('pocket.plan').length > before, 'Open is planned');
  await reply(last('cmd', 'pocket.plan'), {...PLAN, mode: 'open', face: 'side'});
  assert(qa('[data-test=pocket-shape] button').every(b => !b.disabled) && !byTest('pocket-shape-slot'), 'an open pocket takes any shape');
  eq(cmds('settings.save').length, 0, 'nothing stored');
`);

test('a preset chosen before the settings came takes its kept shape once hello answers', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  await fail(last('cmd', 'hello'), {code: 'internal', detail: 'boom'});
  await until(() => last('cmd', 'presets.list'), 'presets asked');
  await reply(last('cmd', 'presets.list'), PRESETS);
  await until(() => byTest('hello-retry'), 'a way to try again');
  const n = cmds('hello').length;
  await click(byTest('hello-retry'));
  await until(() => cmds('hello').length > n, 'hello again');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: {...SETTINGS, pocket_shapes: {'magnet-disc-6x3': 'circle'}}});
  await click(byTest('load'));
  await until(() => last('cmd', 'project.load'), 'load sent');
  await reply(last('cmd', 'project.load'), PROJECT);
  await serveChunks(5);
  eq(qa('[data-test=pocket-shape] button').filter(b => b.getAttribute('aria-pressed') === 'true').map(text), ['Circle'], 'the kept shape');
`);

test('a blocked embedded plan says why and offers Open', `
  await loaded();
  await place({blocked: {code: 'tilted_face', detail: 'tilted'}, preview: null, mode: 'embedded'});
  assert(text(byTest('plan-blocked')).includes('the face is tilted'), 'reason: ' + text(byTest('plan-blocked')));
  assert(text(byTest('embedded-block')).includes('Use Open'), 'mode hint: ' + text(byTest('embedded-block')));
  const embedded = qa('[data-test=mode] button').find(b => text(b) === 'Embedded');
  assert(embedded && embedded.disabled, 'Embedded disabled');
  assert(byTest('add').disabled, 'nothing to add');
  eq(byTest('add').getAttribute('aria-describedby'), 'em-plan-state', 'the disabled button points at the reason');
  assert(q('#em-plan-state').contains(byTest('plan-blocked')), 'which is the blocked plan');
`);

test('a project-level block shows the banner and starts in Open', `
  const blocked = {...PROJECT, blocks: ['by_object'], objects: [object(0, {embedded_block: 'by_object'})]};
  await loaded(blocked);
  assert(text(byTest('blocks')).includes('By object'), 'banner: ' + text(byTest('blocks')));
  assert(!byTest('embedded-block'), 'the reason is said once, in the banner');
  eq(byTest('mode').getAttribute('aria-describedby'), byTest('blocks').id, 'the disabled choice points at the banner');
  const m = await place(null);
  eq(m.args.mode, 'open', 'Open by default');
`);

test('a closed banner stays closed while its state holds and comes back when it changes', `
  const blocked = {...PROJECT, blocks: ['by_object'], objects: [object(0, {embedded_block: 'by_object'})]};
  await loaded(blocked);
  const close = q('[data-test=blocks] .oui-banner-close');
  eq(close.getAttribute('aria-label'), 'Close', 'the X is named');
  await click(close);
  assert(!byTest('blocks'), 'closed');
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 2, 'loads again');
  await reply(last('cmd', 'project.load'), blocked);
  await settle();
  assert(!byTest('blocks'), 'the same project with the same block: still closed');
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 3, 'loads a third time');
  await reply(last('cmd', 'project.load'), {...blocked, job: 'j2', blocks: ['by_object', 'raft']});
  await until(() => byTest('blocks'), 'another block: the banner is back');
`);

test('a closed banner shows again after its condition clears and returns (same key)', `
  const blocked = {...PROJECT, blocks: ['by_object'], objects: [object(0, {embedded_block: 'by_object'})]};
  await loaded(blocked);
  await click(q('[data-test=blocks] .oui-banner-close'));
  assert(!byTest('blocks'), 'closed');
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 2, 'loads again');
  await reply(last('cmd', 'project.load'), PROJECT);
  await until(() => !byTest('blocks') && byTest('mode'), 'the block is gone');
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 3, 'loads a third time');
  await reply(last('cmd', 'project.load'), blocked);
  await until(() => byTest('blocks'), 'the same block back: the banner shows again');
`);

test('the start error stays until the plugin answers: it cannot be closed while Load project is off', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  await fail(last('cmd', 'hello'), {code: 'internal', detail: 'boom'});
  assert(byTest('hello-error') && !q('[data-test=hello-error] .oui-banner-close'), 'no close button');
  await click(byTest('hello-retry'));
  await until(() => cmds('hello').length === 2, 'asks again');
  await fail(last('cmd', 'hello'), {code: 'internal', detail: 'boom again'});
  assert(byTest('hello-error') && byTest('load').disabled, 'the same failure again: still said, Load still off');
  await click(byTest('hello-details'));
  eq(text(q('[data-test=hello-detail] code')), 'internal: boom again', 'the details are those of the last failure');
`);

test('a second apply to the same path shows its result; a closed waiting notice shows for the next send', `
  await loaded();
  const path = '/storage/cube-embedder-20261114-120000-j1.3mf';
  const res = {path, name: 'cube-embedder-20261114-120000-j1.3mf', pockets: 1, removed: 0, pauses: [], warnings: [], pruned: 0};
  await place(PLAN);
  await click(byTest('add'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  await reply(last('cmd', 'project.apply'), res);
  await until(() => byTest('result-banner'), 'result shown');
  await click(q('[data-test=result-banner] .oui-banner-close'));
  assert(!byTest('result-banner'), 'result closed');

  await click(byTest('open'));
  await until(() => byTest('waiting'), 'waiting for OrcaSlicer');
  await click(q('[data-test=waiting] .oui-banner-close'));
  assert(!byTest('waiting'), 'waiting closed');
  await reply(last('cmd', 'project.open'), {open: 'asked'});
  await settle();
  assert(!byTest('waiting'), 'the answer came: no waiting notice');
  await click(byTest('open'));
  await until(() => byTest('waiting'), 'sent again: the waiting notice is back');
  await reply(last('cmd', 'project.open'), {open: 'asked'});

  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 2, 'loads again');
  await reply(last('cmd', 'project.load'), PROJECT);
  await serveChunks(5);
  await until(() => !byTest('fallback-place').disabled, 'meshes ready');
  await place(PLAN);
  await click(byTest('add'));
  await click(byTest('apply'));
  await until(() => cmds('project.apply').length === 2, 'applied again');
  await reply(last('cmd', 'project.apply'), res);
  await until(() => byTest('result-banner'), 'a second apply to the same path: its result shows');
`);

test('a toast sits bottom-left with a Close button, and goes when closed', `
  await ready();
  await tab('settings');
  await until(() => last('cmd', 'copies.status'), 'status asked');
  await reply(last('cmd', 'copies.status'), {count: 3, bytes: 3 * 1024 * 1024, kept: 2});
  await click(byTest('copies-clear'));
  await yes();
  await until(() => last('cmd', 'copies.clear'), 'clear sent');
  await reply(last('cmd', 'copies.clear'), {removed: 3, freed: 3 * 1024 * 1024, failed: 0, count: 0, bytes: 0, kept: 2});
  await until(() => toasts().length === 1, 'one toast');
  const el = toasts()[0];
  eq(toastText(el), 'Deleted 3 old copies, 3.0 MB freed.', 'what it says');
  eq(el.getAttribute('role'), 'status', 'a success is polite');
  await until(() => !document.getAnimations().some(a => a.playState === 'running'), 'the toast is in');
  const r = el.getBoundingClientRect();
  assert(r.left <= 24 && r.right < innerWidth / 2 + 200, 'left: ' + JSON.stringify(r));
  const gap = () => byTest('settings-status').getBoundingClientRect().top - el.getBoundingClientRect().bottom;
  await until(() => gap() >= 0 && gap() <= 24, 'at the bottom, just above the status line of Settings');
  const close = q('.oui-toast-close', el);
  eq(close.getAttribute('aria-label'), 'Close', 'the X is named');
  await click(close);
  await until(() => !toasts().length, 'closed');
`);

test('warnings are shown in words', `
  await loaded();
  await place({...PLAN, warnings: ['thin_cover', 'nfc_near_magnet']});
  const w = qa('[data-test=plan-warning]').map(text);
  eq(w.length, 2, 'two warnings');
  assert(w[0].includes('thinner than two layers') && w[1].includes('within 10 mm'), 'texts: ' + w);
`);

test('hold warnings are one short sentence each, and say to test the hold', `
  await loaded();
  await place({...PLAN, warnings: ['weak_magnet_hold', 'hold_uncertain']});
  const w = qa('[data-test=plan-warning]').map(text);
  eq(w.length, 2, 'two warnings');
  eq(w, ['These magnets may not hold this model. Use larger or stronger magnets, or more of them, and test the hold.',
    'Hold strength is a rough estimate for this model. Test it before you rely on it.'], 'texts');
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
    pauses: [{top_z: 19, extra: 'Embedder: insert 1 x 6x3 magnet (N up)', items: [{label: '6x3 magnet', polarity: 'N', n: 1}]}], warnings: ['existing_gcode_at_layer'], pruned: 2});
  eq(text(byTest('result-pruned')), '2 older copies were deleted from the plugin folder.', 'pruned shown');
  eq(text(byTest('result-banner')), 'New copy written. 1 pocket added to a new copy of cube. 1 pocket removed.', 'what was done, by the project name');
  eq(text(q('[data-test=result] .oui-panel-title')), 'cube', 'the card is named after the project');
  assert(text(byTest('result-pauses')).includes('1 pc Ø6 × 3 mm disc (N up)') && !text(byTest('result')).includes('Embedder: insert'), 'the pause in the page words, not the G-code comment: ' + text(byTest('result-pauses')));
  assert(text(byTest('result')).includes('Save Project As'), 'save-as note');
  assert(text(byTest('result')).includes('Your own custom G-code'), 'apply warning');
  assert(!byTest('result-path') && !text(byTest('result')).includes('cube-embedder') && !text(byTest('result')).includes('/storage'), 'no file name and no folder while all is well: ' + text(byTest('result')));
  assert(!byTest('apply') && !byTest('viewer') && !byTest('no3d') && !byTest('preset'), 'the job is over: no more staging on this copy');
  assert(text(byTest('result')).includes('Load project'), 'result asks for a new load: ' + text(byTest('result')));
  await click(byTest('open'));
  await until(() => last('cmd', 'project.open'), 'open sent');
  eq(last('cmd', 'project.open').args, {path}, 'open arguments');
  await reply(last('cmd', 'project.open'), {open: 'asked'});
  assert(text(byTest('opened')).includes('asked to open') && !byTest('result-path'), 'opened: ' + text(byTest('opened')));
  eq([text(byTest('result-reload')), text(byTest('reload'))], ['Load project again', 'Load project again'], 'the way on is on the card, named as in the bar');
  await click(byTest('result-reload'));
  await until(() => cmds('project.load').length === 2, 'loads again');
`);

test('when OrcaSlicer cannot be asked to open the copy, the result says where the file is', `
  await loaded();
  eq(rows('existing'), [['Ø6 × 3 mm disc', 'Embedded']], 'a pocket the project already holds, as a row');
  eq(q('#rm-9').getAttribute('aria-label'), 'Remove Ø6 × 3 mm disc (Embedded)', 'its bin says what it removes');
  q('#rm-9').focus();
  await click(q('#rm-9'));
  eq(rows('existing'), [['Ø6 × 3 mm disc', 'Will be removed in the new copy']], 'marked: the row says what will happen');
  eq([text(q('#rm-9')), q('#rm-9').getAttribute('aria-label')], ['Undo', 'Keep Ø6 × 3 mm disc'], 'with the way back where the bin was');
  assert(document.activeElement === q('#rm-9'), 'and the focus still on it');
  await click(q('#rm-9'));
  assert(!byTest('summary') && byTest('apply').disabled, 'Undo takes the removal back');
  await click(q('#rm-9'));
  eq(text(byTest('summary')), '1 pocket to remove. Apply writes a new copy.', 'a removal alone');
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  const path = '/storage/cube-embedder-20261114-120000-j1.3mf';
  await reply(last('cmd', 'project.apply'), {path, name: 'cube-embedder-20261114-120000-j1.3mf', pockets: 0, removed: 1, pauses: [], warnings: [], pruned: 0});
  eq(text(byTest('result-banner')), 'New copy written. 1 pocket removed in a new copy of cube.', 'a removal alone is said as one');
  await click(byTest('open'));
  await until(() => last('cmd', 'project.open'), 'open sent');
  await reply(last('cmd', 'project.open'), {open: 'none'});
  assert(text(byTest('opened')).includes('could not be started'), 'said: ' + text(byTest('opened')));
  eq(text(byTest('result-path')), path, 'now the path is shown');
  assert(byTest('copy-path'), 'with a button to copy it');
`);

test('a stale job error tells the user to load again', `
  await loaded();
  const m = await place(null);
  await fail(m, {code: 'stale_job', detail: 'the project was loaded again; load it once more'});
  assert(alerts().includes('The project was loaded again. Load it once more'), 'alert: ' + alerts());
  assert(!alerts().includes('load it once more)'), 'the English detail is not repeated after the sentence: ' + alerts());
  assert(byTest('plan-empty') && byTest('add').disabled, 'no preview kept, the panel asks for a face again');
`);

test('without WebGL the page says so and keeps the face form', `
  await loaded();
  eq(text(q('[data-test=no3d] .oui-panel-title')), 'Place without the 3D view', 'the panel says what it is, once');
  assert(text(byTest('no3d')).includes('Choose the face') && !text(byTest('no3d')).includes('not available'), 'then how, not the same thing again: ' + text(byTest('no3d')));
  assert(byTest('no3d').getBoundingClientRect().height < 200, 'as tall as its one row, not a screen of empty panel');
  assert(!byTest('viewer'), 'no 3D view');
  eq(text(byTest('plan-empty')), 'Choose a face and press Place.', 'the plan asks for the face form');
`);

test('settings show the saved values and the user presets', `
  await ready();
  await tab('settings');
  eq(q('#set-xy_clearance').value, '0.2 mm', 'clearance shown');
  assert(!byTest('settings-save') && !byTest('settings-discard'), 'no Save or Discard: settings are saved as they change');
  eq(text(byTest('settings-status')), 'Changes are saved as you make them.', 'and one line says so');
  assert(byTest('presets-empty'), 'no user presets');
`);

test('a changed setting is saved by itself and plans the staged pockets again; one that no longer fits is dropped, saying so', `
  await loaded();
  const m = await place(PLAN);
  await click(byTest('add'));
  const lid = await place(null);
  await reply(lid, {...PLAN, label: 'Lid magnet'});
  await click(byTest('add'));
  await tab('settings');
  const before = cmds('pocket.plan').length;
  await type(q('#set-xy_clearance'), '0.4');
  q('#set-xy_clearance').blur();
  await until(() => last('cmd', 'settings.save'), 'saved without a Save button');
  eq(last('cmd', 'settings.save').args.settings.xy_clearance, 0.4, 'the new clearance');
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
  assert(text(byTest('staged')).includes('Ø6 × 3 mm disc') && !text(byTest('staged')).includes('Lid magnet'), 'staged: ' + text(byTest('staged')));
`);

test('Centre on the face plans again with center and keeps it for Apply', `
  await loaded();
  const m = await place(PLAN);
  assert(!('center' in m.args), 'off by default');
  const before = cmds('pocket.plan').length;
  await click(q('#f-center'));
  await until(() => cmds('pocket.plan').length > before, 'planned again');
  eq(last('cmd', 'pocket.plan').args.center, true, 'center sent');
  await reply(last('cmd', 'pocket.plan'), PLAN);
  await click(byTest('add'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  eq(last('cmd', 'project.apply').args.pockets[0].center, true, 'center kept for Apply');
`);

test('Auto fridge magnet stages symmetric bottom pockets in one click', `
  await loaded();
  await click(byTest('auto-fridge-2'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'auto_fridge sent');
  const m = last('cmd', 'pocket.auto_fridge');
  eq([m.args.job, m.args.object, m.args.count, m.args.preset], ['j1', 0, 2, 'magnet-disc-6x3'], 'auto_fridge args');
  const p1 = {object: 0, part: 0, tri: 0, point: [104, 110, 0], preset: 'magnet-disc-6x3', mode: 'embedded'};
  const p2 = {object: 0, part: 0, tri: 0, point: [116, 110, 0], preset: 'magnet-disc-6x3', mode: 'embedded'};
  await reply(m, {
    count: 2,
    items: [
      {args: p1, plan: {...PLAN, face: 'bottom', pause_z: 3.8, point: [104, 110, 0]}},
      {args: p2, plan: {...PLAN, face: 'bottom', pause_z: 3.8, point: [116, 110, 0]}},
    ],
  });
  await settle();
  eq(rows('staged').length, 2, 'two bottom pockets staged');
  eq(rows('staged')[0][1], 'Cube · bottom · embedded · pause at Z 3.80 mm', 'bottom row');
`);

test('removing one auto fridge pocket plans the rest of that object again', `
  await loaded();
  await click(byTest('auto-fridge-2'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'auto_fridge sent');
  const mk = x => ({object: 0, part: 0, tri: 0, point: [x, 110, 0], preset: 'magnet-disc-6x3', mode: 'embedded', fridge: true});
  const weak = {...PLAN, face: 'bottom', pause_z: 3.8, warnings: []};
  await reply(last('cmd', 'pocket.auto_fridge'), {count: 2, items: [{args: mk(104), plan: weak}, {args: mk(116), plan: weak}]});
  await settle();
  eq(rows('staged').length, 2, 'two staged');
  const before = cmds('pocket.plan').length;
  await click(qa('[data-test=staged] button[aria-label]')[0]);
  await until(() => cmds('pocket.plan').length > before, 'the remaining fridge pocket is planned again');
  const m = last('cmd', 'pocket.plan');
  eq(m.args.fridge, true, 'with its fridge marker');
  await reply(m, {...weak, warnings: ['weak_magnet_hold']});
  await settle();
  eq(qa('[data-test=hold-warning]').map(text), ['Cube: These magnets may not hold this model. Use larger or stronger magnets, or more of them, and test the hold.'], 'the advisory shows for the pocket left, once, above the rows');
  eq(qa('[data-test=row-hold]').length, 1, 'and its row carries the mark');
`);

test('a failed re-plan of the fridge pockets left never keeps the old plan as enough', `
  await loaded();
  await click(byTest('auto-fridge-2'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'auto_fridge sent');
  const mk = x => ({object: 0, part: 0, tri: 0, point: [x, 110, 0], preset: 'magnet-disc-6x3', mode: 'embedded', fridge: true});
  const ok = {...PLAN, face: 'bottom', pause_z: 3.8, warnings: []};
  await reply(last('cmd', 'pocket.auto_fridge'), {count: 2, items: [{args: mk(104), plan: ok}, {args: mk(116), plan: ok}]});
  await settle();
  const before = cmds('pocket.plan').length;
  await click(qa('[data-test=staged] button[aria-label]')[0]);
  await until(() => cmds('pocket.plan').length > before, 'the remaining fridge pocket is planned again');
  await fail(last('cmd', 'pocket.plan'), {code: 'internal', detail: 'boom'});
  await settle();
  assert(text(byTest('hold-warnings')).includes('rough estimate'), 'the list says the hold is unknown: ' + text(byTest('hold-warnings')));
`);

test('auto fridge says its hold advisory once for the object, not on every row; a pocket keeps its own warnings', `
  await loaded();
  await click(byTest('auto-fridge-auto'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'auto_fridge sent');
  eq([last('cmd', 'pocket.auto_fridge').args.object, last('cmd', 'pocket.auto_fridge').args.count], [0, 'auto'], 'the selected object, as many as it takes');
  const mk = x => ({object: 0, part: 0, tri: 0, point: [x, 110, 0], preset: 'magnet-disc-6x3', mode: 'embedded', fridge: true});
  const plan = extra => ({...PLAN, face: 'bottom', pause_z: 3.8, warnings: ['hold_uncertain', ...extra]});
  await reply(last('cmd', 'pocket.auto_fridge'), {count: 4, items: [{args: mk(96), plan: plan([])}, {args: mk(104), plan: plan(['thin_cover'])},
    {args: mk(110), plan: plan([])}, {args: mk(116), plan: plan([])}]});
  await settle();
  eq(rows('staged').length, 4, 'four pockets');
  eq(qa('[data-test=hold-warning]').map(text), ['Cube: Hold strength is a rough estimate for this model. Test it before you rely on it.'], 'said once, naming the object (the plate has two)');
  eq(qa('[data-test=row-hold]').length, 4, 'each row it covers carries a mark');
  eq(qa('[data-test=row-pick]').map(b => b.getAttribute('aria-describedby')), Array(4).fill('em-holds'), 'that points at the sentence');
  eq(qa('[data-test=row-warning]').map(text), ['The cover is thinner than two layers; the insert may show through.'], 'the warning of one pocket stays on its row');
  eq(qa('[data-test=pauses] li').map(text), ['Z 3.80 mm: insert 4 pcs Ø6 × 3 mm disc'], 'a count and the insert, not the same sign twice');
`);

test('fridge magnets for all objects: the tick sends every object with the count chosen', `
  await loaded();
  assert(byTest('auto-fridge').closest('.em-list') && !q('.em-form [data-test=auto-fridge]'), 'the action sits with the list it fills, not among the settings of a pocket');
  eq(qa('[data-test=auto-fridge] button').map(b => text(b) + '|' + (b.getAttribute('aria-label') || '')), ['Auto|Auto', '1|1 magnet', '2|2 magnets', '4|4 magnets'], 'the counts, named for a screen reader');
  await click(q('#f-fridge-all'));
  await click(byTest('auto-fridge-4'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'sent');
  eq([last('cmd', 'pocket.auto_fridge').args.object, last('cmd', 'pocket.auto_fridge').args.count], ['all', 4], 'all objects, four each');
`);

for (const [width, cols] of [[1280, 'three columns'], [960, 'two columns']]) {
  test(`${cols}: after a click on a face the plan, its warnings, Add pocket and Apply are in the window and the page is one screen`, `
  await loaded({...PROJECT, blocks: ['by_object']});
  await place({...PLAN, warnings: ['thin_cover', 'nfc_near_magnet', 'breaks_surface']});
  const box = el => el.getBoundingClientRect();
  const inWindow = el => box(el).height > 0 && box(el).top >= 0 && box(el).bottom <= innerHeight;
  assert(byTest('blocks'), 'with a banner above the panels');
  eq(text(byTest('blocks')), 'Embedded pockets are off for this plate. Because the print sequence is By object, and OrcaSlicer ignores pauses then. Open pockets still work.', 'which reads as one explanation');
  assert(inWindow(byTest('add')) && !byTest('add').disabled && !byTest('add').classList.contains('p-button-secondary'), 'Add pocket, the one thing to press, as the main button');
  assert(qa('[data-test=plan-warning]').length === 3 && qa('[data-test=plan-warning]').every(inWindow), 'every warning of the pocket');
  assert(box(qa('[data-test=plan-warning]')[2]).bottom <= box(byTest('plan-label')).top, 'the warnings come before the facts');
  assert(inWindow(byTest('plan-pause')) && inWindow(byTest('plan-cover')), 'where it pauses and what covers it');
  eq(qa('#em-plan-state dt').map(text), ['Insert', 'Pause', 'Cover'], 'three facts');
  assert(!byTest('plan-more').open && text(q('summary', byTest('plan-more'))) === 'Dimensions', 'the geometry is behind Dimensions');
  assert(inWindow(byTest('apply')), 'Apply');
  assert(${width === 1280} ? box(byTest('no3d')).right <= box(q('.em-list')).left : box(byTest('no3d')).bottom <= box(q('.em-list')).top && box(byTest('no3d')).left >= box(q('.em-form')).right,
    '${cols}: ' + ${JSON.stringify(width === 1280 ? 'the list beside the view' : 'the list under the view, beside the form')});
  eq(document.documentElement.scrollHeight, innerHeight, 'the page is one screen: nothing is a scroll away');
  // the list: what the project already holds comes first, and nothing is laid over the footer
  const parts = ['existing', 'staged-empty', 'auto-fridge'].map(n => box(byTest(n)));
  assert(parts[0].bottom <= parts[1].top && parts[1].bottom <= parts[2].top, 'the project pockets, then the empty line, then fridge magnets: none over another');
  const body = q('.em-list > .oui-panel-body'), foot = q('.em-list > .oui-panel-foot');
  assert(box(body).bottom <= box(foot).top + 1 && getComputedStyle(body).overflowY === 'auto', 'the list scrolls above its footer, never under it');
  assert(!byTest('summary'), 'and the footer does not count zero pockets');
`, { width });
}

test('a command that answers at once is never said to be still working; one that takes long is, after a moment', `
  await loaded();
  let seen = 0;
  const obs = new MutationObserver(() => { if (byTest('waiting')) seen++; });
  obs.observe(document.body, { subtree: true, childList: true });
  await click(byTest('auto-fridge-2'));
  await until(() => last('cmd', 'pocket.auto_fridge'), 'sent');
  await reply(last('cmd', 'pocket.auto_fridge'), {count: 0, items: []});
  await tab('settings');
  await until(() => last('cmd', 'copies.status'), 'the copies check, which nobody asked for by name');
  await sleep(900);
  eq(seen, 0, 'no banner came and went, and none for a background read');
  await tab('embed');
  await click(byTest('auto-fridge-2'));
  await sleep(250);
  assert(!byTest('waiting'), 'not at once');
  await until(() => byTest('waiting'), 'said once it takes long');
  obs.disconnect();
  eq(text(byTest('waiting')), 'Still working: Placing bottom magnet pockets…', 'in plain words');
`);

test('a failed command says so in words; what Python said is offered to copy, never shown', `
  await loaded();
  await click(q('#rm-9'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  await fail(last('cmd', 'project.apply'), {code: 'internal', detail: 'KeyError: printable_area'});
  assert(alerts().includes('Apply failed: Embedder ran into an unexpected problem'), 'alert: ' + alerts());
  assert(!document.body.innerText.includes('KeyError'), 'no exception text on the page');
  await click(btn('Copy details', q('.oui-toasts')));
  await until(() => toasts().some(t => /^Copied\\.|^Could not copy\\./.test(toastText(t))), 'the copy is confirmed, or the text is given to copy by hand');
`);

test('the list says which inserts to have ready, open pockets and copies included', `
  await loaded();
  await place({...PLAN, copies: 2});
  await click(byTest('add'));
  await place({...PLAN, mode: 'open', pause_z: null, label: '25 mm NFC sticker', kind: 'nfc'});
  await click(byTest('add'));
  eq(text(q('#em-inserts-l')), 'Have ready at the printer', 'inserts heading');
  eq(qa('[data-test=inserts] li').map(text), ['2 Ø6 × 3 mm disc', '1 Ø25 mm sticker'], 'inserts lines: the count as a chip, then the insert');
  eq(qa('[data-test=inserts] .em-kind').map(e => e.dataset.kind), ['magnet', 'nfc'], 'each with the mark of its kind');
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 19.00 mm'], ['Ø25 mm sticker', 'Cube · top · open']], 'rows');
`);

test('Apply refused for one staged pocket says which pocket and why', `
  await loaded();
  await place(PLAN);
  await click(byTest('add'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  await fail(last('cmd', 'project.apply'), {code: 'pocket_blocked', detail: 'pocket 1: no_floor'});
  assert(alerts().includes('A staged pocket can no longer be made (pocket 1: no printed layer would sit under the pocket'), 'alert: ' + alerts());
`);

test('a cut object is named in the error', `
  await loaded();
  const m = await place(null);
  await fail(m, {code: 'cut_object', detail: 'Lid'});
  assert(alerts().includes('This object was cut with connectors; Embedder cannot add parts to it (Lid)'), 'alert: ' + alerts());
`);

test('a project without a part list says why in words', `
  await loaded();
  const m = await place(null);
  await fail(m, {code: 'no_model_settings', detail: 'the project has no model_settings.config'});
  assert(alerts().includes('no OrcaSlicer part list'), 'alert: ' + alerts());
`);

test('settings show the old copies and clear them after asking', `
  await ready();
  await tab('settings');
  await until(() => last('cmd', 'copies.status'), 'status asked');
  await reply(last('cmd', 'copies.status'), {count: 3, bytes: 3 * 1024 * 1024, kept: 2});
  eq(text(byTest('copies-status')), '3 old copies can be deleted (3.0 MB).', 'status');
  await click(byTest('copies-clear'));
  await no();
  assert(!last('cmd', 'copies.clear'), 'nothing cleared when the answer is no');
  await click(byTest('copies-clear'));
  await yes();
  await until(() => last('cmd', 'copies.clear'), 'clear sent');
  await reply(last('cmd', 'copies.clear'), {removed: 2, freed: 2 * 1024 * 1024, failed: 1, count: 1, bytes: 1024 * 1024, kept: 2});
  assert(alerts().includes('could not be deleted'), 'failure said: ' + alerts());
  assert(text(document.body).includes('Deleted 2 old copies, 2.0 MB freed.'), 'freed shown');
  eq(text(byTest('copies-status')), '1 old copy can be deleted (1.0 MB).', 'status after');
  await tab('embed');
  await tab('settings');
  await until(() => cmds('copies.status').length === 2, 'asked again when the tab opens');
`);

test('the cover row and Save as preset carry their icons', `
  await loaded();
  await place(PLAN);
  const cover = qa('[data-test=plan] dt').find(d => text(d) === 'Cover');
  assert(cover && q('svg.oui-icon', cover), 'layers icon on the cover row');
  await custom();
  const save = byTest('save-preset');
  assert(q('svg.oui-icon', save) && text(save) === 'Save as preset', 'save icon on Save as preset: ' + text(save));
`);

test('a custom size is saved as a preset through a dialog with one field; going back saves nothing', `
  await loaded();
  await custom();
  assert(byTest('custom-dims') && text(byTest('preset')) === 'Custom size…', 'the fields open under the list, which names the choice');
  await type(q('#f-d'), '12'); q('#f-d').blur(); await settle();
  byTest('save-preset').focus();
  await click(byTest('save-preset'));
  await until(dialogOpen, 'dialog');
  assert(dialogText().includes('Give this size a name'), 'dialog text: ' + dialogText());
  assert(q('[data-dlg=confirm]').disabled, 'no name, no save');
  await no();
  assert(!last('cmd', 'presets.save'), 'nothing saved when the answer is Cancel');
  await until(() => document.activeElement === byTest('save-preset'), 'focus returns to the button that asked');
  await click(byTest('save-preset'));
  await until(() => q('#dlg-input'), 'dialog again');
  await type(q('#dlg-input'), 'Fridge 12');
  await press('Enter');
  await until(() => last('cmd', 'presets.save'), 'save sent');
  eq(last('cmd', 'presets.save').args, {preset: {name: 'Fridge 12', kind: 'magnet', shape: 'disc', d: 12, t: 3}}, 'preset arguments');
  const mine = {id: 'user-1', name: 'Fridge 12', kind: 'magnet', shape: 'disc', d: 12, t: 3, builtin: false};
  await reply(last('cmd', 'presets.save'), {id: 'user-1', user: [mine]});
  await until(() => byTest('preset'), 'back to the preset list');
  eq(text(byTest('preset')), 'Fridge 12', 'the new preset is chosen');
  eq(q('[data-test=preset] .em-kind').dataset.kind, 'magnet', 'with the mark of its kind');
`);

test('deleting a preset asks first, with the way back focused', `
  await until(() => last('cmd', 'hello'), 'hello sent');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: SETTINGS});
  await until(() => last('cmd', 'presets.list'), 'presets asked');
  const mine = {id: 'user-1', name: 'Fridge 12', kind: 'nfc', shape: 'block', l: 30, w: 20, t: 1, builtin: false};
  await reply(last('cmd', 'presets.list'), {...PRESETS, user: [mine]});
  await tab('settings');
  eq(rows('user-presets'), [['Fridge 12', 'NFC tag · 30 × 20 × 1 mm block']], 'the preset row, its size written as in the picker');
  await click(btn('Delete Fridge 12'));
  await until(dialogOpen, 'dialog');
  assert(dialogText().includes('"Fridge 12" will be removed'), 'what will happen: ' + dialogText());
  await until(() => document.activeElement === q('[data-dlg=cancel]'), 'focus starts on the way out');
  eq(text(q('[data-dlg=cancel]')), 'Cancel', 'which is called Cancel');
  assert(q('[data-dlg=confirm]').classList.contains('p-button-danger') && text(q('[data-dlg=confirm]')) === 'Delete', 'the action is named on the red button');
  await press('Escape');
  await until(() => !dialogOpen(), 'Escape closes');
  assert(!last('cmd', 'presets.delete'), 'Escape deletes nothing');
  await click(btn('Delete Fridge 12'));
  await yes();
  await until(() => last('cmd', 'presets.delete'), 'delete sent');
  eq(last('cmd', 'presets.delete').args, {id: 'user-1'}, 'delete arguments');
  await reply(last('cmd', 'presets.delete'), {user: []});
  assert(byTest('presets-empty'), 'list empty again');
`);

test('settings are saved as they change: one status line, Retry when saving fails, the last change always lands', `
  await ready();
  await tab('settings');
  await type(q('#set-cover_nfc'), '0.8');
  q('#set-cover_nfc').blur();
  await until(() => last('cmd', 'settings.save'), 'saved by itself');
  eq(last('cmd', 'settings.save').args.settings.cover_nfc, 0.8, 'the new value');
  await sleep(700);
  assert(!byTest('waiting'), 'a save is never announced as a command still working');
  await fail(last('cmd', 'settings.save'), {code: 'internal', detail: 'disk full'});
  await until(() => byTest('settings-failed'), 'the failure is said on the status line');
  assert(!toasts().length && !document.body.innerText.includes('disk full'), 'once, and without what Python said');
  eq(q('#set-cover_nfc').value, '0.8 mm', 'what was typed is kept');
  await click(byTest('settings-retry'));
  await until(() => cmds('settings.save').length === 2, 'sent again');
  // a change made while that save is out goes after it
  await type(q('#set-cover_nfc'), '0.9');
  q('#set-cover_nfc').blur();
  await sleep(600);
  eq(cmds('settings.save').length, 2, 'one save out at a time');
  await reply(last('cmd', 'settings.save'), {...SETTINGS, cover_nfc: 0.8});
  await until(() => cmds('settings.save').length === 3, 'the newer value follows');
  eq(last('cmd', 'settings.save').args.settings.cover_nfc, 0.9, 'the last change');
  await reply(last('cmd', 'settings.save'), {...SETTINGS, cover_nfc: 0.9});
  await until(() => byTest('settings-saved'), 'saved');
  eq([text(byTest('settings-saved')), q('#set-cover_nfc').value], ['Saved', '0.9 mm'], 'the line says so and the field keeps the last value');
`);

test('settings are one page: every section is in sight, with no list of pages', `
  await ready();
  await tab('settings');
  const visible = el => !!el && el.getClientRects().length > 0;
  eq(qa('#em-view-settings .oui-panel-title').filter(visible).map(text), ['Pockets', 'My presets', 'Old project copies', 'General'], 'four sections, all shown');
  assert(!q('.oui-settings-nav') && !byTest('settings-back'), 'nothing to pick a page from');
  assert(visible(byTest('lang')) && visible(byTest('version')) && visible(byTest('copies-clear')), 'language, version and old copies without a click');
  const [left, right] = [q('#set-xy_clearance'), byTest('lang')].map(e => e.getBoundingClientRect());
  assert(right.left > left.right, 'two columns when there is room');
  const bar = byTest('settings-status').getBoundingClientRect();
  assert(Math.abs(bar.bottom - innerHeight) <= 1, 'the status line is along the bottom edge: ' + bar.bottom);
`);

test('settings in a narrow window: one column, the status line stays, nothing overflows', `
  await ready();
  await tab('settings');
  const [first, second] = [q('#set-xy_clearance'), byTest('lang')].map(e => e.getBoundingClientRect());
  assert(second.top > first.bottom, 'one column');
  const bar = byTest('settings-status').getBoundingClientRect();
  assert(bar.height > 0 && bar.bottom <= innerHeight + 1, 'the status line is in the window: ' + bar.bottom);
  assert(document.documentElement.scrollWidth <= innerWidth, 'nothing overflows');
`, { width: 480 });

test('a setting left empty is flagged on its row and nothing is saved until it has a value', `
  await ready();
  await tab('settings');
  await type(q('#set-cover_nfc'), '');
  q('#set-cover_nfc').blur();
  await settle();
  const row = q('#set-cover_nfc').closest('.oui-formrow');
  eq(text(q('[role=alert]', row)), 'Enter a value.', 'said on the row');
  await type(q('#set-xy_clearance'), '0.3');
  q('#set-xy_clearance').blur();
  await sleep(700);
  assert(!last('cmd', 'settings.save'), 'nothing is saved with a value missing');
  await type(q('#set-cover_nfc'), '0.7');
  q('#set-cover_nfc').blur();
  await until(() => last('cmd', 'settings.save'), 'saved once every value is there');
  eq([last('cmd', 'settings.save').args.settings.cover_nfc, last('cmd', 'settings.save').args.settings.xy_clearance], [0.7, 0.3], 'both changes');
  assert(!q('[role=alert]', row), 'flag gone');
`);

test('the language choice is sent to the plugin and the page follows it', `
  await ready();
  await tab('settings');
  await click(byTest('lang'));
  await until(() => qa('[role=option]').length === 7, 'language options');
  eq(qa('[role=option]').map(text).slice(1), ['English', 'Português (Brasil)', 'Español', 'Deutsch', '简体中文', 'Polski'], 'each language in its own name');
  await click(qa('[role=option]').find(o => text(o) === 'Português (Brasil)'));
  eq(last('ui_language').value, 'pt-BR', 'choice sent');
  eq(document.documentElement.lang, 'pt-BR', 'document language');
  eq(text(q('[data-tab=embed]')), 'Embutir', 'tabs follow');
  assert(text(byTest('embed-empty')).includes('Nenhum projeto carregado'), 'the page follows');
`);

test('three columns side by side: the form, the view and the list fill the window', `
  await loaded();
  const r = name => q(name).getBoundingClientRect();
  const form = r('.em-form'), view = r('.em-stage-panel'), list = r('.em-list');
  eq([Math.round(form.width), Math.round(list.width)], [320, 380], 'side columns');
  assert(form.right < view.left && view.right < list.left, 'in reading order: form, view, list');
  eq([form.top, list.top], [view.top, view.top], 'on one line');
  assert(form.height > innerHeight - 110 && Math.round(form.bottom) === Math.round(list.bottom) && list.bottom < innerHeight, 'the panels take the window height under the bar: ' + form.height);
  eq(document.documentElement.scrollHeight, innerHeight, 'and the page is one screen');
  // A classic scrollbar keeps its gutter reserved (scrollbar-gutter: stable) even while the page does not scroll; the
  // root's clientWidth then still counts the gutter, so the content is at most that wide, and narrower by the gutter.
  const root = document.documentElement;
  assert(root.scrollWidth <= root.clientWidth, 'nothing wider than the window: ' + root.scrollWidth + ' > ' + root.clientWidth);
  eq(getComputedStyle(document.documentElement).scrollbarGutter, 'stable', 'a scrollbar appearing does not narrow the page');
  const foot = r('.em-list .oui-panel-foot');
  assert(Math.abs(foot.bottom - list.bottom) < 2, 'Apply sits at the foot of the list');
  document.documentElement.style.setProperty('--orca-bg', '#151515');   // the host's theme, not the runner's
  await until(() => document.documentElement.classList.contains('orca-dark'), 'dark', 15000);
  eq(getComputedStyle(q('.em-form .oui-panel-head')).backgroundColor, 'rgba(0, 0, 0, 0)', 'panel headers are neutral: no tinted strip');
  eq(getComputedStyle(q('.em-form')).backgroundColor, 'rgb(45, 45, 49)', "panels are OrcaSlicer's panel grey");
  eq(getComputedStyle(q('.em-list .oui-panel-head .oui-panel-icon')).color, 'rgb(185, 220, 108)', 'the list icon is lime; nothing else in the header is');
  // The token, not the button's computed colour: that one is still in its 120 ms transition right after the theme changed.
  eq(getComputedStyle(document.documentElement).getPropertyValue('--oui-primary').trim(), '#00675b', "the primary action is OrcaSlicer's teal");
  eq(getComputedStyle(byTest('apply')).height, '32px', 'control height');
  eq(getComputedStyle(q('.em-form')).borderRadius, '6px', 'panel radius');
`);

test('one column when the window is narrow, in the order form, view, list; nothing overflows', `
  await loaded();
  const r = name => q(name).getBoundingClientRect();
  const form = r('.em-form'), view = r('.em-stage-panel'), list = r('.em-list');
  assert(form.bottom <= view.top && view.bottom <= list.top, 'stacked in order');
  const room = document.documentElement.clientWidth;   // the window less a classic scrollbar, where the system draws one
  eq([form.left, view.left, list.left], [16, 16, 16], 'page gutter');
  eq([form.width, view.width, list.width], [room - 32, room - 32, room - 32], 'full width');
  eq(document.documentElement.scrollWidth, room, 'nothing wider than the window');
  const bar = r('.oui-appbar');
  assert(r('.oui-appbar-tabs').top > r('.oui-appbar-id').top && bar.height < 110, 'tabs drop to a second line');
  for (const b of qa('button').filter(b => b.getClientRects().length && text(b))) assert(b.scrollWidth <= b.clientWidth + 1, 'label fits its button: ' + text(b));
  const bin = q('#rm-9').getBoundingClientRect(), icon = q('#rm-9 svg').getBoundingClientRect();
  assert(icon.left >= bin.left && icon.right <= bin.right && bin.right <= r('.em-list').right, 'and an icon button holds its icon, inside the panel');
`, { width: 480, lang: 'pt_BR' });

// ------------------------------------------------------------------ moving pockets
test('a pocket of the list taken in hand is changed by the form in place; a change that blocks it is not taken', `
  await loaded();
  await place(PLAN);
  await click(byTest('add'));
  await place({...PLAN, label: 'Second'});
  await click(byTest('add'));
  eq(text(byTest('staged-help')), 'Select a pocket to change it.', 'without the 3D view there is no dragging to offer');
  const picks = () => qa('[data-test=row-pick]');
  const pressed = () => picks().map(b => b.getAttribute('aria-pressed'));
  eq(pressed(), ['false', 'false'], 'nothing in hand at first');
  const before = cmds('pocket.plan').length;
  await click(picks()[1]);
  eq(pressed(), ['false', 'true'], 'the row is a toggle');
  eq(qa('[data-test=staged] li').map(li => li.hasAttribute('data-selected')), [false, true], 'and is marked');
  eq(text(q('.em-form .oui-panel-title')), 'Selected pocket', 'the form says what it changes');
  assert(byTest('done') && !byTest('add'), 'nothing to add: the pocket is on the list already');
  assert(text(byTest('plan-label')) === 'Second' && text(byTest('plan-at')).startsWith('X 100.0 · Y 100.0 · Z 20.0 mm'), 'its plan and where it is: ' + text(byTest('plan')));
  eq(cmds('pocket.plan').length, before, 'taking a pocket in hand plans nothing: it is shown as it is');
  await click(qa('[data-test=mode] button').find(b => text(b) === 'Open'));
  await until(() => cmds('pocket.plan').length > before, 'the change is planned');
  const m = last('cmd', 'pocket.plan');
  eq([m.args.mode, m.args.others.length], ['open', 1], 'the pocket in hand, checked against the other one only');
  await reply(m, {...PLAN, mode: 'open', pause_z: null, label: 'Second'});
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 19.00 mm'], ['Second', 'Cube · top · open']], 'its row follows');
  eq(text(byTest('staged-count')), '2', 'no pocket was added');
  eq(qa('[data-test=pauses] li').map(text), ['Z 19.00 mm: insert 1 pc Ø6 × 3 mm disc'], 'the pauses follow too');
  await click(qa('[data-test=mode] button').find(b => text(b) === 'Embedded'));
  await until(() => cmds('pocket.plan').length > before + 1, 'planned again');
  await reply(last('cmd', 'pocket.plan'), {blocked: {code: 'no_floor', detail: ''}, preview: null, mode: 'embedded'});
  assert(notes().includes('The pocket stays as it was: no printed layer would sit under the pocket'), 'the refusal is said: ' + notes());
  eq(rows('staged')[1], ['Second', 'Cube · top · open'], 'and the pocket is as before');
  assert(text(q('#em-mode-note')).includes('Open at the surface'), 'the form shows it as it is again: ' + text(q('#em-mode-note')));
  eq(pressed(), ['false', 'true'], 'still in hand');
  await click(byTest('done'));
  eq(pressed(), ['false', 'false'], 'Done lets go of it');
  assert(byTest('add') && byTest('plan-empty') && text(q('.em-form .oui-panel-title')) === 'New pocket', 'the form is for a new pocket again');
  await click(picks()[0]);
  await click(btn('Remove 1 · Ø6 × 3 mm disc'));
  assert(byTest('add') && !byTest('done') && text(byTest('staged-count')) === '1', 'removing the pocket in hand lets go of it');
  await click(picks()[0]);
  await place(PLAN);
  eq(pressed(), ['false'], 'placing a new pocket lets go of the one in hand');
  eq(text(byTest('staged-count')), '1', 'and moves nothing');
`);

test('a click on a pocket selects it, a click on its row too; Escape and a click on nothing let go of it', `
  await loaded3d();
  eq([stage().getAttribute('role'), stage().tabIndex, stage().getAttribute('aria-label')], ['application', 0, '3D view'], 'the view is one focusable widget');
  const keys = q('#' + stage().getAttribute('aria-describedby'));
  assert(keys.classList.contains('oui-sr') && text(keys).includes('arrow keys move it 0.5 mm'), 'its keys are described: ' + text(keys));
  assert(text(q('.em-hint')).includes('drag a pocket to move it'), 'the hint says a pocket can be dragged: ' + text(q('.em-hint')));
  const m = await place3d(TOP_A);
  assert(Math.abs(m.args.point[2] - 20) < 1e-3 && dist(m.args.point, [100, 100, 20]) < 3, 'the spot is on the top face: ' + m.args.point);
  await click(byTest('add'));
  eq(text(byTest('staged-help')), 'Select a pocket to change it. Drag it in the 3D view to move it.', 'the list says how');
  const pressed = () => byTest('row-pick').getAttribute('aria-pressed');
  eq(pressed(), 'false', 'on the list, not in hand');
  eq(await clickAt(TOP_A), null, 'a click on a pocket places nothing');
  eq(pressed(), 'true', 'it takes the pocket in hand, and its row shows it');
  assert(byTest('done') && text(byTest('plan-pause')).includes('19'), 'the form shows the pocket');
  eq(document.activeElement, stage(), 'the keyboard is in the view');
  await press('Escape');
  eq(pressed(), 'false', 'Escape lets go');
  assert(byTest('add') && byTest('plan-empty'), 'back to a new pocket');
  await click(byTest('row-pick'));
  eq(pressed(), 'true', 'the row takes it in hand as well');
  eq(await clickAt(NOTHING), null, 'beside the part there is nothing to place');
  eq(pressed(), 'false', 'a click on nothing lets go');
  await click(byTest('row-pick'));
  const fresh = await clickAt(FRONT);
  assert(fresh && Math.abs(fresh.args.point[1] - 90) < 1e-3, 'a click on a face places a new pocket there: ' + (fresh && fresh.args.point));
  eq([pressed(), text(byTest('staged-count')), fresh.args.others.length], ['false', '1', 1], 'the pocket that was in hand is let go, not moved');
`, { gl: true });

test('dragging a pocket slides it over the surface: the camera stays, one plan is out at a time, the release plans like a click', `
  await loaded3d();
  await click(q('#f-center'));
  const m = await place3d(TOP_A);
  eq(m.args.center, true, 'placed with Centre on the face');
  const before = cmds('pocket.plan').length;
  await dragTo(TOP_A, TOP_B);
  assert(stage().hasAttribute('data-drag'), 'the pocket is being dragged');
  eq(cmds('pocket.plan').length, before + 1, 'one plan is out, however many moves');
  const live = last('cmd', 'pocket.plan');
  assert(!('center' in live.args) && !q('#f-center').checked, 'centring is off for a pocket moved by hand');
  assert(live.args.point[0] > m.args.point[0] + 0.2 && Math.abs(live.args.point[2] - 20) < 1e-3, 'planned on the way, on the surface: ' + live.args.point);
  answered.add(live.id);
  await reply(live, planAt(live.args, {warnings: ['breaks_surface']}));
  assert(qa('[data-test=plan-warning]').map(text).join().includes('reaches outside the part'), 'a warning shows while dragging');
  await until(() => open('pocket.plan').length === 1, 'the newest spot is planned once the answer is in');
  eq(cmds('pocket.plan').length, before + 2, 'and only that one');
  const there = await answerPlans(() => TILTED);
  assert(text(byTest('plan-blocked')).includes('the face is tilted'), 'a spot that blocks the pocket says so while dragging');
  await sleep(300);
  eq(cmds('pocket.plan').length, before + 2, 'nothing more is asked while the pointer rests');
  await drop(TOP_B);
  assert(!stage().hasAttribute('data-drag'), 'released');
  await until(() => open('pocket.plan').length === 1, 'the release plans where the pocket lies');
  const final = open('pocket.plan')[0];
  eq(final.args, there.args, 'the same arguments as a click there, without center');
  assert(final.args.point[0] - m.args.point[0] > 2 && Math.abs(final.args.point[2] - 20) < 1e-3, 'well to the right, on the top face: ' + final.args.point);
  await answerPlans(() => TILTED);
  assert(text(byTest('plan-blocked')).includes('the face is tilted') && byTest('add').disabled, 'a new pocket dropped on a blocked spot stays there, flagged, as after a click');
  await press('Delete');
  assert(byTest('plan-empty'), 'Delete drops the pocket in hand');
  const again = await clickAt(TOP_A);
  assert(dist(again.args.point, m.args.point) < 1e-3, 'the camera did not turn under the drag: ' + again.args.point + ' vs ' + m.args.point);
`, { gl: true });

test('a pocket of the list dropped where it cannot be made goes back; a good drop updates its row, the pauses and Apply', `
  await loaded3d();
  const m = await place3d(TOP_A);
  await click(byTest('add'));
  await dragTo(TOP_A, TOP_B);
  eq(byTest('row-pick').getAttribute('aria-pressed'), 'true', 'dragging a pocket of the list takes it in hand');
  assert(!open('pocket.plan')[0].args.others, 'it is not checked against itself');
  await answerPlans(planAt);
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 19.00 mm']], 'the list waits for the release');
  await drop(TOP_B);
  await until(() => open('pocket.plan').length === 1, 'the release plans');
  await answerPlans(() => TILTED);
  assert(notes().includes('The pocket stays as it was: the face is tilted'), 'the refusal is said: ' + notes());
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 19.00 mm']], 'the pocket is where it was');
  assert(text(byTest('plan-pause')).includes('19') && byTest('row-pick').getAttribute('aria-pressed') === 'true', 'still in hand, as it was');
  await dragTo(TOP_A, TOP_B);
  await answerPlans(planAt);
  await drop(TOP_B);
  await until(() => open('pocket.plan').length === 1, 'the release plans');
  const final = open('pocket.plan')[0];
  await answerPlans(args => planAt(args, {pause_z: 12.4}));
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 12.40 mm']], 'the row follows the move');
  eq(qa('[data-test=pauses] li').map(text), ['Z 12.40 mm: insert 1 pc Ø6 × 3 mm disc'], 'and so do the pauses');
  assert(!notes().includes('stays as it was'), 'the refusal is gone: ' + notes());
  eq(text(byTest('staged-count')), '1', 'no pocket was added');
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  const written = last('cmd', 'project.apply').args.pockets;
  const { job, ...moved } = final.args;
  eq(written, [moved], 'Apply writes the pocket where it was dropped');
  assert(written[0].point[0] - m.args.point[0] > 2, 'which is not where it was placed: ' + written[0].point);
`, { gl: true });

test('arrow keys step the pocket in hand along its face, R turns it, Delete removes it; a held key never floods the plugin', `
  await loaded3d();
  const m = await place3d(TOP_A);
  eq(document.activeElement, stage(), 'a click puts the keyboard in the view');
  const where = text(byTest('plan-at'));
  await press('ArrowRight');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  let step = await answerPlans(planAt);
  assert(Math.abs(dist(step.args.point, m.args.point) - 0.5) < 1e-3 && step.args.point[0] > m.args.point[0], 'half a millimetre to the right: ' + step.args.point);
  assert(Math.abs(step.args.point[2] - 20) < 1e-3, 'along the face');
  assert(text(byTest('plan-at')) !== where, 'the position follows: ' + text(byTest('plan-at')));
  assert(byTest('plan-at-live').getAttribute('aria-live') === 'polite' && text(byTest('plan-at-live')).endsWith(text(byTest('plan-at'))), 'and is said in a live region, so a move is announced');
  const from = step.args.point;
  await press('ArrowUp', true);
  await until(() => open('pocket.plan').length === 1, 'the big step is planned');
  step = await answerPlans(planAt);
  assert(Math.abs(dist(step.args.point, from) - 5) < 1e-3, 'Shift: 5 mm: ' + step.args.point);
  const start = step.args.point, base = cmds('pocket.plan').length;
  await sleep(150);   // past the pause between two plans, so the first press is planned at once
  await press('ArrowRight'); await press('ArrowRight'); await press('ArrowRight');
  await sleep(300);
  eq(cmds('pocket.plan').length, base + 1, 'one plan is out while the key repeats');
  await answerPlans(planAt);
  await until(() => cmds('pocket.plan').length === base + 2, 'then the newest spot is planned');
  await answerPlans(planAt);
  step = last('cmd', 'pocket.plan');
  assert(Math.abs(dist(step.args.point, start) - 1.5) < 1e-3, 'three steps on: ' + step.args.point);
  await sleep(300);
  eq(cmds('pocket.plan').length, base + 2, 'and only once');
  for (let k = 0; k < 6 && !notes().includes('no face there'); k++) { await press('ArrowUp', true); await sleep(150); await answerPlans(planAt); }
  assert(notes().includes('There is no face there'), 'the face ends: ' + notes());
  const edge = cmds('pocket.plan').length;
  await press('ArrowUp', true);
  await sleep(300);
  eq(cmds('pocket.plan').length, edge, 'and nothing is planned past it');
  assert(notes().includes('There is no face there'), 'the line stays while the pocket is at the edge: ' + notes());
  await press('r');
  await until(() => open('pocket.plan').length === 1, 'the turn is planned');
  step = await answerPlans(planAt);
  eq(step.args.spin, 15, 'R: 15 degrees');
  assert(text(byTest('plan-at')).endsWith('turned 15°') && !notes().includes('no face there'), 'said with the position: ' + text(byTest('plan-at')));
  await press('r', true);
  await until(() => open('pocket.plan').length === 1, 'the turn back is planned');
  step = await answerPlans(planAt);
  assert(!('spin' in step.args), 'Shift+R turns it back');
  await click(byTest('add'));
  await click(byTest('row-pick'));
  stage().focus();
  await press('ArrowLeft');
  await until(() => open('pocket.plan').length === 1, 'a pocket of the list steps too');
  assert(!open('pocket.plan')[0].args.others, 'not checked against itself');
  await answerPlans(args => planAt(args, {pause_z: 12.4}));
  eq(rows('staged')[0][1], 'Cube · top · embedded · pause at Z 12.40 mm', 'its row follows');
  await press('Delete');
  assert(byTest('staged-empty') && text(byTest('staged-count')) === '0' && byTest('add'), 'Delete takes it off the list');
`, { gl: true });

test('a pocket of the list let go before its move is planned still moves; a move that cannot be made says so', `
  await loaded3d();
  await place3d(TOP_A);
  await click(byTest('add'));
  await dragTo(TOP_A, TOP_B);
  await answerPlans(planAt);
  await drop(TOP_B);
  await until(() => open('pocket.plan').length === 1, 'the release plans');
  await press('Escape');
  eq(byTest('row-pick').getAttribute('aria-pressed'), 'false', 'Escape let go of it before the answer came');
  await answerPlans(args => planAt(args, {pause_z: 12.4}));
  eq(rows('staged'), [['Ø6 × 3 mm disc', 'Cube · top · embedded · pause at Z 12.40 mm']], 'the row moved all the same');
  await click(byTest('row-pick'));
  stage().focus();
  await press('ArrowLeft');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  await click(byTest('done'));
  await answerPlans(args => planAt(args, {pause_z: 7.2}));
  eq(rows('staged')[0][1], 'Cube · top · embedded · pause at Z 7.20 mm', 'Done before the answer keeps the step');
  await click(byTest('row-pick'));
  stage().focus();
  await press('ArrowLeft');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  await press('Escape');
  await answerPlans(() => TILTED);
  eq(rows('staged')[0][1], 'Cube · top · embedded · pause at Z 7.20 mm', 'a step that cannot be made leaves the row');
  assert(toasts().map(toastText).join(' | ').includes('The pocket stays as it was: the face is tilted'), 'and says so: ' + toasts().map(toastText));
  eq(byTest('row-pick').getAttribute('aria-pressed'), 'false', 'without taking it back in hand');
`, { gl: true });

test('Add pocket waits for the plan of where the pocket is; the plan is announced when the drag ends', `
  await loaded3d();
  await place3d(TOP_A);
  assert(!byTest('add').disabled, 'planned: it can be added');
  await press('ArrowRight');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  assert(byTest('add').disabled, 'not while the step is planned');
  await answerPlans(planAt);
  assert(!byTest('add').disabled, 'then it can');
  await dragTo(TOP_A, TOP_B);
  eq([q('#em-plan-state'), byTest('plan-at-live')].map(e => e.getAttribute('aria-live')), ['off', 'off'], 'the plan is not read out on every move of a drag');
  await answerPlans(planAt);
  assert(byTest('add').disabled, 'nor while dragging');
  await drop(TOP_B);
  await until(() => open('pocket.plan').length === 1, 'the release plans');
  eq(q('#em-plan-state').getAttribute('aria-live'), 'polite', 'the plan of the drop is read out');
  assert(byTest('add').disabled, 'nor before the release is planned');
  const final = await answerPlans(planAt);
  await click(byTest('add'));
  await click(byTest('apply'));
  await until(() => last('cmd', 'project.apply'), 'apply sent');
  eq(last('cmd', 'project.apply').args.pockets.map(p => p.point), [final.args.point], 'the pocket added is the one dropped');
`, { gl: true });

test('with Centre on the face the pocket is shown, and the arrows step it, from the middle of the face', `
  await loaded3d();
  await click(q('#f-center'));
  const MID = [100, 100, 20];
  const m = await clickAt(TOP_B);
  assert(m && m.args.center && dist(m.args.point, MID) > 2, 'clicked well off the middle: ' + (m && m.args.point));
  await answerPlans(args => args.center ? planAt({...args, point: MID}, {point: MID}) : planAt(args, {point: args.point}));
  assert(/^X 100(\\.0)? · Y 100(\\.0)? · Z 20(\\.0)? mm$/.test(text(byTest('plan-at'))), 'the position is where the pocket was planned: ' + text(byTest('plan-at')));
  await press('ArrowRight');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  const step = open('pocket.plan')[0];
  assert(Math.abs(dist(step.args.point, MID) - 0.5) < 1e-3 && step.args.point[0] > MID[0], 'half a millimetre right of the middle: ' + step.args.point);
  assert(!('center' in step.args), 'no longer centred');
`, { gl: true });

test('in one column a scroll made while the view has the focus is not undone when the plan above grows', `
  await loaded3d();
  const top = () => canvas().getBoundingClientRect().top;
  const m = await clickAt(FRONT);
  assert(m && document.activeElement === stage(), 'the view has the focus and a plan is out');
  const y = scrollY;
  window.scrollBy(0, -80);
  await settle();
  assert(scrollY < y - 40, 'scrolled: ' + y + ' to ' + scrollY);
  const after = top();
  await answerPlans(planAt);
  await until(() => !document.getAnimations().some(a => a.playState === 'running'), 'animations over');
  await frame(); await frame();
  assert(Math.abs(top() - after) <= 2, 'the view stays where the user scrolled it: ' + after + ' to ' + top());
`, { gl: true, width: 480 });

test('a click beside the pocket of the list in hand starts a new pocket without the shape of that pocket', `
  await loaded3d();
  await place3d(TOP_A);
  await click(byTest('add'));
  await click(byTest('row-pick'));
  assert(await clickAt(FRONT), 'a new pocket is planned');
  const p = spot(FRONT);
  await pointer('mouseMoved', p.x + 1, p.y);
  await settle();
  assert(!stage().hasAttribute('data-over'), 'nothing to grab there before the new pocket is planned');
  await answerPlans(planAt);
  await pointer('mouseMoved', p.x, p.y);
  await settle();
  assert(stage().hasAttribute('data-over'), 'then its own shape is');
`, { gl: true });

test('a click on the pocket of the list in hand keeps it in hand; on a new pocket it places that pocket again', `
  await loaded3d();
  const m = await place3d(TOP_A);
  await click(byTest('add'));
  await click(byTest('row-pick'));
  eq(await clickAt(TOP_A), null, 'nothing is planned');
  eq([byTest('row-pick').getAttribute('aria-pressed'), text(byTest('staged-count'))], ['true', '1'], 'it stays in hand, and no pocket is added');
  assert(byTest('done'), 'Done is still offered');
  await click(byTest('done'));
  const fresh = await place3d(FRONT);
  const again = await clickAt(FRONT);
  assert(again && dist(again.args.point, fresh.args.point) < 1e-2, 'a new pocket is placed again where its own shape is clicked: ' + (again && again.args.point));
`, { gl: true });

test('a pocket of the list let go twice before the answers come takes the newest move, though the older answer comes first', `
  await loaded3d();
  await place3d(TOP_A);
  await click(byTest('add'));
  await dragTo(TOP_A, TOP_B);
  await answerPlans(planAt);
  await drop(TOP_B);
  await until(() => open('pocket.plan').length === 1, 'the release plans');
  await press('Escape');
  await until(() => open('pocket.plan').length === 2, 'letting go plans the drop for the row');
  const first = last('cmd', 'pocket.plan');
  await click(byTest('row-pick'));
  stage().focus();
  await press('ArrowLeft');
  await until(() => open('pocket.plan').length === 3, 'the step is planned');
  await press('Escape');
  await until(() => open('pocket.plan').length === 4, 'letting go plans the step for the row');
  const second = last('cmd', 'pocket.plan');
  assert(first.id !== second.id && dist(first.args.point, second.args.point) > 1, 'two moves: ' + first.args.point + ' / ' + second.args.point);
  answered.add(first.id);
  await reply(first, planAt(first.args, {pause_z: 12.4}));
  answered.add(second.id);
  await reply(second, planAt(second.args, {pause_z: 7.2}));
  await answerPlans(planAt);
  eq(rows('staged')[0][1], 'Cube · top · embedded · pause at Z 7.20 mm', 'the newest move stands');
`, { gl: true });

test('a move planned for its row after letting go says nothing when it fails after the project was loaded again', `
  await loaded3d();
  await place3d(TOP_A);
  await click(byTest('add'));
  await click(byTest('row-pick'));
  stage().focus();
  await press('ArrowLeft');
  await until(() => open('pocket.plan').length === 1, 'the step is planned');
  await press('Escape');
  await until(() => open('pocket.plan').length === 2, 'letting go plans the step for the row');
  const kept = last('cmd', 'pocket.plan');
  await click(byTest('reload'));
  await until(() => cmds('project.load').length === 2, 'loaded again');
  await reply(last('cmd', 'project.load'), PROJECT);
  answered.add(kept.id);
  await fail(kept, {code: 'stale_job', detail: 'the project was loaded again; load it once more'});
  assert(!text(document.body).includes('Placing the pocket failed'), 'no error for a project that is gone: ' + alerts());
`, { gl: true });

test('the 3D view says how to move a pocket in Portuguese too, and the hint stays inside a narrow view', `
  await loaded3d();
  eq(stage().getAttribute('aria-label'), 'Visualização 3D', 'the widget is named');
  assert(text(q('#em-view-keys')).includes('as setas o movem 0,5 mm'), 'keys: ' + text(q('#em-view-keys')));
  const hint = q('.em-hint'), box = q('.em-stage').getBoundingClientRect(), r = hint.getBoundingClientRect();
  assert(text(hint).includes('arraste um bolso para movê-lo'), 'hint: ' + text(hint));
  assert(r.left >= box.left && r.right <= box.right && r.bottom <= box.bottom && r.top > box.top + box.height / 2, 'the hint sits at the foot of the view');
  const inset = (() => { const p = document.createElement('i'); p.style.background = 'var(--oui-inset)'; document.body.append(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; })();
  eq(getComputedStyle(q('.em-stage')).backgroundColor, inset, 'the stage behind the 3D view is the neutral inset grey, not a tint');
  await place3d([0, 0]);
  await click(byTest('add'));
  eq(text(byTest('staged-help')), 'Selecione um bolso para alterá-lo. Arraste-o na visualização 3D para movê-lo.', 'the list says how');
  for (const b of qa('button').filter(b => b.getClientRects().length && text(b))) assert(b.scrollWidth <= b.clientWidth + 1, 'label fits its button: ' + text(b));
  eq(document.documentElement.scrollWidth, document.documentElement.clientWidth, 'nothing wider than the window');
`, { gl: true, width: 480, lang: 'pt_BR' });

test('in one column the view stays put under the pointer while the plan above it grows and shrinks', `
  await loaded3d();
  const top = () => Math.round(canvas().getBoundingClientRect().top);
  const plan = () => Math.round(byTest('plan').getBoundingClientRect().height);
  // The messages of the plan animate their height, and the view is put back each time a frame is drawn. A layout forced
  // between two frames sees more of the animation than was drawn, so measure once nothing moves. Scrolling snaps to
  // whole pixels, hence the 2 px.
  const still = async (was, what) => {
    await until(() => !document.getAnimations().some(a => a.playState === 'running'), 'animations over');
    await frame(); await frame();
    assert(Math.abs(top() - was) <= 2, what + ': ' + was + ' to ' + top());
  };
  assert(q('.em-form').getBoundingClientRect().bottom <= q('.em-stage-panel').getBoundingClientRect().top, 'the form is above the view');
  const at = top(), empty = plan();
  await place3d(FRONT);
  assert(plan() > empty + 50, 'the plan above the view grew: ' + empty + ' to ' + plan());
  await still(at, 'and the view did not move under the pointer');
  await click(byTest('add'));
  canvas().scrollIntoView({ block: 'center' });
  await settle();
  const held = top(), short = plan();
  await dragTo(FRONT, [0.05, 0.02]);
  assert(byTest('row-pick').getAttribute('aria-pressed') === 'true' && plan() > short + 50, 'the drag took the pocket in hand, and its plan is shown above');
  await still(held, 'the view stays where the drag began');
  await answerPlans(() => TILTED);
  assert(byTest('plan-blocked') && plan() < short + 50, 'a blocked spot makes the plan short again');
  await still(held, 'and the pocket does not slip from under the pointer');
  // Every frame as it is drawn: an observer made after the page's own runs after it, once the view was put back.
  const drawn = [];
  const frames = new ResizeObserver(() => drawn.push(top()));
  frames.observe(document.body);
  await drop([0.05, 0.02]);
  await answerPlans(() => TILTED);
  assert(notes().includes('The pocket stays as it was'), 'dropped there, the pocket goes back and the plan says so: ' + notes());
  await still(held, 'and the view is still in its place');
  frames.disconnect();
  assert(drawn.length > 1 && drawn.every(t => Math.abs(t - held) <= 2), 'in every frame drawn while the note unfolded: ' + drawn);
`, { gl: true, width: 480 });

// ------------------------------------------------------------------ runner
const workers = Number(process.env.WORKERS ?? 4);
if (!Number.isSafeInteger(workers) || workers < 1) throw new Error('WORKERS must be a positive integer');
const filter = process.argv[2];
const chosen = scenarios.filter(s => !filter || s.name.includes(filter));
const page = await builtPage();
const dir = await mkdtemp(join(tmpdir(), 'embedder-page-'));
const browser = await launch();
const glBrowser = chosen.some(s => s.gl) ? await launch({ gpu: true }) : null;
let failed = 0;
const results = [];
try {
  await Promise.all(Array.from({ length: Math.min(workers, chosen.length) }, async (_, worker) => {
    for (let k = worker; k < chosen.length; k += workers) {
      const sc = chosen[k];
      const boot = { version: 'test', lang: sc.lang ?? 'en', pref: sc.pref ?? 'auto' };
      const file = join(dir, `p${k}.html`);
      await writeFile(file, preparePage(page, boot));
      const p = await (sc.gl ? glBrowser : browser).newPage();
      const started = Date.now();
      try {
        await p.size(sc.width ?? 1280, 900);
        await p.init(MOCK_HOST + (sc.gl ? '' : NO_WEBGL) + 'try { localStorage.clear(); } catch {}');
        if (sc.intl) await p.call('Emulation.setLocaleOverride', { locale: sc.intl });   // the system's own language
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
  await glBrowser?.close();
  await rm(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
if (process.env.RESULTS) await writeFile(process.env.RESULTS, JSON.stringify(results, null, 2));
console.log(`${chosen.length - failed}/${chosen.length} page scenarios passed`);
if (failed || !chosen.length) process.exit(1);
console.log('PASS');
