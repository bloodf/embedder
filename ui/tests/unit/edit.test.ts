// A pocket of the list taken in hand: the form shows it, and a change (a move, a size, a turn) plans it again in its place.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formOf, hitOf, othersOf, planArgs, previewsFor, restage, turn, verdict } from '../../src/app/logic.ts';
import type { Plan, PlanArgs, Staged } from '../../src/app/types.ts';

test('the form of a staged pocket plans the very same pocket again', () => {
  const all: PlanArgs[] = [
    { object: 0, part: 1, tri: 7, point: [1, 2, 3], mode: 'embedded', preset: 'magnet-disc-6x3' },
    { object: 2, part: 0, tri: 4, point: [4, 5, 6], mode: 'open', custom: { kind: 'nfc', shape: 'block', l: 30, w: 20, t: 1 }, spin: 45, cover: 0, center: true },
    { object: 1, part: 0, tri: 2, point: [7, 8, 9], mode: 'embedded', custom: { kind: 'magnet', shape: 'disc', d: 8, t: 2 }, cover: 1.5 },
    { object: 0, part: 0, tri: 3, point: [1, 1, 1], mode: 'open', preset: 'magnet-block-10x5x2', spin: 90, pocket_shape: 'square' },
  ];
  for (const args of all) {
    const form = formOf(args, 'kept-preset');
    assert.equal(JSON.stringify(planArgs(args.object, hitOf(args), form.insert, form)), JSON.stringify(args), 'key for key, in the same order');
  }
  assert.deepEqual(formOf(all[0], null), { insert: { preset: 'magnet-disc-6x3', custom: null }, mode: 'embedded', spin: null, cover: null, center: false, pocketShape: null, polarity: null });
  assert.equal(formOf(all[1], 'kept-preset').insert.preset, 'kept-preset', 'a custom size keeps the preset list where it was');
  assert.deepEqual(formOf(all[2], null).insert.custom, { kind: 'magnet', shape: 'disc', d: 8, l: 10, w: 5, t: 2 }, 'the sizes a disc does not use get the form\'s defaults');
  assert.deepEqual(hitOf(all[0]), { part: 1, tri: 7, point: [1, 2, 3] });
});

test('a moved pocket keeps its place in the list; the others go along for the proximity check', () => {
  const plan: Plan = { mode: 'open', blocked: null, preview: null };
  const a = { object: 0, point: [1, 1, 1] } as PlanArgs, b = { object: 0, point: [2, 2, 2] } as PlanArgs, moved = { object: 0, point: [9, 9, 9] } as PlanArgs;
  const list: readonly Staged[] = Object.freeze([{ key: 1, args: a, plan }, { key: 2, args: b, plan }]);
  const next = restage(list, 1, moved, { ...plan, label: 'moved' });
  assert.deepEqual(next.map(x => [x.key, x.args.point[0], x.plan.label]), [[1, 9, 'moved'], [2, 2, undefined]]);
  assert.equal(next[1], list[1], 'the others are the same objects');
  assert.deepEqual(restage(list, 5, moved, plan), list, 'a pocket that is gone changes nothing');
  assert.deepEqual(othersOf(list, 1), [b], 'never the pocket itself');
  assert.deepEqual(othersOf(list, null), [a, b], 'a new pocket is checked against all of them');
});

test('a plan for a new pocket is shown as it is; for a pocket of the list it is taken, or the pocket goes back', () => {
  const ok: Plan = { mode: 'embedded', blocked: null, preview: null, warnings: ['thin_cover'] };
  const blocked: Plan = { mode: 'embedded', blocked: { code: 'tilted_face', detail: '' }, preview: null };
  assert.equal(verdict(false, ok), 'show');
  assert.equal(verdict(false, blocked), 'show', 'a new pocket on a bad spot stays there, flagged, as after a click');
  assert.equal(verdict(true, ok), 'take', 'warnings do not stop a move');
  assert.equal(verdict(true, blocked), 'back', 'the list only holds pockets Apply can write');
});

test('the viewer leaves out the pocket in hand and knows each marker\'s pocket and face', () => {
  const preview = { positions: [0, 0, 0], indices: [0, 0, 0] };
  const at = (key: number): Staged => ({ key, args: { object: 0, part: 1, tri: key, point: [key, 0, 0] } as PlanArgs, plan: { mode: 'open', blocked: null, preview } });
  assert.deepEqual(previewsFor([at(1), at(2), at(3)], 0, 2).map(p => [p.key, p.base.tri]), [[1, 1], [3, 3]]);
  assert.deepEqual(previewsFor([at(1)], 0).map(p => p.base), [{ part: 1, tri: 1, point: [1, 0, 0] }]);
});

test('R turns a pocket in 15 degree steps and comes round after a full turn', () => {
  assert.equal(turn(null, 15), 15);
  assert.equal(turn(15, -15), null, 'no turn is no option, as in an empty field');
  assert.equal(turn(350, 15), 5);
  assert.equal(turn(0, -15), -15);
  assert.equal(turn(-350, -15), -5);
});
