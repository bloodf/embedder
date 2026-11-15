import { reactive } from 'vue';
import * as bridge from '../core/bridge';
import { Tracker, message } from '../core/tracker';
import { t, onLangPref } from '../core/i18n';
import { en } from '../core/messages';
import { probeWebGL } from '../core/three-probe';
import type { Hit } from '../core/pick';
import type { InsertChoice } from './logic';
import type { ApplyResult, Hello, Mode, Plan, PlanArgs, Preset, Project, Settings, Staged } from './types';

export const DEFAULT_PRESET = 'magnet-disc-6x3';

export const s = reactive({
  tab: 'embed',
  version: '',
  settings: null as Settings | null,
  error: '',
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
  // the last click, its plan, the staged pockets and the applied copy
  hit: null as Hit | null,
  plan: null as Plan | null,
  planArgs: null as PlanArgs | null,
  staged: [] as Staged[],
  remove: [] as string[],
  result: null as ApplyResult | null,
  opened: '' as '' | 'asked' | 'none',
});

/** A plugin error in words: the translated code (err.<code>) with Python's detail after it. */
export function errorText(e: unknown): string {
  if (e instanceof bridge.ReplyError) {
    const key = `err.${e.code}`;
    if (key in en) return t(key as keyof typeof en) + (e.detail ? ` (${e.detail})` : '');
    return e.detail || e.code;
  }
  return message(e);
}

export const tracker = new Tracker(
  (cmd, args) => bridge.command(cmd, args).catch(e => { throw new Error(errorText(e)); }),
  (key, params) => t(key, params));
bridge.setErrorSink(e => tracker.notify('error', t('msg.plugin', { error: message(e) })));

export async function hello(): Promise<void> {
  try {
    const r: Hello = await bridge.command('hello');
    s.version = r.version;
    s.settings = r.settings;
    s.error = '';
  } catch (e) {
    s.error = errorText(e);
  }
}

export async function loadPresets(): Promise<void> {
  const r = await tracker.run<{ builtin: Preset[]; user: Preset[] }>({ key: 'presets', label: t('act.presets'), cmd: 'presets.list' });
  if (!r.ok) return;
  s.builtin = r.result.builtin;
  s.user = r.result.user;
  if (!s.insert.preset && !s.insert.custom) {
    const pick = s.builtin.find(p => p.id === DEFAULT_PRESET) ?? s.builtin[0];
    s.insert = { preset: pick?.id ?? null, custom: null };
  }
}

export async function saveSettings(values: Partial<Settings>): Promise<boolean> {
  const r = await tracker.run<Settings>({ key: 'settings', label: t('act.settings'), cmd: 'settings.save', args: { settings: values }, okText: t('settings.saved') });
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
  if (s.insert.preset === id) s.insert = { preset: DEFAULT_PRESET, custom: null };
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
