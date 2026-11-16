import { computed, ref } from 'vue';
import { en, ptBR, type MessageKey } from './messages';
import { es } from './messages-es';
import { de } from './messages-de';
import { zhCN } from './messages-zh';
import { interpolate, isLocale, parseInsertLabel, resolveLocale, type LangPref, type Locale } from './i18n-core';
import { boot } from './boot';

const PREF_KEY = 'embedder.lang';
const dicts: Record<Locale, Record<MessageKey, string>> = { en, 'pt-BR': ptBR, es, de, 'zh-CN': zhCN };

// The explicit choice lives in the plugin's settings (boot "pref"); localStorage is only a fallback cache.
let persist: (value: LangPref) => void = () => {};
export function onLangPref(fn: (value: LangPref) => void): void { persist = fn; }
function readPref(): LangPref {
  const fromHost = (boot as { pref?: unknown }).pref;
  if (isLocale(fromHost) || fromHost === 'auto') return fromHost;
  try {
    const v = localStorage.getItem(PREF_KEY);
    return isLocale(v) ? v : 'auto';
  } catch { return 'auto'; }
}

export const langPref = ref<LangPref>(readPref());
const hostLang = ref<unknown>(null);
export const locale = computed<Locale>(() => resolveLocale(langPref.value, hostLang.value, navigator.languages ?? [navigator.language]));
export const autoLocale = computed<Locale>(() => resolveLocale('auto', hostLang.value, navigator.languages ?? [navigator.language]));

export function setHostLanguage(value: unknown): void { hostLang.value = value; }
export function setLangPref(value: LangPref): void {
  langPref.value = value;
  persist(value);
  try { if (value === 'auto') localStorage.removeItem(PREF_KEY); else localStorage.setItem(PREF_KEY, value); } catch { /* per-viewer only */ }
}

export function t(key: MessageKey, params?: Record<string, unknown>): string {
  return interpolate(dicts[locale.value][key] ?? en[key] ?? key, params);
}
/** Plural keys come in pairs "<base>_one" / "<base>_other". */
export function tn(base: string, n: number, params?: Record<string, unknown>): string {
  const key = (new Intl.PluralRules(locale.value).select(n) === 'one' ? `${base}_one` : `${base}_other`) as MessageKey;
  return t(key, { n, ...params });
}
/** A message key when it exists (state names, codes from Python); otherwise the raw value. */
export function tMaybe(key: string, fallback: string, params?: Record<string, unknown>): string {
  return key in en ? t(key as MessageKey, params) : fallback;
}

export const fmt = {
  number: (v: number, digits = 0) => new Intl.NumberFormat(locale.value, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(v),
  time: (unix: number) => new Intl.DateTimeFormat(locale.value, { timeStyle: 'short' }).format(new Date(unix * 1000)),
};

/** "6x3 magnet" as the page language writes it ("Ø6 × 3 mm disc"); the user's own preset names stay as typed. */
export function insertLabel(label: string | undefined): string {
  if (label == null) return '?';
  const parsed = parseInsertLabel(label);
  if (!parsed) return label;
  const nf = new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 });
  const dims = Object.fromEntries(Object.entries(parsed.dims).map(([k, v]) => [k, nf.format(v)]));
  return t(parsed.key, dims);
}
