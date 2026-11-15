// The Embed flow: load the project copy, pull the selected object's meshes, plan pockets on click, stage, apply,
// open. Mesh arrays never enter Vue state: they live in `meshes` and the page is told through s.mesh.version.
import * as bridge from '../core/bridge';
import { t } from '../core/i18n';
import { pullPart, type PartMesh } from '../core/mesh';
import type { Hit } from '../core/pick';
import { planArgs, stage, unstage, toggle } from './logic';
import { s, tracker, errorText } from './store';
import type { ApplyResult, Plan, Project, Staged } from './types';

const LONG_MS = 300_000;   // loading or writing a big project copy
const meshes = new Map<number, PartMesh[]>();
let pullToken = 0;
let planToken = 0;

export const meshesOf = (object: number): PartMesh[] => meshes.get(object) ?? [];
export const currentObject = () => (s.project && s.object != null ? s.project.objects[s.object] ?? null : null);

export async function loadProject(): Promise<void> {
  if (s.loading) return;
  pullToken++;   // a mesh pull still running for the old project must not land in the new one
  s.loading = { done: 0, total: 0 };
  const r = await tracker.run<Project>({ key: 'load', label: t('act.load'), cmd: 'project.load', timeoutMs: LONG_MS });
  s.loading = null;
  if (!r.ok) return;
  meshes.clear();
  pullToken++;
  s.mesh = { ...s.mesh, state: 'idle', done: 0, total: 0 };
  Object.assign(s, { project: r.result, object: null, hit: null, plan: null, planArgs: null, staged: [], remove: [], result: null, opened: '' });
  if (r.result.objects.length) await selectObject(0);
}

export async function selectObject(k: number): Promise<void> {
  const project = s.project;
  const obj = project?.objects[k];
  if (!project || !obj) return;
  Object.assign(s, { object: k, hit: null, plan: null, planArgs: null });
  if (obj.embedded_block && s.mode === 'embedded') s.mode = 'open';
  if (meshes.has(k)) { s.mesh = { ...s.mesh, state: 'ready', version: s.mesh.version + 1 }; return; }
  const token = ++pullToken;
  const total = obj.parts.reduce((n, p) => n + p.pos_chunks + p.idx_chunks, 0);
  s.mesh = { ...s.mesh, state: 'loading', done: 0, total };
  try {
    const out: PartMesh[] = [];
    for (const p of obj.parts) {
      const fetch = (kind: 'pos' | 'idx', i: number) => bridge.command('mesh.chunk', { job: project.job, object: k, part: p.part, kind, i });
      out.push(await pullPart(fetch, p, () => { if (token === pullToken) s.mesh = { ...s.mesh, done: s.mesh.done + 1 }; }));
      if (token !== pullToken) return;   // another object (or project) was chosen meanwhile
    }
    meshes.set(k, out);
    s.mesh = { ...s.mesh, state: 'ready', version: s.mesh.version + 1 };
  } catch (e) {
    if (token !== pullToken) return;
    s.mesh = { ...s.mesh, state: 'error' };
    tracker.notify('error', t('msg.failed', { action: t('act.mesh'), error: errorText(e) }));
  }
}

/** A click on a face (or the fallback's centre pick): plan the pocket there. */
export function placeAt(hit: Hit | null): Promise<void> {
  if (!hit) {
    tracker.notify('info', t('place.miss'));
    return Promise.resolve();
  }
  s.hit = hit;
  return replan();
}

/** Plan again for the last click (after a click, or a change of insert, mode, spin or cover). Last request wins. */
export async function replan(): Promise<void> {
  const project = s.project;
  if (!project || s.object == null || !s.hit) return;
  const args = planArgs(s.object, s.hit, s.insert, { mode: s.mode, spin: s.spin, cover: s.cover, center: s.center });
  if (!args) return;
  const token = ++planToken;
  try {
    const others = s.staged.map(x => x.args);
    const plan: Plan = await bridge.command('pocket.plan', { job: project.job, ...args, ...(others.length ? { others } : {}) });
    if (token !== planToken) return;
    Object.assign(s, { plan, planArgs: args });
  } catch (e) {
    if (token !== planToken) return;
    Object.assign(s, { plan: null, planArgs: null, hit: null });
    tracker.notify('error', t('msg.failed', { action: t('act.plan'), error: errorText(e) }));
  }
}

/** After a settings change or a deleted preset: plan the staged pockets again, so the list, the previews and the
 *  pauses match what Apply will write. A pocket that no longer plans would make Apply fail: it is dropped, saying so. */
export async function replanStaged(): Promise<void> {
  const project = s.project, before = s.staged;
  if (!project || s.result || !before.length) return;
  const kept: Staged[] = [], dropped: string[] = [];
  for (const x of before) {
    const others = before.filter(o => o !== x).map(o => o.args);
    try {
      const plan: Plan = await bridge.command('pocket.plan', { job: project.job, ...x.args, ...(others.length ? { others } : {}) });
      if (plan.blocked) dropped.push(x.plan.label ?? '?'); else kept.push({ ...x, plan });
    } catch {
      dropped.push(x.plan.label ?? '?');
    }
  }
  if (s.project !== project || s.staged !== before) return;   // reloaded or edited meanwhile: that state wins
  s.staged = kept;
  if (dropped.length) tracker.notify('error', t('list.dropped', { labels: dropped.join(', ') }));
  await replan();
}

export function addStaged(): void {
  if (!s.plan || s.plan.blocked || !s.planArgs) return;
  Object.assign(s, { staged: stage(s.staged, s.planArgs, s.plan), plan: null, planArgs: null, hit: null, result: null });
}

export function removeStaged(key: number): void { s.staged = unstage(s.staged, key); }
export function markRemove(id: string, on: boolean): void { s.remove = toggle(s.remove, id, on); }

export async function apply(): Promise<void> {
  const project = s.project;
  if (!project || (!s.staged.length && !s.remove.length)) return;
  const r = await tracker.run<ApplyResult>({ key: 'apply', label: t('act.apply'), cmd: 'project.apply', timeoutMs: LONG_MS,
    args: { job: project.job, pockets: s.staged.map(x => x.args), remove: s.remove } });
  if (r.ok) Object.assign(s, { result: r.result, opened: '', staged: [], remove: [], plan: null, planArgs: null, hit: null });
}

export async function openResult(): Promise<void> {
  if (!s.result) return;
  const r = await tracker.run<{ open: 'asked' | 'none' }>({ key: 'open', label: t('act.open'), cmd: 'project.open', args: { path: s.result.path } });
  if (r.ok) s.opened = r.result.open;
}
