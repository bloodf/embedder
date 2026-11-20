// Picking math on three.js objects that work without WebGL (Raycaster, BufferGeometry, PerspectiveCamera), so it
// runs in unit tests and in the no-WebGL fallback. Plate frame, millimetres, Z up.
import { Box3, BufferAttribute, BufferGeometry, Matrix4, Mesh, MeshBasicMaterial, PerspectiveCamera, Plane, Quaternion, Raycaster, Triangle, Vector2, Vector3, type Material } from 'three';
import type { PartMesh } from './mesh.ts';

export const CLICK_PX = 5;
const STEP_REACH = 0.5;   // mm above and below the face that an arrow-key step still finds the surface, at least
export interface Hit { part: number; tri: number; point: [number, number, number] }
interface Rect { left: number; top: number; width: number; height: number }

export function geometryOf(m: { positions: Float32Array; indices: Uint32Array }): BufferGeometry {
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(m.positions, 3));
  g.setIndex(new BufferAttribute(m.indices, 1));
  g.computeVertexNormals();
  g.computeBoundingBox();
  g.computeBoundingSphere();
  return g;
}

/** A pickable mesh for one part; `material` defaults to an invisible front-side one (fallback picking). */
export function partMesh(m: PartMesh, material: Material = new MeshBasicMaterial()): Mesh {
  const mesh = new Mesh(geometryOf(m), material);
  mesh.userData.part = m.part;
  mesh.updateMatrixWorld();
  return mesh;
}

export function toNdc(x: number, y: number, rect: Rect): { x: number; y: number } {
  return { x: ((x - rect.left) / rect.width) * 2 - 1, y: -((y - rect.top) / rect.height) * 2 + 1 };
}

/** A pointer that moved less than `px` between down and up is a click; more is an orbit drag. */
export function isClick(down: { x: number; y: number }, up: { x: number; y: number }, px = CLICK_PX): boolean {
  return Math.hypot(up.x - down.x, up.y - down.y) < px;
}

function first(hits: ReturnType<Raycaster['intersectObjects']>): Hit | null {
  const h = hits.find(x => x.faceIndex != null);
  if (!h) return null;
  return { part: h.object.userData.part as number, tri: h.faceIndex as number, point: [h.point.x, h.point.y, h.point.z] };
}

export function pick(targets: Mesh[], ndc: { x: number; y: number }, camera: PerspectiveCamera): Hit | null {
  const ray = new Raycaster();
  ray.setFromCamera(new Vector2(ndc.x, ndc.y), camera);
  return first(ray.intersectObjects(targets, false));
}

/** Where a point of the plate is drawn, in the pixels of the pointer events. */
export function toScreen(point: Vector3, rect: Rect, camera: PerspectiveCamera): { x: number; y: number } {
  const p = point.clone().project(camera);
  return { x: rect.left + ((p.x + 1) / 2) * rect.width, y: rect.top + ((1 - p.y) / 2) * rect.height };
}

/** Which of the points is drawn nearest the pointer, within `px` of it; -1 when none is. A small pocket is a small
 *  target: its marker can be grabbed a little beside it too. */
export function nearest(points: (Vector3 | null)[], x: number, y: number, rect: Rect, camera: PerspectiveCamera, px: number): number {
  let best = -1, reach = px;
  points.forEach((p, k) => {
    if (!p) return;
    const s = toScreen(p, rect, camera), d = Math.hypot(s.x - x, s.y - y);
    if (d <= reach) { best = k; reach = d; }
  });
  return best;
}

function triangleAt(targets: Mesh[], hit: Hit): Triangle | null {
  const g = targets.find(m => m.userData.part === hit.part)?.geometry;
  const index = g?.index, pos = g?.getAttribute('position');
  if (!index || !pos || hit.tri < 0 || hit.tri * 3 + 2 >= index.count) return null;
  const corner = (c: number) => new Vector3().fromBufferAttribute(pos, index.getX(hit.tri * 3 + c));
  return new Triangle(corner(0), corner(1), corner(2));
}

/** The outward normal of the face that was hit (the parts are in the plate frame); null for a face the parts do not have. */
export function normalAt(targets: Mesh[], hit: Hit): Vector3 | null {
  const n = triangleAt(targets, hit)?.getNormal(new Vector3());
  return n && n.lengthSq() > 0 ? n : null;
}

/** Where a pocket preview sits on its face: the middle of its bounding box, brought onto the face along the normal.
 *  It lets the page slide a preview without knowing how Python placed it (centred on the face, sunk under a cover,
 *  behind a wall): Python stays the source of the geometry, the page only moves what it drew. */
export function anchorOf(positions: ArrayLike<number>, targets: Mesh[], hit: Hit): Vector3 | null {
  const tri = triangleAt(targets, hit), n = normalAt(targets, hit);
  if (!tri || !n) return null;
  const mid = new Box3().setFromArray(positions as number[]).getCenter(new Vector3());
  return new Plane().setFromNormalAndCoplanarPoint(n, tri.a).projectPoint(mid, new Vector3());
}

/** The move that takes a preview from the face it was planned on to another spot: turned from one normal to the other,
 *  its anchor brought to the new point. */
export function slide(anchor: Vector3, from: Vector3, to: Vector3, normal: Vector3): Matrix4 {
  const turn = new Quaternion().setFromUnitVectors(from, normal);
  return new Matrix4().makeRotationFromQuaternion(turn).setPosition(to.clone().sub(anchor.clone().applyQuaternion(turn)));
}

/** The hit `mm` further along its face, in a direction of the screen (dx to the right, dy up, as the camera shows it);
 *  null where the surface ends. */
export function nudge(targets: Mesh[], camera: PerspectiveCamera, hit: Hit, dx: number, dy: number, mm: number): Hit | null {
  const n = normalAt(targets, hit);
  if (!n) return null;
  const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0), up = new Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const along = right.multiplyScalar(dx).add(up.multiplyScalar(dy)).projectOnPlane(n);
  if (along.lengthSq() < 1e-9) return null;   // the camera looks along the face: the arrow has no direction on it
  // A curved part bends away from the face's plane as far as the step goes: the reach grows with it.
  const reach = Math.max(STEP_REACH, mm);
  const above = new Vector3(...hit.point).addScaledVector(along.normalize(), mm).addScaledVector(n, reach);
  return first(new Raycaster(above, n.clone().negate(), 0, 2 * reach).intersectObjects(targets, false));
}

export function boundsOf(targets: Mesh[]): Box3 {
  return targets.reduce((box, m) => box.expandByObject(m), new Box3());
}

/** The face straight above ('top') or below ('bottom') the centre of the parts' bounding box. */
export function centrePick(targets: Mesh[], face: 'top' | 'bottom'): Hit | null {
  const box = boundsOf(targets);
  if (box.isEmpty()) return null;
  const c = box.getCenter(new Vector3());
  const z = face === 'top' ? box.max.z + 1 : box.min.z - 1;
  const ray = new Raycaster(new Vector3(c.x, c.y, z), new Vector3(0, 0, face === 'top' ? -1 : 1));
  return first(ray.intersectObjects(targets, false));
}

/** Aim the camera (Z up) at the box from the front-right, far enough to see all of it across both the view's height
 *  and its width. Returns the orbit target. */
export function fitCamera(camera: PerspectiveCamera, box: Box3): Vector3 {
  const target = box.isEmpty() ? new Vector3() : box.getCenter(new Vector3());
  const radius = box.isEmpty() ? 50 : Math.max(box.getSize(new Vector3()).length() / 2, 1);
  // camera.fov is vertical; the horizontal half-angle comes from the aspect. The narrower of the two decides.
  const half = Math.atan(Math.tan((camera.fov * Math.PI) / 360) * Math.min(1, camera.aspect));
  const dist = radius / Math.sin(half) * 1.15;
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(new Vector3(0.6, -1, 0.8).normalize().multiplyScalar(dist));
  camera.near = dist / 100;
  camera.far = dist * 100;
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return target;
}
