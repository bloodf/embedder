// Host transport: OrcaSlicer's window.orca (postMessage / onMessage / submit). Message contract (docs/architecture.md):
// {type:"cmd", id, cmd, args} → {type:"reply", id, result} or {type:"reply", id, error: {code, detail}}.
type Handler = (m: any) => void;
interface Waiter { resolve: (v: any) => void; reject: (e: unknown) => void }

const listeners = new Set<Handler>();
const waiters = new Map<number, Waiter>();
let seq = 0;
let attached = false;

/** A command the plugin refused: `code` is stable (see docs/architecture.md), `detail` is human text. */
export class ReplyError extends Error {
  constructor(readonly code: string, readonly detail: string) { super(detail || code); }
}

function replyError(error: unknown): ReplyError {
  if (error && typeof error === 'object') {
    const e = error as { code?: unknown; detail?: unknown };
    return new ReplyError(String(e.code ?? 'internal'), String(e.detail ?? ''));
  }
  return new ReplyError('internal', String(error));
}

function host(): OrcaHostBridge {
  if (!window.orca) throw new Error('OrcaSlicer bridge missing');
  return window.orca;
}

export function attach(): void {
  if (attached) return;
  attached = true;
  host().onMessage(m => {
    if (!m || typeof m !== 'object') return;
    if (m.type === 'reply' && typeof m.id === 'number' && waiters.has(m.id)) {
      const w = waiters.get(m.id)!;
      waiters.delete(m.id);
      if ('error' in m) w.reject(replyError(m.error)); else w.resolve(m.result);
      return;
    }
    listeners.forEach(h => { try { h(m); } catch (e) { reportError(e); } });
  });
}

export function onMessage(h: Handler): () => void { listeners.add(h); return () => listeners.delete(h); }
export function post(message: Record<string, unknown>): void { host().postMessage(message); }

/** A message that the plugin answers with a reply carrying the same id. Never times out by itself. */
export function request(message: Record<string, unknown>): Promise<any> {
  const id = ++seq;
  return new Promise((resolve, reject) => { waiters.set(id, { resolve, reject }); post({ ...message, id }); });
}

export function command(cmd: string, args: Record<string, unknown> = {}): Promise<any> {
  return request({ type: 'cmd', cmd, args });
}

export function submit(result: unknown): void { host().submit?.(result); }

let errorSink: (e: unknown) => void = () => {};
export function setErrorSink(fn: (e: unknown) => void): void { errorSink = fn; }
export function reportError(e: unknown): void { errorSink(e); }
