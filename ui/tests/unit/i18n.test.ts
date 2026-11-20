// Locale resolution, the six message tables, Polish plurals, insert labels and decimal input.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decimalSign, interpolate, LOCALES, normalizeLocale, parseInsertLabel, pastedDecimal, pluralKey, resolveLocale } from '../../src/core/i18n-core.ts';
import { en, ptBR } from '../../src/core/messages.ts';
import { es } from '../../src/core/messages-es.ts';
import { de } from '../../src/core/messages-de.ts';
import { zhCN } from '../../src/core/messages-zh.ts';
import { pl } from '../../src/core/messages-pl.ts';

const TABLES = { 'pt-BR': ptBR, es, de, 'zh-CN': zhCN, pl } as const;

test('locale resolution: explicit choice, host, browser, English', () => {
  assert.equal(normalizeLocale('pt_BR'), 'pt-BR');
  assert.equal(normalizeLocale('en-GB'), 'en');
  assert.equal(normalizeLocale('es'), 'es');
  assert.equal(normalizeLocale('es_MX'), 'es');
  assert.equal(normalizeLocale('de_AT'), 'de');
  assert.equal(normalizeLocale('zh_CN'), 'zh-CN');
  assert.equal(normalizeLocale('zh_TW'), 'zh-CN');
  assert.equal(normalizeLocale('zh-Hans-CN'), 'zh-CN');
  for (const code of ['pl', 'pl_PL', 'pl-PL', 'PL', 'PL_pl']) assert.equal(normalizeLocale(code), 'pl', code);
  assert.equal(resolveLocale('auto', 'pl_PL', ['en']), 'pl');
  assert.equal(normalizeLocale('fr'), null);
  assert.equal(normalizeLocale(''), null);
  assert.equal(resolveLocale('pt-BR', 'en', ['en']), 'pt-BR');
  assert.equal(resolveLocale('zh-CN', 'de', ['en']), 'zh-CN');
  assert.equal(resolveLocale('auto', 'pt', ['en']), 'pt-BR');
  assert.equal(resolveLocale('auto', 'de', ['en']), 'de');
  assert.equal(resolveLocale('auto', 'ja', ['fr', 'es-ES']), 'es');
  assert.equal(resolveLocale('auto', null, ['fr']), 'en');
  assert.equal(interpolate('{a} and {b}', { a: 1 }), '1 and {b}');
  assert.deepEqual([...LOCALES], ['en', 'pt-BR', 'es', 'de', 'zh-CN', 'pl']);
});

test('every language has every key, no empty text and the same placeholders; no sibling-plugin wording', () => {
  const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(',');
  for (const [lang, table] of Object.entries(TABLES)) {
    // Polish adds a "_few" form to each plural pair, and nothing else.
    const extra = Object.keys(table).filter(k => !(k in en));
    assert.deepEqual(extra, lang === 'pl' ? Object.keys(en).filter(k => k.endsWith('_other')).map(k => k.replace(/_other$/, '_few')) : [], `extra keys of ${lang}`);
    for (const k of extra) assert.equal(holes((table as Record<string, string>)[k]), holes(en[k.replace(/_few$/, '_other') as keyof typeof en]), `placeholders of ${lang} ${k}`);
    assert.deepEqual(Object.keys(table).filter(k => k in en).sort(), Object.keys(en).sort(), `keys of ${lang}`);
    for (const k of Object.keys(en) as (keyof typeof en)[]) {
      assert.ok(table[k].trim(), `${lang} ${k} is empty`);
      assert.equal(holes(table[k]), holes(en[k]), `placeholders of ${lang} ${k}`);
      assert.doesNotMatch(en[k] + table[k], /Kobra|Anycubic|printer agent|Spoolman/i, `foreign wording in ${lang} ${k}`);
    }
  }
});

test('the translations are translated: no long English sentence is left in another language', () => {
  for (const [lang, table] of Object.entries(TABLES)) {
    const same = (Object.keys(en) as (keyof typeof en)[]).filter(k => !k.startsWith('lang.') && table[k] === en[k] && /\s\w+\s\w+/.test(en[k]));
    assert.deepEqual(same, [], `${lang} still in English`);
  }
});

test('Chinese uses full-width punctuation around its words', () => {
  for (const [k, v] of Object.entries(zhCN)) assert.doesNotMatch(v, /[一-鿿][,;:?!]|[一-鿿]\.(?!\d)/, `half-width punctuation in zh-CN ${k}`);
});

test('the English insert labels the plugin sends become the page messages; own names stay', () => {
  assert.deepEqual(parseInsertLabel('6x3 magnet'), { key: 'preset.disc', dims: { d: 6, t: 3 } });
  assert.deepEqual(parseInsertLabel('10x5x2 magnet'), { key: 'preset.block', dims: { l: 10, w: 5, t: 2 } });
  assert.deepEqual(parseInsertLabel('25 mm NFC sticker'), { key: 'preset.sticker', dims: { d: 25 } });
  assert.deepEqual(parseInsertLabel('30x2 NFC coin'), { key: 'preset.coin', dims: { d: 30, t: 2 } });
  assert.deepEqual(parseInsertLabel('NFC card'), { key: 'preset.card', dims: { l: 85.6, w: 54, t: 0.9 } });
  assert.deepEqual(parseInsertLabel('12.5x4 magnet'), { key: 'preset.disc', dims: { d: 12.5, t: 4 } });   // a custom size
  assert.deepEqual(parseInsertLabel('20x10x1.5 NFC'), { key: 'preset.block', dims: { l: 20, w: 10, t: 1.5 } });
  assert.deepEqual(parseInsertLabel('22x0.6 NFC'), { key: 'preset.coin', dims: { d: 22, t: 0.6 } });
  assert.equal(parseInsertLabel('Fridge magnets'), null);
  assert.equal(parseInsertLabel('6x3 magnet extra'), null);
});

test('decimal input: the locale sign, and "2.5" pasted means two and a half in every language', () => {
  assert.deepEqual(LOCALES.map(decimalSign), ['.', ',', ',', ',', '.', ',']);
  assert.equal(pastedDecimal('2.5', ','), '2,5');
  assert.equal(pastedDecimal('2,5', '.'), '2.5');
  assert.equal(pastedDecimal(' 2.5 mm ', ','), '2,5');
  assert.equal(pastedDecimal('12', ','), '12');
  assert.equal(pastedDecimal('-1.25', ','), '-1,25');
  assert.equal(pastedDecimal('abc', ','), null);
  assert.equal(pastedDecimal('1.2.3', ','), null);
  assert.equal(pastedDecimal('2．5', '.'), '2.5');
  assert.equal(pastedDecimal('2，5', ','), '2,5');
});

test('Polish plurals: one, few and many (1, 2, 5, 12, 22); other languages keep one and other', () => {
  const say = (lang: string, table: Record<string, string>, base: string, n: number) =>
    interpolate(table[pluralKey(lang, base, n, k => k in table)], { n, removed: 0, size: '1 MB' });
  const ns = [1, 2, 5, 12, 22];
  assert.deepEqual(ns.map(n => say('pl', pl, 'load.objects', n)), ['1 obiekt', '2 obiekty', '5 obiektów', '12 obiektów', '22 obiekty']);
  assert.deepEqual(ns.map(n => say('pl', pl, 'copies.status', n)), [
    '1 starą kopię można usunąć (1 MB).', '2 stare kopie można usunąć (1 MB).', '5 starych kopii można usunąć (1 MB).',
    '12 starych kopii można usunąć (1 MB).', '22 stare kopie można usunąć (1 MB).']);
  assert.equal(say('pl', pl, 'list.summary', 0), '0 kieszeni do dodania, do usunięcia: 0. Zapisuje nową kopię.');
  assert.equal(say('pl', pl, 'result.pruned', 104), '104 starsze kopie zostały usunięte z folderu wtyczki.');
  assert.deepEqual(ns.map(n => say('en', en, 'load.objects', n)), ['1 object', '2 objects', '5 objects', '12 objects', '22 objects']);
});

test('the Apply result and the copy counts agree with their number in every language', () => {
  const say = (lang: string, table: Record<string, string>, base: string, n: number) =>
    interpolate(table[pluralKey(lang, base, n, k => k in table)], { n, size: '1 MB' });
  const body = (lang: string, table: Record<string, string>, added: number, removed: number) =>
    interpolate(table['result.body'], { name: 'a.3mf', added: say(lang, table, 'result.added', added), removed: say(lang, table, 'result.removed', removed) });
  const all = { en, ...TABLES } as Record<string, Record<string, string>>;
  // Portuguese counts 0 as one (CLDR), hence "0 removido".
  assert.deepEqual(Object.entries(all).map(([lang, table]) => body(lang, table, 1, 0)), [
    'a.3mf: 1 pocket added, 0 removed.', 'a.3mf: 1 bolso adicionado, 0 removido.', 'a.3mf: 1 alojamiento añadido, 0 quitados.',
    'a.3mf: 1 Tasche hinzugefügt, 0 entfernt.', 'a.3mf：添加了 1 个凹槽，移除了 0 个。', 'a.3mf: dodano 1 kieszeń, usunięto 0.']);
  assert.deepEqual(Object.entries(all).map(([lang, table]) => body(lang, table, 2, 1)), [
    'a.3mf: 2 pockets added, 1 removed.', 'a.3mf: 2 bolsos adicionados, 1 removido.', 'a.3mf: 2 alojamientos añadidos, 1 quitado.',
    'a.3mf: 2 Taschen hinzugefügt, 1 entfernt.', 'a.3mf：添加了 2 个凹槽，移除了 1 个。', 'a.3mf: dodano 2 kieszenie, usunięto 1.']);
  assert.equal(say('pl', pl, 'result.added', 5), 'dodano 5 kieszeni');
  assert.deepEqual(['copies.cleared', 'copies.failed', 'copies.clearText'].map(k => say('en', en, k, 1)), [
    'Deleted 1 old copy, 1 MB freed.', '1 copy could not be deleted; it may be open in another program.',
    '1 old project copy (1 MB) will be deleted from the plugin folder. Copies OrcaSlicer may have open are kept.']);
  assert.equal(say('pt-BR', ptBR, 'copies.cleared', 1), '1 cópia antiga apagada, 1 MB liberados.');
  // A count goes through a plural message, never straight into one fixed sentence.
  for (const k of Object.keys(en)) if (/\{(n|pockets)\}/.test(en[k as keyof typeof en]) && !/_(one|other)$/.test(k))
    assert.ok(['obj.instance', 'pause.item', 'err.pocketN'].includes(k), `${k} takes a count without a plural form`);
});
