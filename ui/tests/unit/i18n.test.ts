// Locale resolution, the five message tables, insert labels and decimal input.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decimalSign, interpolate, LOCALES, normalizeLocale, parseInsertLabel, pastedDecimal, resolveLocale } from '../../src/core/i18n-core.ts';
import { en, ptBR } from '../../src/core/messages.ts';
import { es } from '../../src/core/messages-es.ts';
import { de } from '../../src/core/messages-de.ts';
import { zhCN } from '../../src/core/messages-zh.ts';

const TABLES = { 'pt-BR': ptBR, es, de, 'zh-CN': zhCN } as const;

test('locale resolution: explicit choice, host, browser, English', () => {
  assert.equal(normalizeLocale('pt_BR'), 'pt-BR');
  assert.equal(normalizeLocale('en-GB'), 'en');
  assert.equal(normalizeLocale('es'), 'es');
  assert.equal(normalizeLocale('es_MX'), 'es');
  assert.equal(normalizeLocale('de_AT'), 'de');
  assert.equal(normalizeLocale('zh_CN'), 'zh-CN');
  assert.equal(normalizeLocale('zh_TW'), 'zh-CN');
  assert.equal(normalizeLocale('zh-Hans-CN'), 'zh-CN');
  assert.equal(normalizeLocale('fr'), null);
  assert.equal(normalizeLocale(''), null);
  assert.equal(resolveLocale('pt-BR', 'en', ['en']), 'pt-BR');
  assert.equal(resolveLocale('zh-CN', 'de', ['en']), 'zh-CN');
  assert.equal(resolveLocale('auto', 'pt', ['en']), 'pt-BR');
  assert.equal(resolveLocale('auto', 'de', ['en']), 'de');
  assert.equal(resolveLocale('auto', 'ja', ['fr', 'es-ES']), 'es');
  assert.equal(resolveLocale('auto', null, ['fr']), 'en');
  assert.equal(interpolate('{a} and {b}', { a: 1 }), '1 and {b}');
  assert.deepEqual([...LOCALES], ['en', 'pt-BR', 'es', 'de', 'zh-CN']);
});

test('every language has every key, no empty text and the same placeholders; no sibling-plugin wording', () => {
  const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(',');
  for (const [lang, table] of Object.entries(TABLES)) {
    assert.deepEqual(Object.keys(table).sort(), Object.keys(en).sort(), `keys of ${lang}`);
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
  assert.deepEqual(LOCALES.map(decimalSign), ['.', ',', ',', ',', '.']);
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
