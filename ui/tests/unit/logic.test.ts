// Pure Embed-panel rules: plan arguments, the Embedded block reason, pause summary, preset groups, staging.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { defaultPocketShape, embeddedBlock, groupPresets, POCKET_SHAPES, rememberedShape, insertsNeeded, pauseSummary, planArgs, previewsFor, sizeOf, splitLead, stage, toggle, unstage } from '../../src/app/logic.ts';
import type { ObjectInfo, Plan, Preset, Staged } from '../../src/app/types.ts';

const hit = { part: 1, tri: 7, point: [1, 2, 3] as [number, number, number] };

test('plan arguments name the hit, the insert and only the options that are set', () => {
  assert.deepEqual(planArgs(0, hit, { preset: 'magnet-disc-6x3', custom: null }, { mode: 'embedded', spin: null, cover: null }),
    { object: 0, part: 1, tri: 7, point: [1, 2, 3], mode: 'embedded', preset: 'magnet-disc-6x3' });
  assert.deepEqual(planArgs(2, hit, { preset: 'x', custom: { kind: 'nfc', shape: 'block', d: 1, l: 30, w: 20, t: 1 } }, { mode: 'open', spin: 45, cover: 0 }),
    { object: 2, part: 1, tri: 7, point: [1, 2, 3], mode: 'open', custom: { kind: 'nfc', shape: 'block', l: 30, w: 20, t: 1 }, spin: 45, cover: 0 });
  assert.deepEqual(planArgs(0, hit, { preset: null, custom: { kind: 'magnet', shape: 'disc', d: 8, l: 1, w: 1, t: 2 } }, { mode: 'open', spin: 0, cover: null })?.custom,
    { kind: 'magnet', shape: 'disc', d: 8, t: 2 });
  assert.equal(planArgs(0, hit, { preset: null, custom: null }, { mode: 'open', spin: null, cover: null }), null);
  assert.equal(planArgs(0, hit, { preset: 'x', custom: null }, { mode: 'open', spin: null, cover: null, center: true })?.center, true);
  assert.equal('center' in (planArgs(0, hit, { preset: 'x', custom: null }, { mode: 'open', spin: null, cover: null, center: false }) ?? {}), false);
});

test('the pocket shape: the insert\'s own unless picked, a pick sent as pocket_shape and kept per preset', () => {
  assert.equal(defaultPocketShape('disc'), 'hexagon');
  assert.equal(defaultPocketShape('block'), 'rectangle');
  assert.deepEqual([...POCKET_SHAPES], ['circle', 'hexagon', 'square', 'rectangle']);
  const insert = { preset: 'magnet-disc-6x3', custom: null };
  assert.equal(planArgs(0, hit, insert, { mode: 'open', spin: null, cover: null, pocketShape: 'circle' })?.pocket_shape, 'circle');
  assert.equal('pocket_shape' in (planArgs(0, hit, insert, { mode: 'open', spin: null, cover: null, pocketShape: null }) ?? {}), false);
  const saved = { 'magnet-disc-6x3': 'square', odd: 'oval' } as Record<string, 'square'>;
  assert.equal(rememberedShape(saved, 'magnet-disc-6x3'), 'square');
  assert.equal(rememberedShape(saved, 'odd'), null, 'a value the page does not know is the default');
  assert.equal(rememberedShape(saved, 'other'), null);
  assert.equal(rememberedShape(undefined, 'magnet-disc-6x3'), null);
  assert.equal(rememberedShape(saved, null), null, 'a custom size has no preset to remember by');
});

test('Embedded is blocked by the object first, then by an embedded plan', () => {
  const obj = { embedded_block: 'raft' } as ObjectInfo;
  const plan = (mode: 'open' | 'embedded', code: string | null) => ({ mode, blocked: code ? { code, detail: '' } : null, preview: null }) as Plan;
  assert.equal(embeddedBlock(obj, plan('embedded', 'tilted_face')), 'raft');
  assert.equal(embeddedBlock({ embedded_block: null } as ObjectInfo, plan('embedded', 'tilted_face')), 'tilted_face');
  assert.equal(embeddedBlock(null, plan('open', 'bad_mode')), null);
  assert.equal(embeddedBlock(null, null), null);
});

const staged = (key: number, z: number | null, label: string, mode: 'open' | 'embedded' = 'embedded'): Staged =>
  ({ key, args: {} as Staged['args'], plan: { mode, pause_z: z, label, blocked: null, preview: null } });

test('pauses group embedded pockets by height, lowest first', () => {
  const list = [staged(1, 5.4, '6x3 magnet'), staged(2, 2.2, 'NFC'), staged(3, 5.4000001, '6x3 magnet'), staged(4, 5.4, '8x2 magnet'), staged(5, null, 'x', 'open')];
  assert.deepEqual(pauseSummary(list), [
    { z: 2.2, items: [{ label: 'NFC', n: 1 }] },
    { z: 5.4, items: [{ label: '6x3 magnet', n: 2 }, { label: '8x2 magnet', n: 1 }] },
  ]);
  assert.deepEqual(pauseSummary([]), []);
});

test('a pocket on an object with copies counts once per copy', () => {
  const two: Staged = { key: 1, args: {} as Staged['args'], plan: { mode: 'embedded', pause_z: 5.4, label: '6x3 magnet', copies: 2, blocked: null, preview: null } };
  assert.deepEqual(pauseSummary([two, staged(2, 5.4, '6x3 magnet')]), [{ z: 5.4, items: [{ label: '6x3 magnet', n: 3 }] }]);
});

test('the viewer shows only the selected object\'s staged pockets', () => {
  const preview = { positions: [0, 0, 0], indices: [0, 0, 0] };
  const at = (key: number, object: number, withPreview = true): Staged =>
    ({ key, args: { object } as Staged['args'], plan: { mode: 'open', blocked: null, preview: withPreview ? preview : null } });
  assert.equal(previewsFor([at(1, 0), at(2, 1), at(3, 0, false)], 0).length, 1);
  assert.equal(previewsFor([at(1, 0)], null).length, 0);
  const nfc = at(4, 0);
  nfc.plan.kind = 'nfc';
  assert.deepEqual(previewsFor([at(1, 0), nfc], 0).map(p => p.kind), ['magnet', 'nfc'], 'each preview carries the kind that colours it');
});

test('the object size is the bounding box of its meshes; nothing to measure is null, never 0', () => {
  const a = { positions: new Float32Array([90, 90, 0, 150, 130, 8]) }, b = { positions: new Float32Array([100, 80, 2]) };
  assert.deepEqual(sizeOf([a, b]), [60, 50, 8]);
  assert.equal(sizeOf([]), null);
  assert.equal(sizeOf([{ positions: new Float32Array(0) }]), null);
});

test('a message splits after its first sentence or colon; decimals and a lone sentence stay whole', () => {
  assert.deepEqual(splitLead('Placing the pocket failed: The project was loaded again. Load it once more'), ['Placing the pocket failed:', 'The project was loaded again. Load it once more']);
  assert.deepEqual(splitLead('No pockets yet. Place one and press Add pocket.'), ['No pockets yet.', 'Place one and press Add pocket.']);
  assert.deepEqual(splitLead('Z 7.20 mm: insert 2 × 6x3 magnet'), ['Z 7.20 mm:', 'insert 2 × 6x3 magnet']);
  assert.deepEqual(splitLead('Settings saved.'), ['Settings saved.', '']);
  assert.deepEqual(splitLead('Deleted 2 old copies, 2.0 MB freed.'), ['Deleted 2 old copies, 2.0 MB freed.', '']);
  assert.deepEqual(splitLead('还没有凹槽。放置一个，然后点击“添加凹槽”。'), ['还没有凹槽。', '放置一个，然后点击“添加凹槽”。']);
  assert.deepEqual(splitLead('Z 7.2 mm：放入 2 × 圆片 Ø6 × 3 mm'), ['Z 7.2 mm：', '放入 2 × 圆片 Ø6 × 3 mm']);
  assert.deepEqual(splitLead('设置已保存。'), ['设置已保存。', '']);
});

test('presets group into magnets, NFC and mine; empty groups drop', () => {
  const p = (id: string, kind: 'magnet' | 'nfc', builtin = true) => ({ id, name: id, kind, shape: 'disc', d: 1, t: 1, builtin }) as Preset;
  const groups = groupPresets([p('m', 'magnet'), p('n', 'nfc')], [p('user-1', 'nfc', false)]);
  assert.deepEqual(groups.map(g => [g.key, g.items.map(i => i.id)]), [['magnet', ['m']], ['nfc', ['n']], ['mine', ['user-1']]]);
  assert.deepEqual(groupPresets([p('m', 'magnet')], []).map(g => g.key), ['magnet']);
});

test('staging and removal lists never mutate their input', () => {
  const a = Object.freeze([] as Staged[]);
  const b = stage(a, {} as Staged['args'], { mode: 'open', blocked: null, preview: null });
  const c = stage(b, {} as Staged['args'], { mode: 'open', blocked: null, preview: null });
  assert.deepEqual(c.map(x => x.key), [1, 2]);
  assert.deepEqual(unstage(Object.freeze(c), 1).map(x => x.key), [2]);
  assert.deepEqual(stage(unstage(c, 1), {} as Staged['args'], { mode: 'open', blocked: null, preview: null }).map(x => x.key), [2, 3]);
  const ids = Object.freeze(['a']);
  assert.deepEqual(toggle(ids, 'b', true), ['a', 'b']);
  assert.deepEqual(toggle(ids, 'a', false), []);
  assert.deepEqual(toggle(ids, 'a', true), ['a']);
});

test('the inserts to have ready count every pocket, open ones too, once per copy, by kind then label', () => {
  const list = [staged(1, 5.4, '6x3 magnet'), staged(2, null, '25 mm NFC sticker', 'open'), staged(3, null, '6x3 magnet', 'open'),
    { ...staged(4, 2.2, '8x2 magnet'), plan: { ...staged(4, 2.2, '8x2 magnet').plan, copies: 3 } }];
  list[1].plan.kind = 'nfc';
  assert.deepEqual(insertsNeeded(list), [
    { label: '6x3 magnet', kind: 'magnet', n: 2 }, { label: '8x2 magnet', kind: 'magnet', n: 3 }, { label: '25 mm NFC sticker', kind: 'nfc', n: 1 }]);
  assert.deepEqual(insertsNeeded([]), []);
});
