import { theta, RANK_W, MAX_SCORE } from '@ds/rt';
import type { Category } from './model';
export { MAX_SCORE };
export const coordinate = (n: number) => `${n < 0 ? '−' : ''}${Math.abs(n).toFixed(5)}`;
export const coordinates = (lat: number, lng: number) => `${coordinate(lat)}, ${coordinate(lng)}`;
export const time = (s: number) => { const n = Math.max(0, Math.floor(s)); return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`; };
export const distance = (m: number | null | undefined) => m == null ? 'unknown' : m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
export const roleText = (role: string) => ({ camera: 'camera position', landmark: 'landmark point, not a camera position', area: 'representative point of an area, not a camera position' }[role] ?? 'coordinate role not logged');
// VLM sources use their role in the UI, independent of model family or hosting.
export const modelName = (id: string | null, kind?: string) =>
  ['checklist', 'vlm_checklist', 'vlm_summary', 'landmark_hypothesis'].includes(kind ?? '') || /\b(?:qwen[\d.]*|gemma\d*|vlm)\b|[-_:]cloud\b|^[a-z]+-[a-z]+-\d+(?:-\d+)*$/i.test(id ?? '') ? 'VLM' : id ?? 'Solver';
export const stageName = (id: string | null) => ({ views: 'Views', detect: 'Detect', read: 'Read', describe: 'Describe', measure: 'Measure', geo: 'Pixel geolocation', names: 'Name lookup', fuse: 'Fusion', fusion: 'Fusion', ask: 'Ask', spot: 'Exact spot', output: 'Answer' }[id ?? ''] ?? id ?? 'Run');
// This is an explicitly labelled estimate using the logged radius as a distance proxy.
// It is not an integral over a hidden error distribution, and never uses an answer key.
export function score(radius: number | null, category: Category, multiplier: number, ranks = 10) {
  if (radius === null) return { expected: null };
  const factor = 1000 * RANK_W.slice(0, ranks).reduce((sum: number, w: number) => sum + w, 0) * multiplier;
  const urban = factor * theta(radius, true), nonUrban = factor * theta(radius, false);
  return { expected: category === 'unknown' ? null : category === 'urban' ? urban : nonUrban, split: category === 'unknown' ? { urban, nonUrban } : undefined };
}
export function haversine(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const r = Math.PI / 180, dlat = (b.lat - a.lat) * r, dlng = (b.lng - a.lng) * r;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dlng / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - Math.min(1, h)));
}
