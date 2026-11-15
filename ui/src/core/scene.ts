// The WebGL view: the selected object's parts, the plate grid, the staged pockets and the current preview.
// Renders on demand (camera moves, data changes), never in a loop. Throws when WebGL is not available.
import {
  AmbientLight, BufferAttribute, BufferGeometry, Color, DirectionalLight, DoubleSide, GridHelper, Mesh, MeshStandardMaterial,
  PerspectiveCamera, Scene, Vector3, WebGLRenderer, type Material, type Object3D,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { boundsOf, fitCamera, isClick, partMesh, pick, toNdc, type Hit } from './pick';
import type { PartMesh } from './mesh';

export interface Preview { positions: number[]; indices: number[] }
export interface SceneApi {
  /** `refit: false` keeps the camera where it is (a repaint after the theme changed). */
  setParts(parts: PartMesh[], pickable: (part: number) => boolean, refit?: boolean): void;
  /** The pocket being placed (accent) and the staged ones, each in the colour of its kind of insert. */
  setPockets(current: Preview | null, staged: (Preview & { kind: 'magnet' | 'nfc' })[]): void;
  fit(): void;
  dispose(): void;
}

const PART_MIX = 0.4;
const css = (name: string, fallback: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

function disposeAll(objects: Object3D[]): void {
  for (const o of objects) {
    o.removeFromParent();
    if (o instanceof GridHelper) o.dispose();
    else if (o instanceof Mesh) { o.geometry.dispose(); (o.material as Material).dispose(); }
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

export function createScene(host: HTMLElement, onPick: (hit: Hit) => void): SceneApi {
  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  host.appendChild(renderer.domElement);
  const scene = new Scene();
  scene.add(new AmbientLight(0xffffff, 1.2));
  const sun = new DirectionalLight(0xffffff, 1.6);
  sun.position.set(1, -2, 3);
  scene.add(sun);
  const camera = new PerspectiveCamera(40, 1, 0.1, 10_000);
  camera.up.set(0, 0, 1);   // Z up before the controls read it
  const controls = new OrbitControls(camera, renderer.domElement);
  let parts: Mesh[] = [];
  let targets: Mesh[] = [];
  let pockets: Mesh[] = [];
  let grid: GridHelper | null = null;
  let frame = 0;

  const render = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; renderer.render(scene, camera); });
  };
  controls.addEventListener('change', render);

  const resize = () => {
    const w = host.clientWidth || 1, h = host.clientHeight || 1;
    renderer.setSize(w, h, false);
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(host);

  let down: { x: number; y: number } | null = null;
  const onDown = (e: PointerEvent) => { if (e.button === 0) down = { x: e.clientX, y: e.clientY }; };
  const onUp = (e: PointerEvent) => {
    const start = down;
    down = null;
    if (!start || e.button !== 0 || !isClick(start, { x: e.clientX, y: e.clientY })) return;
    const hit = pick(targets, toNdc(e.clientX, e.clientY, renderer.domElement.getBoundingClientRect()), camera);
    if (hit) onPick(hit);
  };
  renderer.domElement.addEventListener('pointerdown', onDown);
  renderer.domElement.addEventListener('pointerup', onUp);

  const fit = () => {
    controls.target.copy(fitCamera(camera, boundsOf(parts)));
    controls.update();
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
      disposeAll(pockets);
      const kind = { magnet: css('--em-magnet', '#8c4b08'), nfc: css('--em-nfc', '#6541a6') };
      pockets = [...staged.map(p => previewMesh(p, kind[p.kind], 0.85)), ...(current ? [previewMesh(current, css('--oui-primary', '#00675b'), 0.9)] : [])];
      pockets.forEach(m => scene.add(m));
      render();
    },
    fit,
    dispose() {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onDown);
      renderer.domElement.removeEventListener('pointerup', onUp);
      controls.dispose();
      disposeAll([...parts, ...pockets, ...(grid ? [grid] : [])]);
      renderer.forceContextLoss();   // free the GL context now; WebViews cap how many may live at once
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
