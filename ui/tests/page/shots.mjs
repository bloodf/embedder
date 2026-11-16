// Real renders of the built Embedder page for the brand images: the built page (src/embedder/ui/app.html) in
// headless Chrome with software WebGL, talking to the real plugin (shots_host.py: plugin.py under the fake `orca`
// module, on a project built in code). Nothing on a screenshot is drawn by hand; scripts/marketing.py then places
// them in the empty panels of the marketing art, and scripts/frames.py in the 16:10 frames of the brand kit's PNGs.
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
// The brand kit's frames are 16:10 and so are their renders, at 2x so they are sharp after scaling down. The window
// is as large as the state needs for the whole page to fit without scrolling (the three columns are as tall as the
// window or their content); the small install cards get a small window, so their text stays readable at that size.
const STORE = [1440, 900], CARD = [640, 400], SCALE = 2;
const LANGS = ['en', 'pt-BR'];
// The art's panels are 682 x 658 px in a 1600 x 900 export: PANEL is the narrowest window of that shape that still has
// the form beside the 3D view. The square and social images have a smaller panel, so they get the one-column page.
const PANEL = [912, 880], SMALL = [480, 480], RESULT = [960, 600];
const LABELS = {
  en: { disc: 'Ø10 × 3 mm disc', sticker: 'Ø25 mm sticker', badge: 'Badge' },
  'pt-BR': { disc: 'Disco Ø10 × 3 mm', sticker: 'Adesivo Ø25 mm', badge: 'Crachá' },
};
const THEMES = { dark: '#151515', light: '#f4f4f4' };   // the host colour the page follows (--orca-bg)

const page = process.env.PAGE ? await readFile(process.env.PAGE, 'utf8')
  : execFileSync('python3', ['-c', 'import sys; sys.path.insert(0, "scripts"); import build; sys.stdout.write(build.page_html("app.html"))'],
    { cwd: repo, encoding: 'utf8', maxBuffer: 64 << 20 });

/** One fresh page wired to one fresh plugin process; `run(steps)` evaluates scenario code with the test helpers. */
async function session(browser, dir, theme, [W, H], lang) {
  const file = join(dir, `shot-${theme}-${Date.now()}.html`);
  await writeFile(file, preparePage(page, { version: 'shots', lang: lang ?? 'en', pref: lang ?? 'en' }));
  const host = spawn('python3', [join(here, 'shots_host.py'), lang ?? 'en'], { cwd: repo, stdio: ['pipe', 'pipe', 'inherit'] });
  const p = await browser.newPage();
  await p.size(W, H, SCALE);
  if (lang) await p.call('Emulation.setScrollbarsHidden', { hidden: true });   // the marketing renders: a classic scrollbar is the host's, not the page's
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
    const MESHED = () => text(byTest('viewer')).includes(' mm');   // the view's header shows the object's size once its meshes are in
    await until(() => document.querySelector('#app > *'), 'app mounted');
    ${steps}
    await settle(); })()`);
  /** A real mouse click on the 3D view, `dx`/`dy` pixels from its centre. */
  const clickView = async (dx = 0, dy = 0) => {
    const r = await p.evaluate(`(() => { const c = document.querySelector('[data-test=viewer] canvas'); c.scrollIntoView({ block: 'center' });
      const b = c.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
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
  await until(() => byTest('viewer') && MESHED(), 'meshes in the view', 30000);
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
  // For scripts/frames.py: the brand kit's social formats and install cards.
  { name: 'placement', themes: ['dark'], async go(s) {
    await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED);
  } },
  { name: 'pause', themes: ['dark'], async go(s) {
    await s.run(LOADED);
    await s.clickView(-60, 0); await s.run(PLANNED + ADD);
    await s.clickView(60, 0); await s.run(PLANNED + ADD);
  } },
  { name: 'load', themes: ['light'], size: CARD, async go(s) { await s.run(LOADED); } },
  { name: 'place', themes: ['light'], size: CARD, async go(s) { await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED + SCROLL('plan')); } },
  { name: 'applied', themes: ['light'], size: CARD, async go(s) {
    await s.run(LOADED); await s.clickView(-60, 0); await s.run(PLANNED + ADD); await s.clickView(60, 0); await s.run(PLANNED + ADD);
    await s.run(`await click(byTest('apply')); await until(() => byTest('result'), 'applied', 30000); window.scrollTo(0, 0); await sleep(300);`);
  } },
  // For scripts/marketing.py, in both languages: the near-square panels of the marketing art, and the README's own screenshots.
  { name: 'panel-main', themes: ['dark', 'light'], langs: LANGS, size: PANEL, async go(s) {
    await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED);
  } },
  { name: 'panel-placement', themes: ['dark'], langs: LANGS, size: PANEL, async go(s) {
    await s.run(LOADED); await s.clickView(-70, -15); await s.run(PLANNED + ADD); await s.clickView(95, 20); await s.run(PLANNED);
  } },
  { name: 'panel-magnets', themes: ['dark'], langs: LANGS, size: PANEL, async go(s, lang) {
    await s.run(LOADED + choose('preset', LABELS[lang].disc) + CENTRE); await s.clickView(); await s.run(PLANNED + `await click(q('[data-test=preset]')); await sleep(400);`);
  } },
  { name: 'panel-nfc', themes: ['dark'], langs: LANGS, size: PANEL, async go(s, lang) {
    await s.run(LOADED + choose('object', LABELS[lang].badge) + `await until(() => MESHED(), 'badge mesh', 30000); await sleep(400);`
      + choose('preset', LABELS[lang].sticker) + CENTRE);
    await s.clickView(); await s.run(PLANNED);
  } },
  { name: 'panel-pause', themes: ['dark'], langs: LANGS, size: PANEL, async go(s) {
    await s.run(LOADED); await s.clickView(-60, 0); await s.run(PLANNED + ADD); await s.clickView(60, 0); await s.run(PLANNED + ADD + SCROLL('staged-count'));
  } },
  { name: 'small-main', themes: ['dark'], langs: LANGS, size: SMALL, async go(s) {
    await s.run(LOADED + CENTRE); await s.clickView(); await s.run(PLANNED + SCROLL('viewer'));
  } },
  { name: 'screen-pockets', themes: ['dark', 'light'], langs: LANGS, async go(s) {
    await s.run(LOADED); await s.clickView(-60, 0); await s.run(PLANNED + ADD); await s.clickView(60, 0); await s.run(PLANNED + ADD);
  } },
  { name: 'screen-applied', themes: ['dark', 'light'], langs: LANGS, size: RESULT, async go(s) {
    await s.run(LOADED); await s.clickView(-60, 0); await s.run(PLANNED + ADD); await s.clickView(60, 0); await s.run(PLANNED + ADD);
    await s.run(`await click(byTest('apply')); await until(() => byTest('result'), 'applied', 30000); window.scrollTo(0, 0); await sleep(300);`);
  } },
];

await mkdir(out, { recursive: true });
const dir = await mkdtemp(join(tmpdir(), 'embedder-shots-'));
const browser = await launch({ gpu: true });
let failed = 0;
try {
  for (const shot of SHOTS.filter(s => !process.env.ONLY || s.name === process.env.ONLY)) {
    for (const [theme, lang] of shot.themes.flatMap(theme => (shot.langs ?? [null]).map(lang => [theme, lang]))) {
      const file = [shot.name, theme, lang].filter(Boolean).join('-');
      const s = await session(browser, dir, theme, shot.size ?? STORE, lang);
      try {
        await shot.go(s, lang);
        const probe = await s.p.evaluate('JSON.stringify({ v: __t.violations, r: __t.rejections, e: __t.errors })');
        if (probe !== '{"v":[],"r":[],"e":[]}') throw new Error('page problems: ' + probe);
        await writeFile(join(out, `${file}.png`), await s.p.screenshot());
        console.log(`ok   ${file}`);
      } catch (e) {
        failed++;
        console.log(`FAIL ${file}: ${String(e.message || e).split('\n')[0]}`);
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
