// Picking without WebGL: NDC, click-vs-drag, raycast on a cube, the fallback centre pick and the camera fit.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Box3, PerspectiveCamera, Vector3 } from 'three';
import { boundsOf, centrePick, fitCamera, isClick, partMesh, pick, toNdc } from '../../src/core/pick.ts';
import { CUBE_IDX, CUBE_POS } from './cube.ts';

const cube = (part = 0) => partMesh({ part, positions: CUBE_POS, indices: CUBE_IDX });
const near = (a: number, b: number, what: string) => assert.ok(Math.abs(a - b) < 1e-4, `${what}: ${a} vs ${b}`);

test('pointer to normalized device coordinates', () => {
  const rect = { left: 10, top: 20, width: 200, height: 100 };
  assert.deepEqual(toNdc(110, 70, rect), { x: 0, y: 0 });
  assert.deepEqual(toNdc(10, 20, rect), { x: -1, y: 1 });
  assert.deepEqual(toNdc(210, 120, rect), { x: 1, y: -1 });
});

test('a click moves less than 5 px; more is a drag', () => {
  assert.equal(isClick({ x: 0, y: 0 }, { x: 3, y: 3 }), true);
  assert.equal(isClick({ x: 0, y: 0 }, { x: 3, y: 4 }), false);
  assert.equal(isClick({ x: 0, y: 0 }, { x: 0, y: 0 }), true);
});

test('a ray from above hits the top face of the cube', () => {
  const cam = new PerspectiveCamera(40, 1, 0.1, 1000);
  cam.position.set(100, 100, 100);
  cam.up.set(0, 1, 0);
  cam.lookAt(100, 100, 0);
  cam.updateMatrixWorld();
  const hit = pick([cube(3)], { x: 0, y: 0 }, cam);
  assert.ok(hit);
  assert.equal(hit.part, 3);
  assert.ok(hit.tri === 2 || hit.tri === 3, 'top triangle: ' + hit.tri);
  near(hit.point[0], 100, 'x'); near(hit.point[1], 100, 'y'); near(hit.point[2], 20, 'z');
  assert.equal(pick([cube()], { x: 0.99, y: 0.99 }, cam), null, 'nothing in the corner');
});

test('the fallback picks straight down onto the top and up onto the bottom', () => {
  const top = centrePick([cube()], 'top');
  assert.ok(top && (top.tri === 2 || top.tri === 3));
  near(top.point[2], 20, 'top z');
  const bottom = centrePick([cube()], 'bottom');
  assert.ok(bottom && (bottom.tri === 0 || bottom.tri === 1));
  near(bottom.point[2], 0, 'bottom z');
  assert.equal(centrePick([], 'top'), null);
});

test('fit aims a Z-up camera at the box and sees all of it', () => {
  const cam = new PerspectiveCamera(40, 1, 0.1, 1000);
  const box = boundsOf([cube()]);
  const target = fitCamera(cam, box);
  assert.deepEqual(target.toArray(), [100, 100, 10]);
  assert.deepEqual(cam.up.toArray(), [0, 0, 1]);
  assert.ok(cam.position.z > 10, 'camera above the centre');
  const corners = [box.min, box.max, new Vector3(90, 110, 20), new Vector3(110, 90, 0)];
  for (const c of corners) {
    const p = c.clone().project(cam);
    assert.ok(Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1 && p.z < 1, 'corner in view ' + c.toArray());
  }
  assert.ok(cam.near > 0 && cam.far > cam.near);
  const empty = fitCamera(cam, new Box3());
  assert.deepEqual(empty.toArray(), [0, 0, 0]);
});
