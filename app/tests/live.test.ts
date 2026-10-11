import { describe, expect, it } from 'vitest';
import { reduce } from '../src/reducer';
import type { RunEvent } from '../src/model';

// Payload shapes as panoloc.pipeline logs them (T76); every value here is invented.
const envelope = (seq: number, type: string, payload: Record<string, unknown>, stage: string | null = null): RunEvent =>
  ({ run_id: 'r-live-test', panorama: 'invented.jpg', seq, t: seq, ts: '', type, stage, actor: 'agent', model: null, payload });
const started = (versions: Record<string, unknown>) => envelope(1, 'run.started', { panorama: 'invented.jpg', special_one: false, category: { value: null, source: 'unknown' }, versions });
const box = { yaw: 312.5, pitch: 20, w: 4, h: 2 };
const pipelineRun = [
  started({ pipeline: 'panoloc.pipeline v1', schema: 'panoloc.log/1' }),
  envelope(2, 'evidence.added', { evidence_id: 'e1', kind: 'ocr_text', sign_id: 's1', text: 'INVENTED SIGN', confidence: 0.99, box }, 'read'),
  envelope(3, 'evidence.added', { evidence_id: 'e2', kind: 'name', text: 'INVENTED SIGN', value: 'invented sign', ocr_evidence_id: 'e1', confidence: 0.99, box }, 'read'),
  envelope(4, 'evidence.added', { evidence_id: 'e3', kind: 'language', text: 'INVENTED SIGN', value: 'pt', ocr_evidence_id: 'e1', box }, 'read'),
  envelope(5, 'question.asked', {
    question_id: 'q1', kind: 'zone', text: 'Which zone holds the camera?', scope: { south: 36, west: -10, north: 44, east: 4 },
    expected_gain: { gain: 0.12, break_even: 0.0526 },
    options: [
      { id: 'a', label: 'Invented north', detail: 'Northern cell.', point: { lat: 41, lng: -8 }, bound_m: 9000, links: { osm_cell: 'https://www.openstreetmap.org/' }, complement: false },
      { id: 'b', label: 'Outside this area', complement: true },
    ],
  }, 'ask'),
];

describe('real pipeline events', () => {
  it('moves pipeline yaws (0 = image centre) to the app convention (0 = left edge)', () => {
    const c = reduce(pipelineRun);
    expect(c.evidence.find(e => e.id === 'e1')?.box?.yaw).toBeCloseTo(132.5);
    expect(c.texts.map(t => [t.id, t.yaw])).toEqual([['e1', 132.5]]); // the parsed item repeats the sign: drawn once
    const fixture = reduce([started({ mock: true }), ...pipelineRun.slice(1)]);
    expect(fixture.evidence.find(e => e.id === 'e1')?.box?.yaw).toBeCloseTo(312.5);
  });
  it('shows OCR text instead of a generic caption, and no empty language vote', () => {
    const c = reduce(pipelineRun);
    expect(c.evidence.find(e => e.id === 'e1')?.obs).toBe('INVENTED SIGN');
    expect(c.evidence.find(e => e.id === 'e2')?.obs).toBe('INVENTED SIGN → invented sign');
    expect(c.language).toBeNull();
  });
  it('reads complement options, the nested expected gain and a box scope', () => {
    const q = reduce(pipelineRun).question!;
    expect(q.options.map(o => [o.key, o.none])).toEqual([['A', false], ['B', true]]);
    expect(q.options[0].reason).toBe('Northern cell.');
    expect(q.gain).toBeCloseTo(0.12);
    expect(q.breakEven).toBeCloseTo(0.0526);
    expect(q.scope).toHaveLength(1);
  });
});
