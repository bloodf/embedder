// The pointer gesture on the 3D view: orbit or click on the part, select or drag on a pocket.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gesture, IDLE, type Effect, type Gesture, type Input } from '../../src/core/gesture.ts';

/** Feed the inputs one after the other; the effects they caused and the state at the end. */
function run(inputs: Input[], from: Gesture = IDLE): { effects: Effect[]; state: Gesture } {
  let state = from;
  const effects: Effect[] = [];
  for (const input of inputs) {
    const [next, effect] = gesture(state, input);
    state = next;
    effects.push(effect);
  }
  return { effects, state };
}
const down = (mark: number | 'edit' | null, x = 100, y = 100): Input => ({ type: 'down', x, y, mark });
const move = (x: number, y: number): Input => ({ type: 'move', x, y });
const up = (x: number, y: number): Input => ({ type: 'up', x, y });

test('a press on the part that does not move is a click', () => {
  assert.deepEqual(run([down(null), move(102, 101), up(102, 101)]), { effects: [null, null, 'click'], state: IDLE });
});

test('a press on the part that moves is the camera\'s: no click, no drag', () => {
  assert.deepEqual(run([down(null), move(140, 100), move(180, 120), up(180, 120)]), { effects: [null, null, null, null], state: IDLE });
});

test('a press on a pocket holds the camera; released in place it selects the pocket', () => {
  assert.deepEqual(run([down(7), up(101, 100)]), { effects: ['hold', 'select'], state: IDLE });
  assert.deepEqual(run([down('edit'), up(100, 100)]).effects, ['hold', 'select']);
});

test('a press on a pocket becomes a drag after 5 px, then every move slides it and the release drops it', () => {
  const r = run([down(7), move(102, 102), move(110, 100), move(150, 90), up(150, 90)]);
  assert.deepEqual(r.effects, ['hold', null, 'start', 'move', 'drop']);
  assert.deepEqual(r.state, IDLE);
  assert.deepEqual(run([down(7), move(110, 100)]).state, { kind: 'drag', mark: 7 }, 'the drag remembers which pocket');
});

test('cancel calls a drag off; the release that follows does nothing', () => {
  assert.deepEqual(run([down('edit'), move(120, 100), { type: 'cancel' }, up(130, 100)]).effects, ['hold', 'start', 'cancel', null]);
  assert.deepEqual(run([down(3), { type: 'cancel' }]), { effects: ['hold', null], state: IDLE }, 'a press that never moved has nothing to call off');
});

test('moves and releases with no press are nothing', () => {
  assert.deepEqual(run([move(1, 1), up(1, 1), { type: 'cancel' }]), { effects: [null, null, null], state: IDLE });
});
