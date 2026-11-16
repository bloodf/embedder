// Locale resolution, kept free of Vue so the unit tests can import it directly.
export const LOCALES = ['en', 'pt-BR', 'es', 'de', 'zh-CN'] as const;
export type Locale = typeof LOCALES[number];
export type LangPref = 'auto' | Locale;
export const isLocale = (value: unknown): value is Locale => (LOCALES as readonly unknown[]).includes(value);

// By primary subtag: OrcaSlicer reports "pt_BR", "es", "de", "zh_CN" or "zh_TW"; browsers "es-MX", "de-AT", "zh-Hans-CN".
// Traditional Chinese takes the Simplified page: closer to its reader than English.
const BY_LANGUAGE: Record<string, Locale> = { en: 'en', pt: 'pt-BR', es: 'es', de: 'de', zh: 'zh-CN' };

/** "pt_BR", "pt" → "pt-BR"; "es_ES" → "es"; "de-AT" → "de"; "zh_CN", "zh_TW" → "zh-CN"; any English → "en"; anything else → null. */
export function normalizeLocale(value: unknown): Locale | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  return BY_LANGUAGE[value.trim().toLowerCase().split(/[-_]/)[0]] ?? null;
}

/** Explicit choice first, then the host's language, then the browser's, then English. */
export function resolveLocale(pref: LangPref, host: unknown, browser: readonly string[]): Locale {
  if (isLocale(pref)) return pref;
  return normalizeLocale(host) ?? browser.map(normalizeLocale).find((l): l is Locale => !!l) ?? 'en';
}

export function interpolate(text: string, params?: Record<string, unknown>): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (_, k: string) => (k in params ? String(params[k]) : `{${k}}`));
}

export type InsertLabelKey = 'preset.disc' | 'preset.block' | 'preset.sticker' | 'preset.coin' | 'preset.card';
const NUM = String.raw`(\d+(?:\.\d+)?)`;
const LABELS: [RegExp, InsertLabelKey, string[]][] = [
  [new RegExp(`^${NUM} mm NFC sticker$`), 'preset.sticker', ['d']],
  [new RegExp(`^${NUM}x${NUM} NFC coin$`), 'preset.coin', ['d', 't']],
  [/^NFC card$/, 'preset.card', []],
  [new RegExp(`^${NUM}x${NUM}x${NUM} (?:magnet|NFC)$`), 'preset.block', ['l', 'w', 't']],
  [new RegExp(`^${NUM}x${NUM} magnet$`), 'preset.disc', ['d', 't']],
  [new RegExp(`^${NUM}x${NUM} NFC$`), 'preset.coin', ['d', 't']],
];
const CARD = { l: 85.6, w: 54, t: 0.9 };   // presets.py: the one card the table has

/** The message behind an insert label the plugin wrote in English (presets.py: built-in names and default_label),
 *  or null for the user's own preset names, which stay as typed. */
export function parseInsertLabel(label: string): { key: InsertLabelKey; dims: Record<string, number> } | null {
  for (const [re, key, names] of LABELS) {
    const m = re.exec(label);
    if (m) return { key, dims: key === 'preset.card' ? CARD : Object.fromEntries(names.map((n, i) => [n, Number(m[i + 1])])) };
  }
  return null;
}

/** The decimal sign of a locale: "." in en and zh-CN, "," in pt-BR, es and de. */
export function decimalSign(locale: string): string {
  return new Intl.NumberFormat(locale).formatToParts(1.5).find(p => p.type === 'decimal')?.value ?? '.';
}

/** A pasted plain number ("2.5", "2,5", "2.5 mm") written with `sign` as its decimal sign; null for anything else.
 *  ponytail: one "." or "," is always the decimal sign. The fields hold millimetres below 1000, where a group sign
 *  never occurs; a field for larger numbers would need to tell "1.000" from "1.5". */
export function pastedDecimal(text: string, sign: string): string | null {
  const m = /^\s*(-?\d+)(?:[.,](\d+))?\s*(?:mm)?\s*$/i.exec(text);
  return m ? (m[2] == null ? m[1] : `${m[1]}${sign}${m[2]}`) : null;
}
