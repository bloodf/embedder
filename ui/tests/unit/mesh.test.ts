// Mesh transfer: base64 chunks pulled one at a time, assembled in order, checked against the announced sizes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assemble, decodeBase64, pullArray, pullPart, type ChunkReply } from '../../src/core/mesh.ts';
import { CUBE_IDX, CUBE_POS } from './cube.ts';

const b64 = (u: Uint8Array) => Buffer.from(u).toString('base64');

/** A fake plugin serving `arrays` in chunks of `size` bytes; it records every request. */
function server(arrays: Record<'pos' | 'idx', Uint8Array>, size: number) {
  const calls: string[] = [];
  let inFlight = 0;
  const fetch = async (kind: 'pos' | 'idx', i: number): Promise<ChunkReply> => {
    assert.equal(inFlight, 0, 'one request at a time');
    inFlight++;
    calls.push(`${kind}${i}`);
    await new Promise(r => setTimeout(r, 1));
    inFlight--;
    const data = arrays[kind];
    const chunks = Math.max(1, Math.ceil(data.length / size));
    return { i, chunks, bytes: data.length, data: b64(data.subarray(i * size, (i + 1) * size)) };
  };
  return { fetch, calls };
}

const bytes = (a: Float32Array | Uint32Array) => new Uint8Array(a.buffer, a.byteOffset, a.byteLength).slice();

test('base64 decodes to the original bytes', () => {
  assert.deepEqual([...decodeBase64(b64(new Uint8Array([0, 1, 254, 255])))], [0, 1, 254, 255]);
  assert.equal(decodeBase64('').length, 0);
});

test('assemble joins chunks in order and checks the total', () => {
  const buf = assemble([new Uint8Array([1, 2]), new Uint8Array([3])], 3);
  assert.deepEqual([...new Uint8Array(buf)], [1, 2, 3]);
  assert.throws(() => assemble([new Uint8Array([1])], 2), /expected 2/);
});

test('a part is pulled chunk by chunk, positions then indices', async () => {
  const { fetch, calls } = server({ pos: bytes(CUBE_POS), idx: bytes(CUBE_IDX) }, 40);
  let ticks = 0;
  const m = await pullPart(fetch, { part: 2, pos_bytes: CUBE_POS.byteLength, idx_bytes: CUBE_IDX.byteLength }, () => ticks++);
  assert.equal(m.part, 2);
  assert.deepEqual([...m.positions], [...CUBE_POS]);
  assert.deepEqual([...m.indices], [...CUBE_IDX]);
  assert.deepEqual(calls, ['pos0', 'pos1', 'pos2', 'idx0', 'idx1', 'idx2', 'idx3']);
  assert.equal(ticks, calls.length);
});

test('an empty array is one empty chunk', async () => {
  const { fetch, calls } = server({ pos: new Uint8Array(0), idx: new Uint8Array(0) }, 40);
  const buf = await pullArray(fetch, 'pos', 0);
  assert.equal(buf.byteLength, 0);
  assert.deepEqual(calls, ['pos0']);
});

test('size mismatches and bad indices are refused', async () => {
  const { fetch } = server({ pos: bytes(CUBE_POS), idx: bytes(CUBE_IDX) }, 4096);
  await assert.rejects(pullArray(fetch, 'pos', CUBE_POS.byteLength + 12), /does not match/);
  await assert.rejects(pullPart(fetch, { part: 0, pos_bytes: 10, idx_bytes: 12 }), /whole vertices/);
  const bad = server({ pos: bytes(CUBE_POS.subarray(0, 6)), idx: bytes(CUBE_IDX.subarray(0, 3)) }, 4096);
  await assert.rejects(pullPart(bad.fetch, { part: 0, pos_bytes: 24, idx_bytes: 12 }), /outside the vertex list/);
  const wrongIndex = async (kind: 'pos' | 'idx', i: number): Promise<ChunkReply> => ({ i: i + 1, chunks: 1, bytes: 0, data: '' });
  await assert.rejects(pullArray(wrongIndex, 'pos', 0), /does not match/);
});
