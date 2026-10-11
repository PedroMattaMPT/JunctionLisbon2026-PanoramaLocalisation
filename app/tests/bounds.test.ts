import { describe, expect, it } from 'vitest';
import { reduce } from '../src/reducer';
import { questionBounds, questionView } from '../src/bounds';
import type { RunEvent } from '../src/model';

// Option shapes as panoloc.questions logs them (T50 map fit and tile prefetch); every value here is invented.
const envelope = (seq: number, type: string, payload: Record<string, unknown>): RunEvent =>
  ({ run_id: 'r-bounds-test', panorama: 'invented.jpg', seq, t: seq, ts: '', type, stage: 'ask', actor: 'agent', model: null, payload });
const asked = (options: Record<string, unknown>[]) => reduce([
  envelope(1, 'run.started', { panorama: 'invented.jpg', special_one: false, category: { value: null, source: 'unknown' }, versions: { pipeline: 'test' } }),
  envelope(2, 'question.asked', { question_id: 'q1', kind: 'place', text: 'Where?', options }),
]).question!;

describe('question bounds for the base map', () => {
  it('covers place points with their radius and ignores the complement option', () => {
    const q = asked([
      { id: 'a', label: 'Invented A', point: { lat: 41.0, lng: -8.0 }, radius_m: 1113.2 },
      { id: 'b', label: 'Invented B', point: { lat: 41.2, lng: -8.4 }, radius_m: 500 },
      { id: 'c', label: 'None of these', complement: true },
    ]);
    expect(q.options[0].radius).toBeCloseTo(1113.2);
    const b = questionBounds(q)!;
    expect(b.south).toBeCloseTo(40.99, 2);
    expect(b.north).toBeGreaterThan(41.2);
    expect(b.west).toBeLessThan(-8.4);
    const v = questionView(q)!;
    expect(v.lat).toBeCloseTo((b.south + b.north) / 2);
    expect(v.span).toBeGreaterThan(b.east - b.west);
  });
  it('uses zone polygons (any nesting), else the extent, and gives nothing without geometry', () => {
    const zone = asked([
      { id: 'a', label: 'Invented zone', point: { lat: 40, lng: -8 }, zone: { type: 'MultiPolygon', coordinates: [[[[-9, 39], [-7, 39], [-7, 41], [-9, 41], [-9, 39]]]] } },
      { id: 'b', label: 'Invented box', point: { lat: 43, lng: -3 }, extent: { south: 42, west: -4, north: 44, east: -2 } },
    ]);
    expect(questionBounds(zone)).toEqual({ south: 39, west: -9, north: 44, east: -2 });
    expect(questionBounds(asked([{ id: 'a', label: 'Yes' }, { id: 'b', label: 'No' }]))).toBeUndefined();
  });
});
