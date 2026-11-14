import { reactive } from 'vue';
import * as bridge from '../core/bridge';
import { Tracker, message } from '../core/tracker';
import { t } from '../core/i18n';
import { probeWebGL } from '../core/three-probe';
import type { Hello, Settings } from './types';

export const s = reactive({
  tab: 'embed',
  version: '',
  settings: null as Settings | null,
  error: '',
  webgl: null as boolean | null,
});

export const tracker = new Tracker((cmd, args) => bridge.command(cmd, args), (key, params) => t(key, params));
bridge.setErrorSink(e => tracker.notify('error', t('msg.plugin', { error: message(e) })));

export async function hello(): Promise<void> {
  try {
    const r: Hello = await bridge.command('hello');
    s.version = r.version;
    s.settings = r.settings;
    s.error = '';
  } catch (e) {
    s.error = message(e);
  }
}

export function start(): () => void {
  bridge.attach();
  s.webgl = probeWebGL();
  void hello();
  return () => {};
}
