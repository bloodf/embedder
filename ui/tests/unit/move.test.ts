// Moving a pocket without WebGL: face normals, where a preview sits on its face, sliding it, arrow-key steps and
// grabbing a small marker.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';
import { anchorOf, boundsOf, fitCamera, nearest, normalAt, nudge, partMesh, slide, toScreen } from '../../src/core/pick.ts';
import { CUBE_IDX, CUBE_POS } from './cube.ts';

const cube = (part = 0) => partMesh({ part, positions: CUBE_POS, indices: CUBE_IDX });
const near = (a: number, b: number, what: string) => assert.ok(Math.abs(a - b) < 1e-4, `${what}: ${a} vs ${b}`);
const vec = (v: Vector3 | null, to: number[], what: string) => { assert.ok(v, what); v.toArray().forEach((c, i) => near(c, to[i], `${what} [${i}]`)); };
const TOP = { part: 0, tri: 2, point: [100, 100, 20] as [number, number, number] };
const FRONT = { part: 0, tri: 4, point: [100, 90, 10] as [number, number, number] };

/** A camera straight above the cube: screen up is +Y, screen right is +X. */
function above(): PerspectiveCamera {
  const cam = new PerspectiveCamera(40, 1, 0.1, 1000);
  cam.position.set(100, 100, 100);
  cam.up.set(0, 1, 0);
  cam.lookAt(100, 100, 0);
  cam.updateMatrixWorld();
  return cam;
}

test('the normal of a hit face points out of the part; a face the part does not have has none', () => {
  vec(normalAt([cube()], TOP), [0, 0, 1], 'top');
  vec(normalAt([cube()], FRONT), [0, -1, 0], 'front');
  assert.equal(normalAt([cube()], { ...TOP, tri: 99 }), null);
  assert.equal(normalAt([cube()], { ...TOP, part: 5 }), null);
});

test('a preview is anchored where its middle meets the face, however deep Python sank it', () => {
  const sunk = [97, 97, 15.6, 103, 103, 18.8];   // an embedded cavity under the top, 1.2 mm of cover
  vec(anchorOf(sunk, [cube()], TOP), [100, 100, 20], 'under the top face');
  const behind = [96, 91, 7, 104, 94.4, 13.2];   // a slot behind the front wall
  vec(anchorOf(behind, [cube()], FRONT), [100, 90, 10.1], 'behind the front wall');
  assert.equal(anchorOf(sunk, [cube()], { ...TOP, tri: 99 }), null);
});

test('sliding keeps a preview as deep under the new spot, turned to the new face', () => {
  const anchor = new Vector3(100, 100, 20), up = new Vector3(0, 0, 1);
  const along = slide(anchor, up, new Vector3(105, 98, 20), up);
  vec(new Vector3(100, 100, 17).applyMatrix4(along), [105, 98, 17], 'the same face: a plain move');
  const over = slide(anchor, up, new Vector3(100, 90, 10), new Vector3(0, -1, 0));
  vec(anchor.clone().applyMatrix4(over), [100, 90, 10], 'the anchor lands on the new point');
  vec(new Vector3(100, 100, 17).applyMatrix4(over), [100, 93, 10], '3 mm under the top becomes 3 mm behind the wall');
});

test('an arrow key steps along the face in the direction the camera shows; the step ends where the face does', () => {
  const cam = above();
  const right = nudge([cube()], cam, TOP, 1, 0, 0.5);
  assert.ok(right);
  vec(new Vector3(...right.point), [100.5, 100, 20], 'half a millimetre to the right');
  assert.ok(right.tri === 2 || right.tri === 3, 'still a top triangle: ' + right.tri);
  const far = nudge([cube()], cam, TOP, 0, 1, 5);
  vec(far && new Vector3(...far.point), [100, 105, 20], 'Shift: 5 mm up the screen');
  assert.equal(nudge([cube()], cam, { ...TOP, point: [108, 100, 20] }, 1, 0, 5), null, 'past the edge there is no face');
  assert.equal(nudge([cube()], cam, { ...TOP, tri: 99 }, 1, 0, 5), null, 'nor on a face that is not there');
});

test('on a wall, up on the screen is up the wall', () => {
  const cam = new PerspectiveCamera(40, 1, 0.1, 1000);
  fitCamera(cam, boundsOf([cube()]));
  const higher = nudge([cube()], cam, FRONT, 0, 1, 5);
  assert.ok(higher);
  near(higher.point[1], 90, 'stays on the wall');
  assert.ok(higher.point[2] > 14.5, 'and climbs it: ' + higher.point);
  near(Math.hypot(higher.point[0] - 100, higher.point[2] - 10), 5, 'by the whole step');
});

test('a point is found on the screen, and the nearest one within reach of the pointer is the one grabbed', () => {
  const cam = above(), rect = { left: 10, top: 20, width: 400, height: 400 };
  const mid = toScreen(new Vector3(100, 100, 20), rect, cam);
  assert.deepEqual([Math.round(mid.x), Math.round(mid.y)], [210, 220], 'the point under the camera is in the middle');
  const points = [new Vector3(95, 100, 20), null, new Vector3(105, 100, 20)];
  const at = toScreen(points[2] as Vector3, rect, cam);
  assert.equal(nearest(points, at.x + 3, at.y - 2, rect, cam, 12), 2, 'within 12 px');
  assert.equal(nearest(points, at.x + 30, at.y, rect, cam, 12), -1, 'too far from all of them');
  assert.equal(nearest([], 0, 0, rect, cam, 12), -1);
});
