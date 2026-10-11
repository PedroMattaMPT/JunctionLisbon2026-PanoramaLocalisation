import { expect, it, vi } from 'vitest';
import { reduce, emptyCase } from '../src/reducer';
import { beatsFor, motionDuration } from '../src/motion';
import { featuresFor, explanationFor } from '../src/analysis-model';
import { caseView, interpolateView, openingView, searchFocus } from '../src/map-model';
import type { RunEvent } from '../src/model';

const event = (seq: number, type: string, payload: Record<string, unknown>, stage = 'describe'): RunEvent =>
  ({ run_id: 'investigation', panorama: 'invented.jpg', seq, type, payload, stage, model: 'test-model', actor: 'model', ts: '', t: seq });
const start = event(1, 'run.started', { versions: { pipeline: 'test' } });
const checking = event(2, 'stage.started', {});
it('converts second-valued CSS tokens into milliseconds for real browser animations and map flights', () => {
  vi.stubGlobal('document', { documentElement: {} });
  vi.stubGlobal('getComputedStyle', () => ({ getPropertyValue: (name: string) => name === '--dur-standard' ? '280ms' : '0.52s' }));
  try { expect(motionDuration('deliberate')).toBe(520); expect(motionDuration('standard')).toBe(280); }
  finally { vi.unstubAllGlobals(); }
});
it('keeps measured per-view progress separate from observations and shifts its box into the image convention', () => {
  const c = reduce([start, checking, event(3, 'stage.progress', { message: 'Checking road markings.', completed: 2, total: 9, view: 'h090', box: { yaw: 90, pitch: 0, w: 90, h: 90 } })]);
  expect(c.evidence).toEqual([]);
  expect(c.stages[0].status).toBe('running');
  expect(c.stages[0].progress).toMatchObject({ completed: 2, total: 9, box: { yaw: 270 } });
  const invalid = reduce([start, checking, event(3, 'stage.progress', { completed: 15, total: 9 })]);
  expect(invalid.stages[0].progress?.completed).toBeNull();
});
it('shows every saved scene answer, including missing visibility, without converting it into a detection', () => {
  const e = reduce([start, event(2, 'evidence.added', { kind: 'vlm_checklist', answers: { post_box: 'red', roof: 'not_visible', pavement: 'granite_slabs' } })]).evidence[0];
  expect(featuresFor(e)).toEqual(expect.arrayContaining([expect.objectContaining({ label: 'Post box', description: 'Red', unknown: false }), expect.objectContaining({ label: 'Roof', description: 'Not visible', unknown: true })]));
  expect(explanationFor(e)).toContain('post box: red');
  expect(explanationFor(e)).not.toContain('roof');
  expect(beatsFor(event(3, 'evidence.added', { kind: 'vlm_checklist' }))).toEqual([5]);
});
it('follows country evidence before fusion, and widens again when country clues conflict', () => {
  const pt = event(2, 'evidence.added', { kind: 'language', value: 'portuguese', countries: ['PT'], strength: 'strong' });
  expect(searchFocus(reduce([start, pt])).label).toBe('Portugal');
  expect(caseView(reduce([start, pt])).span).toBeLessThan(openingView.span);
  const ambiguous = event(3, 'evidence.added', { kind: 'vlm_checklist', features: [{ key: 'vegetation', value: 'eucalyptus', countries: ['PT', 'ES'], strength: 'medium' }] });
  expect(searchFocus(reduce([start, pt, ambiguous])).label).toBe('Portugal');
  const fr = event(3, 'evidence.added', { kind: 'language', value: 'french', countries: ['FR'], strength: 'strong' });
  expect(caseView(reduce([start, pt, fr]))).toEqual(openingView);
  expect(caseView(emptyCase())).toEqual(openingView);
});
it('uses real retrieval coordinates before fused candidates and fits the leading alternatives and their extents', () => {
  const c = reduce([start, event(2, 'evidence.added', { kind: 'knn', neighbours: [
    { lat: 41.1, lng: -8.6, label: 'Invented A', weight: 0.8, extent_m: 1000 },
    { lat: 43, lng: -5, label: 'Invented B', weight: 0.2, extent_m: 80000 },
    { lat: 1000, lng: -8, label: 'Invalid', weight: 100 },
  ] }, 'retrieve')]);
  expect(c.candidates).toHaveLength(0);
  const view = caseView(c);
  expect(view.lat).toBe(41.1);
  expect(view.lng).toBe(-8.6);
  expect(view.span).toBeGreaterThan(10);
});
it('keeps unknown uncertainty broad and never flies tighter than the logged uncertainty', () => {
  const candidates = (accuracy_m?: number, extent_m?: number) => reduce([start,
    { ...event(2, 'candidates.updated', { candidates: [{ lat: 41, lng: -8, role: 'area', source: 'test:area', weight: 1, accuracy_m, extent_m }] }, 'fuse'), actor: 'agent' }]);
  expect(caseView(candidates()).span).toBeGreaterThan(10);
  expect(caseView(candidates(10000, 10000)).span).toBeGreaterThan(1);
});
it('interpolates a map flight continuously and reaches the exact target', () => {
  const target = { lat: 41.1, lng: -8.6, span: 0.1 };
  const middle = interpolateView(openingView, target, 0.5);
  expect(middle.span).toBeGreaterThan(target.span);
  expect(middle.span).toBeLessThan(openingView.span);
  expect(interpolateView(openingView, target, 0)).toEqual(openingView);
  expect(interpolateView(openingView, target, 1).lat).toBe(target.lat);
  expect(interpolateView(openingView, target, 1).span).toBeCloseTo(target.span);
});
