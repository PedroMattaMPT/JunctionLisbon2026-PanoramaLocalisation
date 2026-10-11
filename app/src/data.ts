import { arr, record, str, finite, type RunEvent, type Category, type Fields } from './model';

export function parseLog(text: string): RunEvent[] {
  let input: unknown;
  try { input = JSON.parse(text); } catch {
    input = text.split(/\r?\n/).filter(line => line.trim()).map((line, index) => {
      try { return JSON.parse(line) as unknown; } catch { throw new Error(`Invalid JSON on line ${index + 1}; no events were imported.`); }
    });
  }
  const rows = Array.isArray(input) ? input : arr(record(input).events);
  if (!rows.length) throw new Error('This file contains no run events.');
  if (rows.length > 100000) throw new Error('This log exceeds the local replay limit of 100,000 events.');
  const events = rows.map((row, index) => {
    const e = record(row);
    if (!str(e.run_id) || !str(e.type) || !Number.isInteger(e.seq) || (finite(e.seq) ?? 0) < 1 || finite(e.t) === null || (e.t as number) < 0 || !e.payload || typeof e.payload !== 'object' || Array.isArray(e.payload)) throw new Error(`Event ${index + 1} has an invalid envelope; no events were imported.`);
    return { run_id: str(e.run_id), panorama: str(e.panorama), seq: e.seq as number, t: e.t as number, ts: str(e.ts), type: str(e.type), actor: str(e.actor, 'agent'), stage: str(e.stage) || null, model: str(e.model) || null, payload: record(e.payload) } satisfies RunEvent;
  });
  if (new Set(events.map(e => e.run_id)).size !== 1) throw new Error('A replay must contain exactly one sealed run.');
  if (new Set(events.map(e => e.panorama).filter(Boolean)).size > 1) throw new Error('A sealed run cannot contain more than one panorama.');
  const seen = new Set<number>();
  return events.sort((a, b) => a.seq - b.seq).filter(e => seen.has(e.seq) ? false : (seen.add(e.seq), true));
}
/** One base-map layer behind the live server's caching tile proxy (/api/tiles/<id>/{z}/{x}/{y}). */
export interface TileLayer { id: string; name: string; url: string; max_zoom: number; attribution: string; attribution_url?: string }
/** The question a live run is blocked on (live server only). */
export interface WaitingQuestion { question_id: string; text: string | null; kind: string | null; waiting_s: number; timeout_in_s: number | null }
export interface WorkerStatus {
  worker: string; gpu: { used_gb: number | null; total_gb: number }; models: Fields[];
  tile_source: string | null; csrf_token?: string; mock?: boolean;
  tile_layers?: TileLayer[]; current?: string | null; current_panorama?: string | null; queue?: string[];
  current_question?: WaitingQuestion | null; question_timeout_s?: number | null;
}
export interface RunSummary { run_id: string; status: string; special_one: boolean; panorama?: string; question?: WaitingQuestion | null; skip_remaining?: boolean; position?: number; error?: string }
function waiting(value: unknown): WaitingQuestion | null {
  const q = record(value); if (!str(q.question_id)) return null;
  return { question_id: str(q.question_id), text: str(q.text) || null, kind: str(q.kind) || null, waiting_s: finite(q.waiting_s) ?? 0, timeout_in_s: finite(q.timeout_in_s) };
}
function tileLayers(value: unknown): TileLayer[] {
  return arr(value).map(record).flatMap(l => str(l.id) && str(l.url) && localAsset(str(l.url)) ? [{ id: str(l.id), name: str(l.name, str(l.id)), url: str(l.url), max_zoom: finite(l.max_zoom) ?? 19, attribution: str(l.attribution), attribution_url: str(l.attribution_url) || undefined }] : []);
}
export interface StartInput { file: File; category: Category; categorySource: string; special: boolean }
export interface DataSource {
  readonly mode: 'live' | 'replay';
  start(input: StartInput): Promise<string>;
  subscribe(runId: string, onEvent: (e: RunEvent) => void, onConnection: (connected: boolean) => void, after?: number): () => void;
  answer(runId: string, questionId: string, optionId: string): Promise<void>;
  skip(runId: string, questionId: string): Promise<void>;
  cue(runId: string, text: string): Promise<void>;
  submit(runId: string, outputId: string): Promise<void>;
  priority(runId: string): Promise<void>;
  /** Skip the open question and every later one of this run: free, neutral skips (live server). */
  skipRemaining(runId: string): Promise<void>;
  /** Warm the tile cache behind one open question's options (live server; best effort). */
  prefetchTiles(runId: string, questionId: string, layer: string): Promise<void>;
  log(runId: string): Promise<unknown>;
  list(): Promise<RunSummary[]>;
  status(): Promise<WorkerStatus>;
}
function apiBase() {
  const base = str(import.meta.env.VITE_API_BASE);
  if (!base) return '';
  const url = new URL(base, location.origin);
  if (url.origin !== location.origin && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('The agent API must be served locally.');
  return url.href.replace(/\/$/, '');
}
export class LiveSource implements DataSource {
  readonly mode = 'live';
  private token?: string;
  private base = apiBase();
  private async request(path: string, body?: BodyInit) {
    if (body && !this.token) await this.status();
    const headers: Record<string, string> = {};
    if (body) {
      if (!this.token) throw new Error('The backend did not provide a write token; the action was not sent.');
      headers['X-Aqui-Token'] = this.token;
      if (typeof body === 'string') headers['Content-Type'] = 'application/json';
    }
    let response: Response;
    try { response = await fetch(`${this.base}${path}`, { method: body ? 'POST' : 'GET', headers, body, signal: AbortSignal.timeout(body instanceof FormData ? 120000 : 15000) }); }
    catch { throw new Error('No agent connected. Start the backend or replay a log.'); }
    if (!response.ok) {
      if (path === '/api/status') throw new Error('No agent connected. Start the backend or replay a log.');
      const message = await response.text();
      try { throw new Error(str(record(JSON.parse(message)).error, `Agent returned ${response.status}.`)); }
      catch (error) { if (error instanceof SyntaxError) throw new Error(`Agent returned ${response.status}; the action was not accepted.`); throw error; }
    }
    return response;
  }
  async status(): Promise<WorkerStatus> {
    const p = record(await (await this.request('/api/status')).json());
    this.token = str(p.csrf_token) || undefined;
    return { worker: str(p.worker, 'unknown'), gpu: { used_gb: finite(record(p.gpu).used_gb), total_gb: finite(record(p.gpu).total_gb) ?? 16 }, models: arr(p.models).map(record), tile_source: str(p.tile_source) || null, csrf_token: this.token, mock: p.mock === true,
      tile_layers: tileLayers(p.tile_layers), current: str(p.current) || null, current_panorama: str(p.current_panorama) || null, queue: arr(p.queue).filter((v): v is string => typeof v === 'string'), current_question: waiting(p.current_question), question_timeout_s: finite(p.question_timeout_s) };
  }
  async start(input: StartInput) {
    const body = new FormData(); body.append('file', input.file); body.append('category', input.category === 'unknown' ? '' : input.category); body.append('category_source', input.categorySource); body.append('special_one', String(input.special));
    const p = record(await (await this.request('/api/runs', body)).json());
    if (!str(p.run_id)) throw new Error('The backend did not return a run ID.');
    return str(p.run_id);
  }
  subscribe(runId: string, onEvent: (e: RunEvent) => void, onConnection: (connected: boolean) => void, after = 0) {
    const stream = new EventSource(`${this.base}/api/runs/${encodeURIComponent(runId)}/events?after=${after}`);
    stream.onopen = () => onConnection(true);
    stream.onerror = () => onConnection(false);
    stream.onmessage = message => {
      try { const e = parseLog(`[${message.data}]`)[0]; if (e.run_id === runId) onEvent(e); }
      catch { onConnection(false); }
    };
    stream.addEventListener('end', () => { stream.close(); onConnection(true); });
    return () => stream.close();
  }
  async answer(r: string, q: string, o: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/questions/${encodeURIComponent(q)}/answer`, JSON.stringify({ option_id: o })); }
  async skip(r: string, q: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/questions/${encodeURIComponent(q)}/skip`, '{}'); }
  async cue(r: string, text: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/cues`, JSON.stringify({ text })); }
  async submit(r: string, o: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/submit`, JSON.stringify({ output_id: o })); }
  async priority(r: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/priority`, '{}'); }
  async skipRemaining(r: string) { await this.request(`/api/runs/${encodeURIComponent(r)}/skip-remaining`, '{}'); }
  async prefetchTiles(r: string, q: string, layer: string) { await this.request('/api/tiles/prefetch', JSON.stringify({ run_id: r, question_id: q, layer })); }
  async log(r: string) { return (await this.request(`/api/runs/${encodeURIComponent(r)}/log.json`)).json() as Promise<unknown>; }
  async list(): Promise<RunSummary[]> { const p = await (await this.request('/api/runs')).json() as unknown; return arr(Array.isArray(p) ? p : record(p).runs).map(record).map(r => ({ run_id: str(r.run_id), status: str(r.status, 'unknown'), special_one: r.special_one === true, panorama: str(r.panorama) || undefined, question: waiting(r.question), skip_remaining: r.skip_remaining === true, position: finite(r.position) ?? undefined, error: str(r.error) || undefined })); }
}
/** Replay is immutable. It never writes a response or synthesises a penalty. */
export class ReplaySource implements DataSource {
  readonly mode = 'replay';
  constructor(readonly events: RunEvent[]) {}
  private readonlyError(): never { throw new Error('Replay is read-only; answers and cues need a live agent.'); }
  async start(): Promise<string> { return this.readonlyError(); }
  subscribe(_r: string, onEvent: (e: RunEvent) => void, onConnection: (connected: boolean) => void) { this.events.forEach(onEvent); onConnection(true); return () => {}; }
  async answer(): Promise<void> { return this.readonlyError(); }
  async skip(): Promise<void> { return this.readonlyError(); }
  async cue(): Promise<void> { return this.readonlyError(); }
  async submit(): Promise<void> { return this.readonlyError(); }
  async priority(): Promise<void> { return this.readonlyError(); }
  async skipRemaining(): Promise<void> { return this.readonlyError(); }
  async prefetchTiles(): Promise<void> {}
  async log(): Promise<unknown> { return { schema: 'panoloc.log/1', run_id: this.events[0]?.run_id, events: this.events }; }
  async list(): Promise<RunSummary[]> { return [{ run_id: this.events[0]?.run_id ?? '', status: 'replay', special_one: this.events[0]?.payload.special_one === true }]; }
  async status(): Promise<WorkerStatus> { return { worker: 'replay', gpu: { used_gb: null, total_gb: 16 }, models: [], tile_source: null }; }
}
export function localAsset(value: unknown): string | undefined {
  const input = str(value); if (!input) return;
  if (input.startsWith('blob:')) return input;
  try {
    const url = new URL(input, location.origin);
    const local = url.origin === location.origin || ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
    return local && ['http:', 'https:'].includes(url.protocol) ? url.href.replace(/%7B([zxy])%7D/gi, '{$1}') : undefined;
  } catch { return undefined; }
}
