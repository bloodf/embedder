// The WebGL view: the selected object's parts, the plate grid, the staged pockets and the pocket in hand, which the
// pointer can drag over the surface. Renders on demand (camera moves, data changes), never in a loop. Throws when
// WebGL is not available.
import {
  AmbientLight, BufferAttribute, BufferGeometry, Color, DirectionalLight, DoubleSide, EdgesGeometry, GridHelper, LineBasicMaterial, LineSegments,
  Mesh, MeshStandardMaterial, PerspectiveCamera, Raycaster, Scene, Vector2, Vector3, WebGLRenderer, type Material, type Object3D,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { anchorOf, boundsOf, fitCamera, nearest, normalAt, nudge, partMesh, pick, slide, toNdc, toScreen, type Hit } from './pick';
import { gesture, IDLE, type Gesture, type Input, type Mark } from './gesture';
import type { PartMesh } from './mesh';

export interface Preview { positions: number[]; indices: number[] }
/** The pocket in hand: its last planned shape, the face that was planned on, and how the plan came out. */
export interface InHand { preview: Preview; base: Hit; tone: 'ok' | 'warn' | 'blocked' }
export interface StagedMark extends Preview { kind: 'magnet' | 'nfc'; key: number; base: Hit }
export interface SceneEvents {
  /** A click on a face; `onHand`: on the pocket in hand. */
  pick(hit: Hit, onHand: boolean): void;
  /** A click on a pocket of the list; null: a click on nothing at all. */
  select(key: number | null): void;
  dragStart(mark: Mark): void;
  dragMove(hit: Hit): void;
  dragEnd(cancelled: boolean): void;
}
export interface SceneApi {
  /** `refit: false` keeps the camera where it is (a repaint after the theme changed). */
  setParts(parts: PartMesh[], pickable: (part: number) => boolean, refit?: boolean): void;
  /** The pocket in hand (accent, outlined; amber with warnings, red when it cannot be made) and the staged ones, each
   *  in the colour of its kind of insert. All of them can be grabbed. */
  setPockets(inHand: InHand | null, staged: StagedMark[]): void;
  /** Slide the pocket in hand from where it was planned to `to`, as it is: Python has not planned it there yet. */
  pose(to: Hit | null): void;
  /** `hit` a step along its face in a direction of the screen; null where the surface ends. */
  nudge(hit: Hit, dx: number, dy: number, mm: number): Hit | null;
  /** Call a drag off (Escape). False when nothing was being dragged. */
  cancel(): boolean;
  fit(): void;
  dispose(): void;
}

const PART_MIX = 0.4;
const GRAB_PX = 12;   // a marker can be grabbed this far beside its middle, so a small pocket is not a tiny target
const css = (name: string, fallback: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

function disposeAll(objects: Object3D[]): void {
  for (const o of objects) {
    o.removeFromParent();
    o.traverse(c => {
      const drawn = c as Partial<Mesh>;
      drawn.geometry?.dispose();
      (drawn.material as Material | undefined)?.dispose();
    });
  }
}

function previewMesh(p: Preview, color: string, opacity: number): Mesh {
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(new Float32Array(p.positions), 3));
  g.setIndex(p.indices);
  g.computeVertexNormals();
  // drawn over the part (no depth test), so a pocket inside the body stays visible
  return new Mesh(g, new MeshStandardMaterial({ color, transparent: true, opacity, depthTest: false, side: DoubleSide }));
}

const sameHit = (a: Hit, b: Hit) => a.part === b.part && a.tri === b.tri && a.point.every((v, i) => v === b.point[i]);

export function createScene(host: HTMLElement, events: SceneEvents): SceneApi {
  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const canvas = renderer.domElement;
  host.appendChild(canvas);
  const scene = new Scene();
  scene.add(new AmbientLight(0xffffff, 1.2));
  const sun = new DirectionalLight(0xffffff, 1.6);
  sun.position.set(1, -2, 3);
  scene.add(sun);
  const camera = new PerspectiveCamera(40, 1, 0.1, 10_000);
  camera.up.set(0, 0, 1);   // Z up before the controls read it
  const controls = new OrbitControls(camera, canvas);
  let parts: Mesh[] = [];
  let targets: Mesh[] = [];
  let grid: GridHelper | null = null;
  // Every pocket drawn: what it is, its mesh and where it sits on its face (what the pointer grabs it by).
  let marks: { id: Mark; mesh: Mesh; at: Vector3 | null }[] = [];
  let inHand: { base: Hit; anchor: Vector3 | null; normal: Vector3 | null } | null = null;
  let frame = 0;

  const render = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; renderer.render(scene, camera); });
  };
  controls.addEventListener('change', render);

  const resize = () => {
    const w = host.clientWidth || 1, h = host.clientHeight || 1;
    renderer.setSize(w, h, false);
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(host);

  // ---- the pointer: orbit and click on the part, select and drag on a pocket (core/gesture.ts decides which)
  let state: Gesture = IDLE;
  let grab = { x: 0, y: 0 };   // from the grabbed pocket's middle to the pointer, so the pocket does not jump under it
  let pointer: { x: number; y: number; id: number } | null = null;
  let moveFrame = 0;

  const rect = () => canvas.getBoundingClientRect();
  const surface = (x: number, y: number) => pick(targets, toNdc(x, y, rect()), camera);
  const markAt = (x: number, y: number): Mark | null => {
    const ndc = toNdc(x, y, rect()), ray = new Raycaster();
    ray.setFromCamera(new Vector2(ndc.x, ndc.y), camera);
    const under = ray.intersectObjects(marks.map(m => m.mesh), false)[0];
    const k = under ? marks.findIndex(m => m.mesh === under.object) : nearest(marks.map(m => m.at), x, y, rect(), camera, GRAB_PX);
    return k < 0 ? null : marks[k].id;
  };
  /** One raycast per frame, however fast the pointer events come: the pocket follows a drag, the cursor shows a pocket
   *  that can be grabbed. ponytail: the drag tests every triangle of the part; add a BVH if huge parts drag slowly. */
  const dragTo = () => {
    const hit = pointer && surface(pointer.x - grab.x, pointer.y - grab.y);
    if (hit) events.dragMove(hit);   // off the part the pocket waits at the last spot on it
  };
  const flushMove = () => {
    moveFrame = 0;
    if (state.kind === 'drag') dragTo();
    else if (state.kind === 'idle' && pointer) host.toggleAttribute('data-over', markAt(pointer.x, pointer.y) != null);
  };
  const step = (input: Input) => {
    const from = state;
    const [next, effect] = gesture(state, input);
    state = next;
    const held = state.kind === 'drag' || (state.kind === 'press' && state.mark != null);
    controls.enabled = !held;   // the camera must not orbit under a pocket that is being pressed or dragged
    host.toggleAttribute('data-drag', state.kind === 'drag');
    if (effect === 'start' && state.kind === 'drag') events.dragStart(state.mark);
    if (effect === 'start' || effect === 'move') moveFrame ||= requestAnimationFrame(flushMove);
    if (effect === 'drop') {
      if (moveFrame) {   // the pocket is dropped where the pointer was released, not a frame behind
        cancelAnimationFrame(moveFrame);
        moveFrame = 0;
        dragTo();
      }
      events.dragEnd(false);
    }
    if (effect === 'cancel') events.dragEnd(true);
    if (effect === 'select' && from.kind === 'press' && typeof from.mark === 'number') events.select(from.mark);
    if (effect === 'click' && pointer) {
      const hit = surface(pointer.x, pointer.y);
      if (hit) events.pick(hit, from.kind === 'press' && from.mark === 'edit'); else events.select(null);
    }
  };
  const onDown = (e: PointerEvent) => {
    if (e.button !== 0 || !e.isPrimary || e.target !== canvas) return;
    if (state.kind === 'drag') step({ type: 'cancel' });   // its release never came (let go outside the window, uncaptured)
    host.focus({ preventScroll: true });
    pointer = { x: e.clientX, y: e.clientY, id: e.pointerId };
    const mark = markAt(e.clientX, e.clientY);
    const at = marks.find(m => m.id === mark)?.at;
    const drawn = at ? toScreen(at, rect(), camera) : pointer;
    grab = { x: e.clientX - drawn.x, y: e.clientY - drawn.y };
    step({ type: 'down', x: e.clientX, y: e.clientY, mark });
    if (mark != null) {
      try { canvas.setPointerCapture(e.pointerId); } catch { /* a pointer that cannot be captured still drags inside the window */ }
    }
  };
  const tracked = (e: PointerEvent) => state.kind !== 'idle' && pointer?.id === e.pointerId;
  const onMove = (e: PointerEvent) => {
    if (state.kind === 'idle') {
      if (e.target !== canvas) return;
      pointer = { x: e.clientX, y: e.clientY, id: e.pointerId };
      moveFrame ||= requestAnimationFrame(flushMove);
    } else if (tracked(e)) {
      pointer = { x: e.clientX, y: e.clientY, id: e.pointerId };
      step({ type: 'move', x: e.clientX, y: e.clientY });
    }
  };
  const onUp = (e: PointerEvent) => {
    if (!tracked(e)) return;
    pointer = { x: e.clientX, y: e.clientY, id: e.pointerId };
    step({ type: 'up', x: e.clientX, y: e.clientY });
  };
  const onCancel = (e: PointerEvent) => { if (tracked(e)) step({ type: 'cancel' }); };
  // In the capture phase on the host, so the camera controls on the canvas hear of a held pocket before they start.
  host.addEventListener('pointerdown', onDown, true);
  // On the window: a drag goes on when the pointer leaves the view, captured or not.
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onCancel);

  const fit = () => {
    controls.target.copy(fitCamera(camera, boundsOf(parts)));
    controls.update();
    render();
  };

  const pose = (to: Hit | null) => {
    const mark = marks.find(m => m.id === 'edit');
    if (!mark || !inHand) return;
    const normal = to && !sameHit(to, inHand.base) ? normalAt(targets, to) : null;
    const moved = to && normal && inHand.anchor && inHand.normal ? new Vector3(...to.point) : null;
    if (moved && normal && inHand.anchor && inHand.normal) mark.mesh.matrix.copy(slide(inHand.anchor, inHand.normal, moved, normal));
    else mark.mesh.matrix.identity();
    mark.mesh.updateMatrixWorld(true);
    mark.at = moved ?? inHand.anchor;
    render();
  };

  return {
    setParts(list, pickable, refit = true) {
      disposeAll([...parts, ...(grid ? [grid] : [])]);
      grid = null;
      // The part is a mid tone between the hairline and the control outline of the theme: it stands off the stage in
      // both themes and leaves the pockets (lighter in dark, darker in light) easy to see on it.
      const solid = new Color(css('--oui-border', '#b6cbd0')).lerp(new Color(css('--oui-control-border', '#4c737a')), PART_MIX);
      const ghost = css('--oui-warning', '#c08a00');
      parts = list.map(m => {
        const negative = !pickable(m.part);
        return partMesh(m, new MeshStandardMaterial({ color: negative ? new Color(ghost) : solid, flatShading: true,
          transparent: negative, opacity: negative ? 0.35 : 1, depthWrite: !negative }));
      });
      targets = parts.filter(m => pickable(m.userData.part as number));
      parts.forEach(m => scene.add(m));
      const box = boundsOf(parts);
      if (!box.isEmpty()) {
        const c = box.getCenter(new Vector3()), size = box.getSize(new Vector3());
        const span = Math.max(20, Math.ceil((Math.max(size.x, size.y) * 1.6) / 10) * 10);
        grid = new GridHelper(span, span / 10, css('--oui-border', '#888'), css('--oui-border', '#888'));
        grid.rotation.x = Math.PI / 2;   // GridHelper lies in XZ; the plate is XY
        grid.position.set(c.x, c.y, 0);
        scene.add(grid);
      }
      if (refit) fit(); else render();
    },
    setPockets(current, staged) {
      disposeAll(marks.map(m => m.mesh));
      const kind = { magnet: css('--em-magnet', '#8c4b08'), nfc: css('--em-nfc', '#6541a6') };
      const tone = { ok: css('--oui-primary', '#00675b'), warn: css('--oui-warning', '#c08a00'), blocked: css('--oui-danger', '#b3261e') };
      marks = staged.map(p => ({ id: p.key, mesh: previewMesh(p, kind[p.kind], 0.85), at: anchorOf(p.positions, targets, p.base) }));
      inHand = null;
      if (current) {
        const mesh = previewMesh(current.preview, tone[current.tone], 0.9);
        // The pocket in hand carries an outline, so it reads as the selected one by more than its colour.
        const outline = new LineSegments(new EdgesGeometry(mesh.geometry, 30), new LineBasicMaterial({ color: css('--oui-text', '#101010'), depthTest: false }));
        mesh.renderOrder = 1;
        outline.renderOrder = 2;
        mesh.add(outline);
        mesh.matrixAutoUpdate = false;
        inHand = { base: current.base, anchor: anchorOf(current.preview.positions, targets, current.base), normal: normalAt(targets, current.base) };
        marks.push({ id: 'edit', mesh, at: inHand.anchor });
      }
      marks.forEach(m => scene.add(m.mesh));
      render();
    },
    pose,
    nudge: (hit, dx, dy, mm) => nudge(targets, camera, hit, dx, dy, mm),
    cancel() {
      if (state.kind !== 'drag') return false;
      cancelAnimationFrame(moveFrame);
      moveFrame = 0;
      step({ type: 'cancel' });
      return true;
    },
    fit,
    dispose() {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(moveFrame);
      observer.disconnect();
      host.removeEventListener('pointerdown', onDown, true);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onCancel);
      controls.dispose();
      disposeAll([...parts, ...marks.map(m => m.mesh), ...(grid ? [grid] : [])]);
      renderer.forceContextLoss();   // free the GL context now; WebViews cap how many may live at once
      renderer.dispose();
      canvas.remove();
    },
  };
}
