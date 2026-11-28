import { markRaw, reactive } from 'vue';

// Every printer command goes through one tracker: one in flight per action key (double clicks send once), a
// visible "waiting" state, a UI timeout that reports an UNKNOWN outcome (never success, never an automatic retry)
// and errors that stay until closed (B-04, B-05, U11). Results are returned, never thrown (B-12).
// What it has to say goes to the sink (the page's toasts); a notice with the key of one already shown replaces it,
// which is how a late answer takes the place of its "no answer" notice.
export type NoticeKind = 'error' | 'unknown' | 'success' | 'info';
/** `detail`: the raw technical text behind an error (a Python exception, a path), kept off the sentence the user reads. */
export interface Notice { kind: NoticeKind; text: string; key?: string; detail?: string }
export type NoticeSink = (n: Notice) => void;
export interface Pending { key: string; label: string; startedAt: number; background?: boolean }
export type RunResult<T = any> =
  | { ok: true; result: T }
  | { ok: false; reason: 'busy' | 'error' | 'timeout'; error?: string };
export interface RunOptions {
  key: string;
  label: string;
  cmd: string;
  args?: Record<string, unknown>;
  okText?: string;
  /** Shown instead of okText when the plugin answers {confirmed: false}: the command was sent, the printer has not reported yet. */
  sentText?: string;
  timeoutMs?: number;
  /** E-stop: a second press is allowed while the first is still unanswered. */
  allowRepeat?: boolean;
  /** Errors reported by the caller itself (e.g. inline next to a form). */
  quiet?: boolean;
  /** A read or save the user did not ask for by name (a list refreshed, a setting kept): never announced as "still working". */
  background?: boolean;
}
type Text = (key: 'msg.unknown' | 'msg.lateOk' | 'msg.lateError' | 'msg.failed', params: Record<string, unknown>) => string;

interface Clock { now: () => number; setTimeout: (fn: () => void, ms: number) => unknown }

export const DEFAULT_TIMEOUT_MS = 20_000;

export class Tracker {
  readonly pending = reactive(new Map<string, Pending>());

  private readonly send: (cmd: string, args: Record<string, unknown>) => Promise<any>;
  private readonly text: Text;
  private readonly sink: NoticeSink;
  private readonly clock: Clock;

  constructor(send: (cmd: string, args: Record<string, unknown>) => Promise<any>, text: Text, sink: NoticeSink,
    clock: Clock = { now: () => Date.now(), setTimeout: (fn, ms) => setTimeout(fn, ms) }) {
    this.send = send; this.text = text; this.sink = sink; this.clock = clock;
  }

  isBusy(key: string): boolean { return this.pending.has(key); }

  notify(kind: NoticeKind, text: string, key?: string, detail?: string): void {
    this.sink({ kind, text, key, ...(detail ? { detail } : {}) });
  }

  async run<T = any>(o: RunOptions): Promise<RunResult<T>> {
    if (this.pending.has(o.key) && !o.allowRepeat) return { ok: false, reason: 'busy' };
    const mine: Pending = markRaw({ key: o.key, label: o.label, startedAt: this.clock.now(), ...(o.background ? { background: true } : {}) });
    this.pending.set(o.key, mine);
    const done = () => { if (this.pending.get(o.key) === mine) this.pending.delete(o.key); };
    const timeoutMs = o.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    let timedOut = false;
    const sent = this.send(o.cmd, o.args ?? {});
    const timeout = new Promise<'timeout'>(res => this.clock.setTimeout(() => res('timeout'), timeoutMs));
    try {
      const first = await Promise.race([sent.then(r => ({ r })), timeout]);
      if (first === 'timeout') {
        timedOut = true;
        done();
        this.notify('unknown', this.text('msg.unknown', { action: o.label, seconds: Math.round(timeoutMs / 1000) }), o.key);
        sent.then(   // same key: replaces the "no answer" notice
          () => this.notify('info', this.text('msg.lateOk', { action: o.label }), o.key),
          e => this.notify('error', this.text('msg.lateError', { action: o.label, error: message(e) }), o.key, detailOf(e)),
        );
        return { ok: false, reason: 'timeout' };
      }
      done();
      const unconfirmed = (first.r as { confirmed?: unknown } | null)?.confirmed === false;
      if (unconfirmed && o.sentText) this.notify('info', o.sentText, o.key);
      else if (o.okText) this.notify('success', o.okText, o.key);
      return { ok: true, result: first.r as T };
    } catch (e) {
      if (timedOut) return { ok: false, reason: 'timeout' };
      done();
      const error = message(e);
      if (!o.quiet) this.notify('error', this.text('msg.failed', { action: o.label, error }), o.key, detailOf(e));
      return { ok: false, reason: 'error', error };
    }
  }
}

export function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** The technical text an error carries beside its sentence (`detail` on the thrown error), or undefined. */
export function detailOf(e: unknown): string | undefined {
  const d = (e as { detail?: unknown } | null)?.detail;
  return typeof d === 'string' && d ? d : undefined;
}
