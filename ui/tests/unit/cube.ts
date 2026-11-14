// A 20 mm cube on the plate (x, y 90..110, z 0..20): 8 vertices, 12 outward-wound triangles.
export const CUBE_POS = new Float32Array([
  90, 90, 0, 110, 90, 0, 110, 110, 0, 90, 110, 0,
  90, 90, 20, 110, 90, 20, 110, 110, 20, 90, 110, 20,
]);
export const CUBE_IDX = new Uint32Array([
  0, 2, 1, 0, 3, 2,   // bottom (-Z)
  4, 5, 6, 4, 6, 7,   // top (+Z)
  0, 1, 5, 0, 5, 4,   // front (-Y)
  1, 2, 6, 1, 6, 5,   // right (+X)
  2, 3, 7, 2, 7, 6,   // back (+Y)
  3, 0, 4, 3, 4, 7,   // left (-X)
]);
