// Picking math on three.js objects that work without WebGL (Raycaster, BufferGeometry, PerspectiveCamera), so it
// runs in unit tests and in the no-WebGL fallback. Plate frame, millimetres, Z up.
import { Box3, BufferAttribute, BufferGeometry, Mesh, MeshBasicMaterial, PerspectiveCamera, Raycaster, Vector2, Vector3, type Material } from 'three';
import type { PartMesh } from './mesh.ts';

export const CLICK_PX = 5;
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

/** Aim the camera (Z up) at the box from the front-right, far enough to see all of it. Returns the orbit target. */
export function fitCamera(camera: PerspectiveCamera, box: Box3): Vector3 {
  const target = box.isEmpty() ? new Vector3() : box.getCenter(new Vector3());
  const radius = box.isEmpty() ? 50 : Math.max(box.getSize(new Vector3()).length() / 2, 1);
  const dist = radius / Math.sin((camera.fov * Math.PI) / 360) * 1.15;
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(new Vector3(0.6, -1, 0.8).normalize().multiplyScalar(dist));
  camera.near = dist / 100;
  camera.far = dist * 100;
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return target;
}
