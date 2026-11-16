// The pointer gesture on the 3D view as a pure state machine (tests/unit/gesture.test.ts). A press on a pocket holds
// the camera still and becomes a drag once it has moved; a press anywhere else is the camera's, or a click.
import { isClick } from './pick.ts';

/** A pocket that can be grabbed: one of the list (its key), or the one in hand ('edit'). */
export type Mark = number | 'edit';
export type Gesture = { kind: 'idle' } | { kind: 'press'; mark: Mark | null; x: number; y: number } | { kind: 'drag'; mark: Mark };
export type Input = { type: 'down'; x: number; y: number; mark: Mark | null } | { type: 'move' | 'up'; x: number; y: number } | { type: 'cancel' };
/** hold: a pocket is under the pointer, the camera must stay · start: the press became a drag · move: the drag goes on ·
 *  drop: released · cancel: the drag is called off · select: a click on a pocket · click: a click anywhere else. */
export type Effect = 'hold' | 'start' | 'move' | 'drop' | 'cancel' | 'select' | 'click' | null;

export const IDLE: Gesture = { kind: 'idle' };

export function gesture(g: Gesture, e: Input): [Gesture, Effect] {
  if (e.type === 'down') return [{ kind: 'press', mark: e.mark, x: e.x, y: e.y }, e.mark == null ? null : 'hold'];
  if (e.type === 'cancel') return [IDLE, g.kind === 'drag' ? 'cancel' : null];
  if (g.kind === 'drag') return e.type === 'move' ? [g, 'move'] : [IDLE, 'drop'];
  if (g.kind !== 'press') return [g, null];
  if (e.type === 'move') return g.mark == null || isClick(g, e) ? [g, null] : [{ kind: 'drag', mark: g.mark }, 'start'];
  return [IDLE, !isClick(g, e) ? null : g.mark == null ? 'click' : 'select'];
}
