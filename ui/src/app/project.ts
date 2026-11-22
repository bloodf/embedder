// The Embed flow: load the project copy, pull the selected object's meshes, plan pockets on click, move them, stage,
// apply, open. Mesh arrays never enter Vue state: they live in `meshes` and the page is told through s.mesh.version.
import * as bridge from '../core/bridge';
import { t, tMaybe, insertLabel } from '../core/i18n';
import { pullPart, type PartMesh } from '../core/mesh';
import type { Hit } from '../core/pick';
import { customDims, formOf, hitOf, othersOf, planArgs, restage, stage, unstage, toggle, verdict } from './logic';
import { s, tracker, errorText } from './store';
import type { ApplyResult, Plan, PlanArgs, Project, Staged } from './types';

const LONG_MS = 300_000;   // loading or writing a big project copy
const PLAN_WAIT_MS = 1500;   // a plan that has not answered by then no longer holds the next one back
const LIVE_PLAN_MS = 100;    // while a pocket slides (a drag, a held arrow key) a new plan is asked at most this often
const meshes = new Map<number, PartMesh[]>();
let pullToken = 0;
// Planning the pocket in hand: the request that counts, when the one still out was sent (0: none), when the last one
// was sent, whether a forced plan was asked while one was out, the arguments asked last (asking the same again is
// skipped) and the timer of a plan that waits for its turn.
let planToken = 0;
let planOut = 0;
let planSent = 0;
let planAgain = false;
let planKey = '';
let planTimer: ReturnType<typeof setTimeout> | undefined;
const kept = new Map<number, number>();   // per pocket of the list: the newest keepMove, whose answer alone counts
let dragFrom: Pick<typeof s, 'hit' | 'plan' | 'planArgs' | 'center'> | null = null;

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
  Object.assign(s, { project: r.result, object: null, staged: [], remove: [], result: null, opened: '' });
  letGo();
  if (r.result.objects.length) await selectObject(0);
}

export async function selectObject(k: number): Promise<void> {
  const project = s.project;
  const obj = project?.objects[k];
  if (!project || !obj) return;
  letGo();
  s.object = k;
  if (obj.embedded_block && s.mode === 'embedded') s.mode = 'open';
  if (meshes.has(k)) {
    pullToken++;   // a pull still running for the object left must not mark this one loading or failed
    s.mesh = { ...s.mesh, state: 'ready', version: s.mesh.version + 1 };
    return;
  }
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

/** One passing line about the pocket in hand (the face ends there, the pocket went back), shown with its plan. A banner
 *  above the page would push the 3D view down under the pointer that just dropped the pocket. */
function note(text: string | null): void {
  s.note = text ?? '';
}

/** The pocket in hand changed or was let go: an answer still on its way is not for it. `planned`: what is in hand now. */
function forgetPlans(planned: PlanArgs | null = null): void {
  planToken++;
  planOut = 0;
  s.planning = false;
  planAgain = false;
  planKey = planned ? JSON.stringify(planned) : '';
  clearTimeout(planTimer);
  planTimer = undefined;
}

/** Nothing in hand: no new pocket being placed, no pocket of the list selected. */
function letGo(): void {
  keepMove();
  forgetPlans();
  dragFrom = null;
  Object.assign(s, { selected: null, dragging: false, hit: null, plan: null, planArgs: null, note: '' });
}

/** Put a pocket of the list in hand as it is in the list: the form shows what it was planned with. */
function takeStaged(x: Staged): void {
  if (s.selected !== x.key) keepMove();
  forgetPlans(x.args);
  Object.assign(s, { selected: x.key, ...formOf(x.args, s.insert.preset), hit: hitOf(x.args), plan: x.plan, planArgs: x.args });
}

/** The pocket of the list in hand is let go while its last change is not its row yet (a drop, an arrow key or a
 *  setting whose plan is out or not even asked): plan that change for the row, which takes the answer, or stays as it
 *  was and says why. Called before the pocket in hand changes, so the answer is bound to the row, not to the hand. */
function keepMove(): void {
  const project = s.project, x = s.staged.find(p => p.key === s.selected), args = argsInHand();
  if (!project || !x || !args || JSON.stringify(args) === JSON.stringify(x.args)) return;
  const others = othersOf(s.staged, x.key), gen = (kept.get(x.key) ?? 0) + 1;
  kept.set(x.key, gen);
  // Reloaded, let go again with a newer move, removed, changed again, or back in hand (what the hand shows wins).
  const current = () => s.project === project && kept.get(x.key) === gen;
  bridge.command('pocket.plan', { job: project.job, ...args, ...(others.length ? { others } : {}) }).then((plan: Plan) => {
    if (!current() || s.selected === x.key || !s.staged.includes(x)) return;
    if (plan.blocked) tracker.notify('info', t('edit.back', { reason: tMaybe(`block.${plan.blocked.code}`, plan.blocked.detail || plan.blocked.code) }));
    else s.staged = restage(s.staged, x.key, args, plan);
  }, e => { if (current()) tracker.notify('error', t('msg.failed', { action: t('act.plan'), error: errorText(e) })); });
}

/** Take a pocket of the list in hand (a click on its row or on its marker in the 3D view): the form then changes that
 *  pocket in place, and it can be dragged, nudged and turned. null (or a pocket that is gone) lets go of the one in hand. */
export function selectStaged(key: number | null): void {
  const x = s.staged.find(p => p.key === key);
  note(null);
  if (!x) {
    if (s.selected != null) letGo();
    return;
  }
  if (x.args.object !== s.object) void selectObject(x.args.object);   // shows its object; state is set before the meshes come
  takeStaged(x);
}

/** A click on a face (or the fallback's centre pick): plan a new pocket there. A pocket of the list that was in hand is
 *  let go: a click never moves it, only a drag or the arrow keys do. */
export function placeAt(hit: Hit | null): Promise<void> {
  if (!hit) {
    tracker.notify('info', t('place.miss'));
    return Promise.resolve();
  }
  if (s.selected != null) letGo();
  s.hit = hit;
  return replan(true);
}

/** The pocket in hand goes to `hit`: dragged over the surface, or stepped with an arrow key (null: the face ends
 *  there). Centring is off from here on, or it would pull the pocket back to the middle of the face. */
export function moveTo(hit: Hit | null): void {
  if (!hit) {
    note(t('place.miss'));
    return;
  }
  Object.assign(s, { hit, center: false });
  void replan();
}

/** The pointer starts sliding a pocket: the one in hand ('edit'), or a pocket of the list, which it takes in hand first. */
export function dragStart(mark: number | 'edit'): void {
  if (mark !== 'edit') selectStaged(mark);
  dragFrom = { hit: s.hit, plan: s.plan, planArgs: s.planArgs, center: s.center };
  s.dragging = true;
}

/** The drag is over. Released: plan the pocket where it lies, the way a click there is planned. Called off (Escape):
 *  it goes back to where the drag took it from. */
export function dragEnd(cancelled: boolean): void {
  const from = dragFrom;
  dragFrom = null;
  s.dragging = false;
  if (!cancelled) {
    void replan(true);
  } else if (from) {
    forgetPlans(from.planArgs);
    Object.assign(s, from);
  }
}

/** Delete in the 3D view: the pocket in hand goes, off the list if it was on it. */
export function removeInHand(): void {
  if (s.selected != null) removeStaged(s.selected); else letGo();
}

/** The pocket.plan arguments of the pocket in hand as the form stands; null with nothing in hand. */
function argsInHand(): PlanArgs | null {
  if (s.object == null || !s.hit) return null;
  return planArgs(s.object, s.hit, s.insert, { mode: s.mode, spin: s.spin, cover: s.cover, center: s.center, pocketShape: s.pocketShape });
}

/** Plan the pocket in hand again: after a click, a move, or a change of insert, mode, rotation or cover. A drag or a
 *  held arrow key never floods the plugin: one request is out at a time, a new one goes at most every LIVE_PLAN_MS,
 *  and what changed meanwhile is planned after that. `force`: plan now, even with the arguments planned last (a
 *  click, the end of a drag, new settings). */
export async function replan(force = false): Promise<void> {
  const project = s.project, args = argsInHand();
  if (!project || !args) return;
  const key = JSON.stringify(args);
  if (!force && key === planKey) return;
  if (planOut && Date.now() - planOut < PLAN_WAIT_MS) {   // its answer plans what is in hand by then
    planAgain ||= force;
    return;
  }
  const wait = force ? 0 : planSent + LIVE_PLAN_MS - Date.now();
  if (wait > 0) {
    planTimer ??= setTimeout(() => { planTimer = undefined; void replan(); }, wait);
    return;
  }
  const token = ++planToken;
  planOut = planSent = Date.now();
  s.planning = true;
  planAgain = false;
  planKey = key;
  const others = othersOf(s.staged, s.selected), said = s.note;
  let plan: Plan | null = null, error: unknown = null;
  try {
    plan = await bridge.command('pocket.plan', { job: project.job, ...args, ...(others.length ? { others } : {}) });
  } catch (e) {
    error = e;
  }
  if (token !== planToken) return;
  planOut = 0;
  s.planning = false;
  const now = argsInHand();
  const stale = planAgain || !now || JSON.stringify(now) !== key;   // the pocket moved on while Python planned
  // Under a drag every answer is shown (the preview slides on from it) and none is final: the release plans once more.
  if (s.dragging || stale) {
    if (s.dragging && plan) Object.assign(s, { plan, planArgs: args });
    if (stale) await replan(planAgain);
    return;
  }
  settle(plan, args, error, said);
}

/** A plan that stands: show it for a new pocket; a pocket of the list takes it, or goes back when it cannot be made.
 *  `said`: the note that stood when the plan was asked. Success clears that one, not one said since (an arrow key that
 *  ran into the edge of the face while this plan was out). */
function settle(plan: Plan | null, args: PlanArgs, error: unknown, said: string): void {
  const mine = s.staged.find(x => x.key === s.selected) ?? null;
  if (!plan) {   // the plugin refused the request
    tracker.notify('error', t('msg.failed', { action: t('act.plan'), error: errorText(error) }));
    if (mine) takeStaged(mine); else letGo();
    return;
  }
  const what = verdict(!!mine, plan);
  if (what === 'back' && mine) {
    const reason = plan.blocked ? tMaybe(`block.${plan.blocked.code}`, plan.blocked.detail || plan.blocked.code) : '';
    takeStaged(mine);
    note(t('edit.back', { reason }));
    return;
  }
  if (s.note === said) note(null);
  Object.assign(s, { plan, planArgs: args, ...(mine ? { staged: restage(s.staged, mine.key, args, plan) } : {}) });
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
      if (plan.blocked) dropped.push(insertLabel(x.plan.label)); else kept.push({ ...x, plan });
    } catch {
      dropped.push(insertLabel(x.plan.label));
    }
  }
  if (s.project !== project || s.staged !== before) return;   // reloaded or edited meanwhile: that state wins
  s.staged = kept;
  if (dropped.length) tracker.notify('error', t('list.dropped', { labels: dropped.join(', ') }));
  if (s.selected != null && !kept.some(x => x.key === s.selected)) letGo();   // the pocket in hand was dropped
  await replan(true);
}

/** Add pocket stages what the plan shows: only once that plan is the answer for where the pocket is, with no drag on
 *  and no plan out (a drop or an arrow key whose answer has not come would add the pocket where it was). */
export function canAdd(): boolean {
  const args = argsInHand();
  return !!s.plan && !s.plan.blocked && !!s.planArgs && s.selected == null && !s.dragging && !s.planning
    && !!args && JSON.stringify(args) === JSON.stringify(s.planArgs);
}

export function addStaged(): void {
  if (!canAdd() || !s.plan || !s.planArgs) return;
  const staged = stage(s.staged, s.planArgs, s.plan);
  letGo();
  Object.assign(s, { staged, result: null });
}

export async function autoFridge(count: 'auto' | number = 'auto', allObjects = false): Promise<void> {
  const project = s.project;
  if (!project || (!allObjects && s.object == null)) return;
  const obj = s.object ?? 0;
  const which = s.insert.custom ? { custom: customDims(s.insert.custom) } : s.insert.preset ? { preset: s.insert.preset } : { preset: 'magnet-disc-6x2' };
  const r = await tracker.run<{ items: { args: PlanArgs; plan: Plan }[]; count: number }>({
    key: 'auto-fridge',
    label: t('act.autoFridge'),
    cmd: 'pocket.auto_fridge',
    args: {
      job: project.job,
      object: allObjects ? 'all' : obj,
      count,
      mode: s.mode,
      spread: 0.28,
      ...which,
      ...(s.spin ? { spin: s.spin } : {}),
      ...(s.cover != null ? { cover: s.cover } : {}),
      ...(s.pocketShape ? { pocket_shape: s.pocketShape } : {}),
    },
  });
  if (!r.ok || !r.result.items.length) return;
  let staged = allObjects
    ? s.staged.filter(x => x.plan.face !== 'bottom')
    : s.staged.filter(x => x.args.object !== obj || x.plan.face !== 'bottom');
  for (const item of r.result.items) staged = stage(staged, item.args, item.plan);
  letGo();
  Object.assign(s, { staged, result: null });
}

export function removeStaged(key: number): void {
  s.staged = unstage(s.staged, key);   // first: a pocket that goes is not planned into its row again
  if (key === s.selected) letGo();
}
export function markRemove(id: string, on: boolean): void { s.remove = toggle(s.remove, id, on); }

export async function apply(): Promise<void> {
  const project = s.project;
  if (!project || (!s.staged.length && !s.remove.length)) return;
  const r = await tracker.run<ApplyResult>({ key: 'apply', label: t('act.apply'), cmd: 'project.apply', timeoutMs: LONG_MS,
    args: { job: project.job, pockets: s.staged.map(x => x.args), remove: s.remove } });
  if (!r.ok) return;
  Object.assign(s, { result: r.result, applies: Math.max(s.applies + 1, Date.now()), opened: '', staged: [], remove: [] });
  letGo();
}

export async function openResult(): Promise<void> {
  if (!s.result) return;
  const r = await tracker.run<{ open: 'asked' | 'none' }>({ key: 'open', label: t('act.open'), cmd: 'project.open', args: { path: s.result.path } });
  if (r.ok) s.opened = r.result.open;
}
