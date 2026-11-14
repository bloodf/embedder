// Locale resolution and the two message tables.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeLocale, resolveLocale, interpolate } from '../../src/core/i18n-core.ts';
import { en, ptBR } from '../../src/core/messages.ts';

test('locale resolution: explicit choice, host, browser, English', () => {
  assert.equal(normalizeLocale('pt_BR'), 'pt-BR');
  assert.equal(normalizeLocale('en-GB'), 'en');
  assert.equal(normalizeLocale('de'), null);
  assert.equal(resolveLocale('pt-BR', 'en', ['en']), 'pt-BR');
  assert.equal(resolveLocale('auto', 'pt', ['en']), 'pt-BR');
  assert.equal(resolveLocale('auto', null, ['de', 'pt-BR']), 'pt-BR');
  assert.equal(resolveLocale('auto', null, ['de']), 'en');
  assert.equal(interpolate('{a} and {b}', { a: 1 }), '1 and {b}');
});

test('both languages have the same keys and the same placeholders; no sibling-plugin wording', () => {
  assert.deepEqual(Object.keys(ptBR).sort(), Object.keys(en).sort());
  const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(',');
  for (const k of Object.keys(en) as (keyof typeof en)[]) {
    assert.equal(holes(ptBR[k]), holes(en[k]), `placeholders of ${k}`);
    assert.doesNotMatch(en[k] + ptBR[k], /Kobra|Anycubic|printer agent|Spoolman/i, `foreign wording in ${k}`);
  }
});
