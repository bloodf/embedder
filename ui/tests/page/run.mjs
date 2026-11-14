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
async function ready() {
  await until(() => last('cmd', 'hello'), 'hello sent');
  await reply(last('cmd', 'hello'), {version: '0.1.0', settings: SETTINGS});
}
async function tab(name) { await click(q('[data-tab="' + name + '"]')); }
const alerts = () => qa('[role=alert] .p-message').map(text).join(' | ');
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
  await tab('settings'); assert(byTest('settings-empty'), 'settings panel');
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
        await p.init(MOCK_HOST + 'try { localStorage.clear(); } catch {}');
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
