export type Fields = Record<string, unknown>;
export type Actor = 'solver' | 'model' | 'team';
export type Category = 'urban' | 'non-urban' | 'unknown';
export interface RunEvent {
  run_id: string; panorama: string; seq: number; t: number; ts: string;
  type: string; stage: string | null; actor: string; model: string | null; payload: Fields;
}
export interface Penalty { answered_questions: number; cues: number; conversions: number; multiplier: number }
export interface Box { yaw: number; pitch: number; w: number; h: number }
export interface Stage {
  id: string; name: string; models: string[]; status: string; dur: number | null;
  started: number; deadline: number | null; optional: boolean; note?: string; fallback?: string; seq: number;
}
export interface Evidence {
  id: string; kind: string; stage: string; actor: Actor; model: string; t: number; seq: number;
  obs: string; inference?: string; conf: number | null; box?: Box; ref?: string;
  notVisible: boolean; group?: string; pol: Record<string, number>; payload: Fields;
}
export interface Candidate {
  id: string; rank: number; name: string; level: string; lat?: number; lng?: number;
  role: string; source: string; weight: number; v: number | null; lo?: number; hi?: number;
  delta: number | null; sup?: number; con?: number; r: number | null;
  supports: string[]; contradicts: string[]; evidence: string[]; group?: string; details: Fields;
}
export interface Option {
  id: string; key: string; label: string; reason: string; chips: string[];
  point?: [number, number]; zone?: Fields; region?: string; none: boolean; links: Record<string, string>;
  /** Place options: the camera stood within radius_m of point. Zones: their logged bounding box. */
  radius?: number; extent?: { south: number; west: number; north: number; east: number };
}
export interface Question {
  id: string; text: string; kind: string; options: Option[]; scope: string[];
  gain: number | null; breakEven: number; cost: number; wordedBy?: string;
  status: 'open' | 'answered' | 'skipped'; answer?: string; askedAt: number; resolvedAt?: number;
  before: Candidate[]; after?: Candidate[]; multiplierBefore: number; multiplierAfter?: number;
}
export interface Output {
  id: string; t: number; seq: number; lat: number; lng: number; role: string; method: string;
  r: number | null; rSource: string; multiplier: number; penalty: Penalty; category: Category;
  special: boolean; expected: number | null; split?: { urban: number; nonUrban: number };
  max: number; why: string; sources: string[]; mostLikely?: boolean;
  coordinates: { rank: number; lat: number; lng: number }[]; raw: Fields;
}
export interface CaseRecord {
  id: string; label: string; file: string; urban: Category; urbanSource: string; special: boolean;
  date?: string; time?: string; shot?: number; size?: [number, number]; scene?: string;
  events: RunEvent[]; stages: Stage[]; evidence: Evidence[]; candidates: Candidate[]; outputs: Output[];
  answer?: Output; questions: Question[]; question?: Question; ruledOut: Fields[];
  detections: (Box & { id: string; label: string; score: number | null; kept?: boolean })[];
  texts: (Box & { id: string; text: string; conf: number | null })[];
  language: { id: string; v: number }[] | null; shares: { id: string; v: number }[] | null;
  masked?: number; maskUrl?: string; maskPalette?: Fields; photographerMask?: number; viewCount?: number;
  yawToBearing: number | null; yawToBearingErr?: number;
  /** Degrees added to logged yaws: 180 for panoloc.pipeline logs, whose yaw 0 is the image centre (panoloc/views.py). */
  yawShift?: number;
  sun?: { azimuth: number; elevation: number; yaw?: number };
  regions: Fields[]; neighbours: Evidence[]; matches: Evidence[];
  groups: { id: string; label: string; members: string[]; cap?: number }[];
  matrix: { candidates: string[]; names: Record<string, string> };
  penalty: Penalty; multiplierHistory: { t: number; m: number; what: string }[];
  finished: boolean; submitted: boolean;
  run: { used: number; budget: number; session: number; sessionBudget: number; gpu: number | null;
    gpuMax: number; multiplier: number; expected: number | null; split?: { urban: number; nonUrban: number } };
}
export const record = (value: unknown): Fields => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Fields : {};
export const arr = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
export const str = (value: unknown, fallback = ''): string => typeof value === 'string' ? value : fallback;
export const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
export const strings = (value: unknown): string[] => arr(value).filter((x): x is string => typeof x === 'string');
export const positive = (value: unknown): number | null => { const n = finite(value); return n !== null && n > 0 ? n : null; };
export const nonnegative = (value: unknown): number | null => { const n = finite(value); return n !== null && n >= 0 ? n : null; };
export function angularBox(value: unknown): Box | undefined {
  const b = record(value); const [yaw, pitch, w, h] = ['yaw', 'pitch', 'w', 'h'].map(k => finite(b[k]));
  return yaw !== null && pitch !== null && w !== null && h !== null && w > 0 && h > 0 && w <= 360 && h <= 180 && Math.abs(pitch) <= 90 ? { yaw: (yaw % 360 + 360) % 360, pitch, w, h } : undefined;
}
export function point(value: unknown): { lat: number; lng: number } | undefined {
  const p = record(value); const lat = finite(p.lat), lng = finite(p.lng);
  return lat !== null && lng !== null && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? { lat, lng } : undefined;
}
export function snapshot(value: unknown): Penalty | undefined {
  const p = record(value);
  if (['answered_questions', 'cues', 'conversions', 'multiplier'].some(k => finite(p[k]) === null)) return;
  return { answered_questions: p.answered_questions as number, cues: p.cues as number, conversions: p.conversions as number, multiplier: p.multiplier as number };
}
export function extentOf(value: unknown): { south: number; west: number; north: number; east: number } | undefined {
  const e = record(value); const [south, west, north, east] = ['south', 'west', 'north', 'east'].map(k => finite(e[k]));
  return south !== null && west !== null && north !== null && east !== null && south <= north && Math.abs(south) <= 90 && Math.abs(north) <= 90 ? { south, west, north, east } : undefined;
}
