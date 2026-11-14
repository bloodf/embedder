// Mesh transfer (mesh.chunk): base64 chunks of little-endian Float32 xyz positions (plate frame, mm) and Uint32
// triangle indices. Pulled one request at a time, assembled in order and checked against the announced sizes.
export interface ChunkReply { i: number; chunks: number; bytes: number; data: string }
export type ChunkFetch = (kind: 'pos' | 'idx', i: number) => Promise<ChunkReply>;
export interface PartMesh { part: number; positions: Float32Array; indices: Uint32Array }

export function decodeBase64(text: string): Uint8Array {
  const bin = atob(text);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** The chunks joined in order; throws unless they add up to exactly `bytes`. */
export function assemble(chunks: readonly Uint8Array[], bytes: number): ArrayBuffer {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  if (total !== bytes) throw new Error(`mesh data is ${total} bytes, expected ${bytes}`);
  const out = new Uint8Array(bytes);
  chunks.reduce((at, c) => { out.set(c, at); return at + c.length; }, 0);
  return out.buffer;
}

/** One array, chunk after chunk; the first reply says how many chunks there are. */
export async function pullArray(fetch: ChunkFetch, kind: 'pos' | 'idx', bytes: number, onChunk?: () => void): Promise<ArrayBuffer> {
  const chunks: Uint8Array[] = [];
  let count = 1;
  for (let i = 0; i < count; i++) {
    const r = await fetch(kind, i);
    if (r.i !== i || r.bytes !== bytes) throw new Error(`mesh chunk ${kind} ${i} does not match the announced mesh`);
    count = r.chunks;
    chunks.push(decodeBase64(r.data));
    onChunk?.();
  }
  return assemble(chunks, bytes);
}

/** Positions and indices of one part, validated (whole triangles, indices inside the vertex list). */
export async function pullPart(fetch: ChunkFetch, part: { part: number; pos_bytes: number; idx_bytes: number }, onChunk?: () => void): Promise<PartMesh> {
  if (part.pos_bytes % 12 || part.idx_bytes % 12) throw new Error('mesh sizes are not whole vertices and triangles');
  // ponytail: native byte order; every WebView this runs in is little-endian, matching the plugin's data.
  const positions = new Float32Array(await pullArray(fetch, 'pos', part.pos_bytes, onChunk));
  const indices = new Uint32Array(await pullArray(fetch, 'idx', part.idx_bytes, onChunk));
  const vertices = positions.length / 3;
  for (const v of indices) if (v >= vertices) throw new Error('mesh index outside the vertex list');
  return { part: part.part, positions, indices };
}
