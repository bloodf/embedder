import { reactive } from 'vue';
import * as bridge from '../core/bridge';
import { Tracker, message, type Notice } from '../core/tracker';
import { showToast, type OuiToastTone } from '@orca-plugins/ui-foundation/src/components/toast';
import { copyText } from '@orca-plugins/ui-foundation/src/components/clipboard';
import { t, tMaybe, fmt, onLangPref } from '../core/i18n';
import { en } from '../core/messages';
import { probeWebGL } from '../core/three-probe';
import type { Hit } from '../core/pick';
import { rememberedShape, splitLead, type InsertChoice } from './logic';
import type { ApplyResult, Hello, Mode, Plan, PlanArgs, PocketShape, Polarity, Preset, Project, Settings, Staged } from './types';

export const DEFAULT_PRESET = 'magnet-disc-6x3';

export const s = reactive({
  tab: 'embed',
  version: '',
  settings: null as Settings | null,
  error: '',
  errorDetail: '',   // the technical text behind `error`, shown only on request
  // Each failed hello is a new notice (the same text again included). Never below the clock, so a reload of the tab
  // (the closed notices are kept for the session) does not count from 1 again onto a closed one.
  helloFails: 0,
  webgl: null as boolean | null,
  builtin: [] as Preset[],
  user: [] as Preset[],
  // project and the selected object's meshes (the meshes themselves live outside Vue, see project.ts)
  project: null as Project | null,
  loading: null as { done: number; total: number } | null,
  object: null as number | null,
  mesh: { state: 'idle' as 'idle' | 'loading' | 'ready' | 'error', done: 0, total: 0, version: 0 },
  // placement form
  insert: { preset: null, custom: null } as InsertChoice,
  mode: 'embedded' as Mode,
  spin: null as number | null,
  cover: null as number | null,
  center: false,
  pocketShape: null as PocketShape | null,   // null: the insert's own (defaultPocketShape)
  polarity: null as Polarity | null,
  // the pocket in hand (where it is, its plan), the staged pockets and the applied copy. `selected`: the staged pocket
  // that is in hand (its key), or null while a new one is being placed. `dragging`: the pointer is sliding it.
  hit: null as Hit | null,
  plan: null as Plan | null,
  planArgs: null as PlanArgs | null,
  selected: null as number | null,
  dragging: false,
  planning: false,   // a plan of the pocket in hand is out
  note: '',   // one passing line about the pocket in hand: the face ends there, the pocket went back

  staged: [] as Staged[],
  remove: [] as string[],
  result: null as ApplyResult | null,
  applies: 0,   // each apply is a new result notice, a copy at the same path included (never below the clock, as above)
  opened: '' as '' | 'asked' | 'none',
});

// Codes whose detail is a name the user knows (a file of the project, a preset, an object): said after the sentence.
const NAME_DETAIL = new Set(['missing_model_file', 'unknown_preset', 'cut_object', 'unsupported_object']);
// Codes whose detail is the machine's own text (a Python exception, OrcaSlicer's error, a storage path): never in the
// sentence, kept as the error's technical details.
const TECH_DETAIL = new Set(['internal', 'unknown_command', 'export_failed', 'open_failed', 'bad_xml', 'bad_package', 'not_found',
  'exists', 'path_too_long']);

/** A plugin error in words: the translated code (err.<code>), with the name it is about when the detail is one. */
export function errorText(e: unknown): string {
  if (e instanceof bridge.ReplyError) {
    const key = `err.${e.code}`;
    const blocked = e.code === 'pocket_blocked' && /^pocket (\d+): (\w+)$/.exec(e.detail);   // "pocket 2: no_floor"
    if (blocked) return `${t('err.pocket_blocked')} (${t('err.pocketN', { n: blocked[1] })}: ${tMaybe(`block.${blocked[2]}`, blocked[2])})`;
    if (key in en) return t(key as keyof typeof en) + (e.detail && NAME_DETAIL.has(e.code) ? ` (${e.detail})` : '');
    return t('err.internal');
  }
  return e instanceof PluginError ? e.message : t('err.internal');
}

/** What the machine said, for the "technical details" of an error: "internal: KeyError: 'printable_area'". Empty when
 *  the sentence already says everything. Also written to the console, where a bug report can pick it up. */
export function errorDetail(e: unknown): string {
  let detail = '';
  if (e instanceof bridge.ReplyError) {
    const known = `err.${e.code}` in en;
    if (!known || TECH_DETAIL.has(e.code)) detail = e.detail ? `${e.code}: ${e.detail}` : known ? '' : e.code;
    else if (e.detail && !NAME_DETAIL.has(e.code)) console.warn(`embedder: ${e.code}: ${e.detail}`);
  } else if (e instanceof PluginError) {
    detail = e.detail ?? '';
  } else {
    detail = message(e);
  }
  if (detail) console.warn(`embedder: ${detail}`);
  return detail;
}

/** An error as the page says it: the sentence as its message, the technical text beside it. */
export class PluginError extends Error {
  constructor(message: string, readonly detail?: string) { super(message); }
}
export const pluginError = (e: unknown): PluginError => new PluginError(errorText(e), errorDetail(e) || undefined);

// The tracker's notices are the page's toasts: the first sentence is the title. An unknown outcome is a warning
// that stays until closed, like an error: the user has to know the command may or may not have happened. Those two
// carry the time they were said, since they may be read long after.
const TONE: Record<Notice['kind'], OuiToastTone> = { error: 'error', unknown: 'warn', success: 'success', info: 'info' };
export function toast(n: Notice): void {
  const [title, rest] = splitLead(n.text);
  const lasting = n.kind === 'error' || n.kind === 'unknown';
  const body = [rest, lasting ? fmt.time(Date.now() / 1000) : ''].filter(Boolean).join(' · ');
  // An error with technical text behind it offers that text to copy (for a bug report); it is never in the sentence.
  const detail = n.detail;
  const action = detail ? { label: t('err.copyDetails'), run: () => { void copyToClipboard(detail); } } : undefined;
  showToast({ tone: TONE[n.kind], title, body: body || undefined, key: n.key && 'cmd:' + n.key, timeout: n.kind === 'unknown' ? 0 : undefined, action });
}

export async function copyToClipboard(text: string): Promise<void> {
  showToast((await copyText(text)) ? { tone: 'success', title: t('common.copied') } : { tone: 'warn', title: t('common.notCopied'), body: text, timeout: 0 });
}

export const tracker = new Tracker(
  (cmd, args) => bridge.command(cmd, args).catch(e => { throw pluginError(e); }),
  (key, params) => t(key, params), toast);
bridge.setErrorSink(e => tracker.notify('error', t('msg.plugin'), undefined, errorDetail(e)));

/** A step that failed outside the tracker (a mesh pull, a plan): said as its commands are. */
export function notifyFailed(action: string, e: unknown): void {
  tracker.notify('error', t('msg.failed', { action, error: errorText(e) }), undefined, errorDetail(e));
}

export async function hello(): Promise<void> {
  try {
    const r: Hello = await bridge.command('hello');
    s.version = r.version;
    s.settings = r.settings;
    s.error = s.errorDetail = '';
    // A preset chosen before the settings came (presets listed after a failed hello): its kept shape now applies.
    if (s.pocketShape == null && !s.insert.custom && s.selected == null) s.pocketShape = rememberedShape(r.settings.pocket_shapes, s.insert.preset);
  } catch (e) {
    s.error = errorText(e);
    s.errorDetail = errorDetail(e);
    s.helloFails = Math.max(s.helloFails + 1, Date.now());
  }
}

export async function loadPresets(): Promise<void> {
  const r = await tracker.run<{ builtin: Preset[]; user: Preset[] }>({ key: 'presets', label: t('act.presets'), cmd: 'presets.list', background: true });
  if (!r.ok) return;
  s.builtin = r.result.builtin;
  s.user = r.result.user;
  if (!s.insert.preset && !s.insert.custom) {
    const pick = s.builtin.find(p => p.id === DEFAULT_PRESET) ?? s.builtin[0];
    choosePreset(pick?.id ?? null);
  }
}

/** Settings are saved as they change: no toast for it, and a failure is said by the Settings page's own status line. */
export async function saveSettings(values: Partial<Settings>): Promise<boolean> {
  const r = await tracker.run<Settings>({ key: 'settings', label: t('act.settings'), cmd: 'settings.save', args: { settings: values }, quiet: true, background: true });
  if (r.ok) s.settings = r.result;
  return r.ok;
}

export async function savePreset(preset: Record<string, unknown>): Promise<string | null> {
  const r = await tracker.run<{ id: string; user: Preset[] }>({ key: 'preset-save', label: t('act.presetSave'), cmd: 'presets.save', args: { preset }, okText: t('preset.saved') });
  if (!r.ok) return null;
  s.user = r.result.user;
  return r.result.id;
}

export async function deletePreset(id: string): Promise<void> {
  const r = await tracker.run<{ user: Preset[] }>({ key: 'preset-del-' + id, label: t('act.presetDelete'), cmd: 'presets.delete', args: { id } });
  if (!r.ok) return;
  s.user = r.result.user;
  if (s.settings) s.settings = { ...s.settings, pocket_shapes: withoutKey(s.settings.pocket_shapes ?? {}, id) };   // Python dropped it too
  if (s.insert.preset === id) choosePreset(DEFAULT_PRESET);
}

/** A preset is picked: its pocket shape comes along, the one picked for it before or the insert's own. */
export function choosePreset(id: string | null): void {
  s.insert = { preset: id, custom: null };
  s.pocketShape = rememberedShape(s.settings?.pocket_shapes, id);
}

const withoutKey = <T>(map: Record<string, T>, key: string): Record<string, T> =>
  Object.fromEntries(Object.entries(map).filter(([k]) => k !== key));

// The kept shapes the newest pick asks for while a save is out: quick picks are saved in turn, the last one last.
let wantedShapes: Record<string, PocketShape> | null = null;

/** A pocket shape is picked. For a preset it is kept (quietly: a failed save says so) and comes back with it; the
 *  newest pick goes last, since Python keeps the newest MAX_POCKET_SHAPES. */
export async function choosePocketShape(shape: PocketShape): Promise<void> {
  s.pocketShape = shape;
  const id = s.insert.custom ? null : s.insert.preset;
  if (!id || !s.settings) return;
  const base = wantedShapes ?? s.settings.pocket_shapes ?? {};
  if (!wantedShapes && base[id] === shape) return;
  const saving = wantedShapes != null;
  wantedShapes = { ...withoutKey(base, id), [id]: shape };
  if (saving) return;   // the save that is out sends it when it is back
  try {
    let want: Record<string, PocketShape>;
    do {
      want = wantedShapes;
      const r = await tracker.run<Settings>({ key: 'pocket-shape', label: t('act.settings'), cmd: 'settings.save',
        args: { settings: { pocket_shapes: want } }, background: true });
      if (!r.ok) break;
      s.settings = r.result;
    } while (wantedShapes !== want);
  } finally {
    wantedShapes = null;
  }
}

export function start(): () => void {
  bridge.attach();
  onLangPref(value => bridge.post({ type: 'ui_language', value }));
  const off = bridge.onMessage(m => {
    if (m.type === 'progress' && s.loading) s.loading = { done: Number(m.done) || 0, total: Number(m.total) || 0 };
  });
  s.webgl = probeWebGL();
  void hello().then(loadPresets);
  return off;
}
