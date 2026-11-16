// Pure rules of the Embed panel (no Vue, no bridge), unit-tested in tests/unit/logic.test.ts.
import type { Custom, Kind, Mode, ObjectInfo, Plan, PlanArgs, Preset, Staged } from './types.ts';
import type { Hit } from '../core/pick.ts';

export interface InsertChoice { preset: string | null; custom: Custom | null }
export interface Options { mode: Mode; spin: number | null; cover: number | null; center?: boolean }

export function customDims(c: Custom): Record<string, unknown> {
  return c.shape === 'disc' ? { kind: c.kind, shape: c.shape, d: c.d, t: c.t } : { kind: c.kind, shape: c.shape, l: c.l, w: c.w, t: c.t };
}

/** The pocket.plan arguments (without job) for a hit, an insert and the options; null without an insert. */
export function planArgs(object: number, hit: Hit, insert: InsertChoice, o: Options): PlanArgs | null {
  const base: PlanArgs = { object, part: hit.part, tri: hit.tri, point: hit.point, mode: o.mode };
  const which = insert.custom ? { custom: customDims(insert.custom) } : insert.preset ? { preset: insert.preset } : null;
  if (!which) return null;
  return { ...base, ...which, ...(o.spin ? { spin: o.spin } : {}), ...(o.cover != null ? { cover: o.cover } : {}), ...(o.center ? { center: true } : {}) };
}

/** Why Embedded is not offered: the object's (or project's) block first, then the last plan's. */
export function embeddedBlock(obj: ObjectInfo | null, plan: Plan | null): string | null {
  if (obj?.embedded_block) return obj.embedded_block;
  return plan?.blocked && plan.mode === 'embedded' ? plan.blocked.code : null;
}

export interface PauseGroup { z: number; items: { label: string; n: number }[] }

/** Staged embedded pockets grouped by pause height, lowest first: "Pauses at Z 5.40 mm: insert 2 x 6x3 magnet". */
export function pauseSummary(staged: readonly Staged[]): PauseGroup[] {
  const groups = new Map<number, Map<string, number>>();
  for (const s of staged) {
    const z = s.plan.pause_z;
    if (z == null || s.plan.mode !== 'embedded') continue;
    const key = Math.round(z * 1e6) / 1e6;
    const labels = groups.get(key) ?? new Map<string, number>();
    labels.set(s.plan.label ?? '?', (labels.get(s.plan.label ?? '?') ?? 0) + (s.plan.copies ?? 1));
    groups.set(key, labels);
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0])
    .map(([z, labels]) => ({ z, items: [...labels.entries()].map(([label, n]) => ({ label, n })) }));
}

export interface InsertCount { label: string; kind: Kind; n: number }

/** Every insert the staged pockets need (open ones too, once per copy of the object): magnets first, then NFC. */
export function insertsNeeded(staged: readonly Staged[]): InsertCount[] {
  const counts = new Map<string, InsertCount>();
  for (const s of staged) {
    const label = s.plan.label ?? '?', kind = s.plan.kind ?? 'magnet', key = `${kind}\u0000${label}`;
    const n = (counts.get(key)?.n ?? 0) + (s.plan.copies ?? 1);
    counts.set(key, { label, kind, n });
  }
  return [...counts.values()].sort((a, b) => (a.kind === b.kind ? a.label.localeCompare(b.label) : a.kind === 'magnet' ? -1 : 1));
}

export type KindPreview = NonNullable<Plan['preview']> & { kind: Kind; key: number; base: Hit };

/** Previews of the staged pockets on one object (the viewer shows one object at a time), each with the insert kind
 *  that colours it, its key in the list and the face it was planned on. `except`: the pocket in hand, drawn apart. */
export function previewsFor(staged: readonly Staged[], object: number | null, except: number | null = null): KindPreview[] {
  return staged.flatMap(x => (x.args.object === object && x.key !== except && x.plan.preview
    ? [{ ...x.plan.preview, kind: x.plan.kind ?? 'magnet', key: x.key, base: hitOf(x.args) }] : []));
}

// ---- a pocket of the list taken in hand: the form shows it, and a change plans it again in its place

export const hitOf = (a: PlanArgs): Hit => ({ part: a.part, tri: a.tri, point: a.point });

/** The form values a pocket was planned with; planArgs() of them gives the same arguments back. `preset`: where the
 *  preset list stays while a custom size is shown. */
export function formOf(a: PlanArgs, preset: string | null): Required<Options> & { insert: InsertChoice } {
  const insert: InsertChoice = a.custom ? { preset, custom: { d: 6, l: 10, w: 5, ...a.custom } as Custom } : { preset: a.preset ?? null, custom: null };
  return { insert, mode: a.mode, spin: a.spin ?? null, cover: a.cover ?? null, center: !!a.center };
}

/** The list with one pocket planned anew, in its place. */
export function restage(list: readonly Staged[], key: number, args: PlanArgs, plan: Plan): Staged[] {
  return list.map(x => (x.key === key ? { key, args, plan } : x));
}

/** The pockets that go along with a plan for the NFC-near-magnet check: all of the list but the one being planned. */
export function othersOf(list: readonly Staged[], key: number | null): PlanArgs[] {
  return list.filter(x => x.key !== key).map(x => x.args);
}

/** What a finished plan means. A new pocket shows it as it is, blocked or not, as after a click. A pocket of the list
 *  takes it, unless it is blocked: the list only holds pockets Apply can write, so that pocket goes back. */
export function verdict(listed: boolean, plan: Plan): 'show' | 'take' | 'back' {
  return !listed ? 'show' : plan.blocked ? 'back' : 'take';
}

/** A turn of `by` degrees on top of `spin`, round after a full turn; null for no turn (the empty field). */
export function turn(spin: number | null, by: number): number | null {
  return ((spin ?? 0) + by) % 360 || null;
}

/** The bounding size (x, y, z in mm) of meshes in the plate frame; null without vertices. */
export function sizeOf(parts: readonly { positions: ArrayLike<number> }[]): [number, number, number] | null {
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (const p of parts) {
    for (let i = 0; i + 2 < p.positions.length; i += 3) {
      for (let a = 0; a < 3; a++) {
        const v = p.positions[i + a];
        if (v < min[a]) min[a] = v;
        if (v > max[a]) max[a] = v;
      }
    }
  }
  return max[0] >= min[0] ? [max[0] - min[0], max[1] - min[1], max[2] - min[2]] : null;
}

/** A message split after its first sentence or colon, so a banner can set the lead apart: ["Apply failed:", "the reason"].
 *  Chinese ends a sentence with full-width 。：！？ and no space after it. */
export function splitLead(text: string): [string, string] {
  const m = /^(.+?(?:[.:!?…](?=\s)|[。：！？]))\s*(\S.*)$/s.exec(text);
  return m ? [m[1], m[2]] : [text, ''];
}

export interface PresetGroup { key: 'magnet' | 'nfc' | 'mine'; items: Preset[] }

/** Built-ins split into magnets and NFC, the user's own presets last; empty groups dropped. */
export function groupPresets(builtin: readonly Preset[], user: readonly Preset[]): PresetGroup[] {
  return ([
    { key: 'magnet', items: builtin.filter(p => p.kind === 'magnet') },
    { key: 'nfc', items: builtin.filter(p => p.kind === 'nfc') },
    { key: 'mine', items: [...user] },
  ] as PresetGroup[]).filter(g => g.items.length);
}

export function stage(list: readonly Staged[], args: PlanArgs, plan: Plan): Staged[] {
  const key = list.reduce((m, s) => Math.max(m, s.key), 0) + 1;
  return [...list, { key, args, plan }];
}

export function unstage(list: readonly Staged[], key: number): Staged[] {
  return list.filter(s => s.key !== key);
}

export function toggle(list: readonly string[], id: string, on: boolean): string[] {
  const rest = list.filter(x => x !== id);
  return on ? [...rest, id] : rest;
}
