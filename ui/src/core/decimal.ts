// PrimeVue 5.0.5 InputNumber takes only its locale's own decimal sign. In de, es and pt-BR "." is the group sign, so
// "2.5" typed or pasted into a millimetre field became 25. v-decimal, on an InputNumber that has :locale, reads a
// typed "." or "," as the decimal sign and a pasted "2.5" or "2,5" as two and a half, in every language. It listens
// on the field's wrapper in the capture phase, before InputNumber's own handlers on the input, and hands InputNumber
// the same key or paste with the locale's sign instead.
import type { Directive } from 'vue';
import { locale } from './i18n';
import { decimalSign, pastedDecimal } from './i18n-core';

const ours = new WeakSet<Event>();

function again(target: EventTarget | null, e: Event): void {
  ours.add(e);
  target?.dispatchEvent(e);
}

// A Chinese input method in Chinese mode types the full-width signs.
const DECIMAL_KEYS = ['.', ',', '。', '．', '，'];

function onKeypress(e: KeyboardEvent): void {
  const sign = decimalSign(locale.value);
  if (ours.has(e) || !DECIMAL_KEYS.includes(e.key) || e.key === sign) return;
  e.preventDefault();
  e.stopPropagation();
  again(e.target, new KeyboardEvent('keypress', { key: sign, bubbles: true, cancelable: true }));
}

function onPaste(e: ClipboardEvent): void {
  const text = e.clipboardData?.getData('text/plain') ?? '';
  const fixed = pastedDecimal(text, decimalSign(locale.value));
  if (ours.has(e) || fixed == null || fixed === text.trim()) return;
  let paste: ClipboardEvent;
  try {   // a WebView without these constructors keeps InputNumber's own paste
    const data = new DataTransfer();
    data.setData('text/plain', fixed);
    paste = new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true });
  } catch { return; }
  e.preventDefault();
  e.stopPropagation();
  again(e.target, paste);
}

export const vDecimal: Directive<HTMLElement> = {
  mounted(el) {
    el.addEventListener('keypress', onKeypress, true);
    el.addEventListener('paste', onPaste, true);
  },
  unmounted(el) {
    el.removeEventListener('keypress', onKeypress, true);
    el.removeEventListener('paste', onPaste, true);
  },
};
