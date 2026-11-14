import { WebGLRenderer } from 'three';

/** Whether three.js can open a WebGL context here; the renderer is created only to find out, then freed. */
export function probeWebGL(): boolean {
  try {
    const renderer = new WebGLRenderer({ antialias: false });
    renderer.forceContextLoss();
    renderer.dispose();
    return true;
  } catch {
    return false;
  }
}
