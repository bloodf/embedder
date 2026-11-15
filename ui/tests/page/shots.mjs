// Real renders of the built Embedder page for the brand images: the built page (src/embedder/ui/app.html) in
// headless Chrome with software WebGL, talking to the real plugin (shots_host.py: plugin.py under the fake `orca`
// module, on a project built in code). Nothing on a screenshot is drawn by hand; scripts/frames.py then places
// them in the empty 16:10 frames of the brand PNGs.
//   node ui/tests/page/shots.mjs [out-dir]        default out-dir: dist/shots
import { spawn, execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { launch, MOCK_HOST, HELPERS, preparePage } from './cdp.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../../..');
const out = resolve(process.argv[2] ?? join(repo, 'dist', 'shots'));
const W = 1280, H = 800, SCALE = 2;   // 16:10, rendered at 2x so the frames are sharp after scaling down
const THEMES = { dark: '#151515', light: '#f4f4f4' };   // the host colour the page follows (--orca-bg)

const page = process.env.PAGE ? await readFile(process.env.PAGE, 'utf8')
  : execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import build; sys.stdout.write(build.page_html("app.html"))'],
    { cwd: repo, encoding: 'utf8', maxBuffer: 64 << 20 });

/** One fresh page wired to one fresh plugin process; `run(steps)` evaluates scenario code with the test helpers. */
async function session(browser, dir, theme) {
  const file = join(dir, `shot-${theme}-${Date.now()}.html`);
  await writeFile(file, preparePage(page, { version: 'shots', lang: 'en', pref: 'en' }));
  const host = spawn('python3', [join(here, 'shots_host.py')], { cwd: repo, stdio: ['pipe', 'pipe', 'inherit'] });
  const p = await browser.newPage();
  await p.size(W, H, SCALE);
  await p.init(MOCK_HOST);
  await p.goto(pathToFileURL(file).href);
  await p.evaluate(`(async () => { const root = document.documentElement; root.style.setProperty('--orca-bg', '${THEMES[theme]}');
    const end = Date.now() + 15000; while (root.classList.contains('orca-dark') !== ${theme === 'dark'} && Date.now() < end) await new Promise(r => setTimeout(r, 50)); })()`);
  // the bridge: page -> plugin by polling what the page posted, plugin -> page through the page's handler
  let forwarded = 0, open = true;
  createInterface({ input: host.stdout }).on('line', line => {
    if (open) p.evaluate(`window.__t.handler && window.__t.handler(${line}), 0`).catch(() => {});
  });
  const pump = (async () => {
    while (open) {
      const fresh = await p.evaluate(`JSON.stringify(window.__t.sent.slice(${forwarded}))`).catch(() => '[]');
      for (const m of JSON.parse(fresh)) host.stdin.write(JSON.stringify(m) + '\n');
      forwarded += JSON.parse(fresh).length;
      await new Promise(r => setTimeout(r, 25));
    }
  })();
  const run = steps => p.evaluate(`(async () => { ${HELPERS}
    await until(() => document.querySelector('#app > *'), 'app mounted');
    ${steps}
    await settle(); })()`);
  /** A real mouse click on the 3D view, `dx`/`dy` pixels from its centre. */
  const clickView = async (dx = 0, dy = 0) => {
    const r = await p.evaluate(`(() => { const b = document.querySelector('[data-test=viewer] canvas').getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
    const at = { x: r.x + dx, y: r.y + dy, button: 'left', clickCount: 1 };
    await p.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: at.x, y: at.y });
    await p.call('Input.dispatchMouseEvent', { type: 'mousePressed', ...at });
    await p.call('Input.dispatchMouseEvent', { type: 'mouseReleased', ...at });
  };
  const close = async () => { open = false; await pump; host.stdin.end(); await p.close(); if (host.exitCode === null && host.signalCode === null) await new Promise(r => host.once('exit', r)); };
  return { p, run, clickView, close };
}

// Scenario pieces, in the page's own terms (data-test hooks and the visible option labels).
const LOADED = `
  await until(() => last('cmd', 'hello') && byTest('load'), 'ready');
  await click(byTest('load'));
  await until(() => byTest('viewer') && !text(byTest('viewer')).includes('Loading'), 'meshes in the view', 30000);
  await sleep(400);`;
const choose = (test, label) => `
  await click(q('[data-test=${test}]'));
  await until(() => qa('[role=option]').some(o => text(o) === ${JSON.stringify(label)}), 'option ${label}');
  await click(qa('[role=option]').find(o => text(o) === ${JSON.stringify(label)}));`;
const PLANNED = `await until(() => byTest('plan-label') || byTest('plan-blocked'), 'plan', 30000); await sleep(400);`;
const ADD = `await click(byTest('add')); await sleep(300);`;
const CENTRE = `await click(q('#f-center'));`;
/** Scroll the page so `test` sits near the top; the 3D view is sticky and stays in sight. */
const SCROLL = test => `window.scrollTo(0, byTest('${test}').getBoundingClientRect().top + window.scrollY - 90); await sleep(300);`;

const SHOTS = [
  { name: 'placement', themes: ['dark', 'light'], async go(s) {
    await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED);
  } },
  { name: 'magnets', themes: ['dark'], async go(s) {
    await s.run(LOADED + choose('preset', 'Ø10 × 3 mm disc') + CENTRE); await s.clickView(); await s.run(PLANNED + `await click(q('[data-test=preset]')); await sleep(400);`);
  } },
  { name: 'nfc', themes: ['dark'], async go(s) {
    await s.run(LOADED + choose('object', 'Badge') + `await until(() => !text(byTest('viewer')).includes('Loading'), 'badge mesh', 30000); await sleep(400);`
      + choose('preset', 'Ø25 mm sticker') + CENTRE);
    await s.clickView(); await s.run(PLANNED + SCROLL('plan'));
  } },
  { name: 'pause', themes: ['dark'], async go(s) {
    await s.run(LOADED);
    await s.clickView(-60, 0); await s.run(PLANNED + ADD);
    await s.clickView(60, 0); await s.run(PLANNED + ADD);
    await s.run(SCROLL('staged'));
  } },
  { name: 'custom', themes: ['dark'], async go(s) {
    await s.run(LOADED + `await click(q('#f-custom'));
      await type(q('#f-d'), '12'); q('#f-d').blur(); await type(q('#f-t'), '4'); q('#f-t').blur(); await settle();` + CENTRE);
    await s.clickView(); await s.run(PLANNED);
  } },
  { name: 'load', themes: ['light'], async go(s) { await s.run(LOADED); } },
  { name: 'place', themes: ['light'], async go(s) { await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED + SCROLL('plan')); } },
  { name: 'applied', themes: ['light'], async go(s) {
    await s.run(LOADED); await s.clickView(-60, 0); await s.run(PLANNED + ADD); await s.clickView(60, 0); await s.run(PLANNED + ADD);
    await s.run(`await click(byTest('apply')); await until(() => byTest('result'), 'applied', 30000);`);
  } },
];

await mkdir(out, { recursive: true });
const dir = await mkdtemp(join(tmpdir(), 'embedder-shots-'));
const browser = await launch({ gpu: true });
let failed = 0;
try {
  for (const shot of SHOTS.filter(s => !process.env.ONLY || s.name === process.env.ONLY)) {
    for (const theme of shot.themes) {
      const s = await session(browser, dir, theme);
      try {
        await shot.go(s);
        const probe = await s.p.evaluate('JSON.stringify({ v: __t.violations, r: __t.rejections, e: __t.errors })');
        if (probe !== '{"v":[],"r":[],"e":[]}') throw new Error('page problems: ' + probe);
        await writeFile(join(out, `${shot.name}-${theme}.png`), await s.p.screenshot());
        console.log(`ok   ${shot.name}-${theme}`);
      } catch (e) {
        failed++;
        console.log(`FAIL ${shot.name}-${theme}: ${String(e.message || e).split('\n')[0]}`);
      } finally {
        await s.close();
      }
    }
  }
} finally {
  await browser.close();
  await rm(dir, { recursive: true, force: true });
}
console.log(`screenshots in ${out}`);
if (failed) process.exit(1);
