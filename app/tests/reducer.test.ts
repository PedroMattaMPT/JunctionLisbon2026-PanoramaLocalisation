import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { localAsset, LiveSource, parseLog, ReplaySource } from '../src/data';
import { emptyCase, parseFilename, reduce, reduceEvent } from '../src/reducer';
import { captionFor } from '../src/captions';
import { record, snapshot, type RunEvent } from '../src/model';
import { score, MAX_SCORE, coordinates } from '../src/format';
import { beatsFor } from '../src/motion';
const fixtures = ['sample', 'case-a', 'case-b'].map(name => ({ name, events: parseLog(readFileSync(new URL(`../public/fixtures/${name}.events.jsonl`, import.meta.url), 'utf8')) }));
const event = (type: string, payload = {}, seq = 1): RunEvent => ({ run_id: 'test-run', panorama: 'invented.jpg', seq, t: seq, ts: '', type, stage: 'unknown-stage', actor: 'agent', model: null, payload });

describe.each(fixtures)('$name log invariants', ({ events }) => {
  it('uses every backend penalty snapshot and preserves skips', () => {
    let state = emptyCase();
    for (const e of events) {
      const before = state; state = reduceEvent(state, e); const p = snapshot(e.payload.penalty);
      if (p) expect(state.penalty).toEqual(p);
      if (e.type === 'question.skipped') {
        expect(state.penalty).toEqual(before.penalty);
        expect(state.candidates).toEqual(before.candidates);
        expect(state.questions.find(q => q.id === e.payload.question_id)?.status).toBe('skipped');
      }
    }
  });
  it('keeps each output snapshot instead of overwriting earlier outputs', () => {
    const state = reduce(events), raw = events.filter(e => e.type === 'output.produced');
    expect(state.outputs).toHaveLength(raw.length);
    state.outputs.forEach((output, i) => expect(output.penalty).toEqual(raw[i].payload.penalty));
  });
  it('makes a complete caption for every event and every replay prefix', () => {
    for (const e of events) {
      const caption = captionFor(e); expect(caption.caption).not.toMatch(/undefined|NaN/); expect(caption.headline).toBeTruthy(); expect(caption.caption).toBeTruthy();
      const state = reduce(events.filter(p => p.seq <= e.seq)); expect(state.events.at(-1)?.seq).toBe(e.seq);
    }
  });
  it('ignores repeated sequence IDs and sorts imported events', () => {
    expect(reduce([...events, ...events].reverse())).toEqual(reduce(events));
    const final = reduce(events); expect(reduceEvent(final, events[0])).toBe(final);
  });
  it('does not mutate input events', () => {
    const saved = JSON.stringify(events); reduce(events); expect(JSON.stringify(events)).toBe(saved);
  });
});
describe('missing information and case boundaries', () => {
  it('keeps unknown event types and kinds, without breaking the state', () => {
    const events = [event('future.type'), event('evidence.added', { kind: 'future-kind', evidence_id: 'unknown' }, 2)];
    const state = reduce(events); expect(state.events).toEqual(events); expect(state.evidence[0].kind).toBe('future-kind');
    expect(captionFor(events[1]).caption).not.toMatch(/undefined|NaN/);
  });
  it('retains null uncertainty and does not invent a box, range or support', () => {
    const state = reduce([event('candidates.updated', { candidates: [{ candidate_id: 'c', lat: 41, lng: -8, role: 'area', source: 'fixture:c', weight: 0 }] }), event('evidence.added', { evidence_id: 'e', kind: 'text', text: 'word' }, 2)]);
    expect(state.candidates[0].r).toBeNull(); expect(state.candidates[0].v).toBeNull(); expect(state.candidates[0].lo).toBeUndefined(); expect(state.evidence[0].box).toBeUndefined(); expect(state.texts).toEqual([]); expect(state.run.expected).toBeNull();
  });
  it('does not combine runs or accept an output attributed to a language model', () => {
    const first = event('run.started'); const foreign = { ...event('cue.sent', { penalty: { answered_questions: 0, cues: 1, conversions: 0, multiplier: 0.8 } }, 2), run_id: 'foreign' };
    expect(reduce([first, foreign]).events).toEqual([first]);
    expect(() => parseLog(JSON.stringify([first, foreign]))).toThrow('sealed run');
    const forged = { ...event('output.produced', { coordinates: [{ lat: 41, lng: -8 }] }, 2), actor: 'model', model: 'qwen3.5:9b' };
    expect(reduce([first, forged]).answer).toBeUndefined();
    expect(captionFor(forged).caption).not.toContain('41.00000');
  });
  it('refuses malformed envelopes before importing any events', () => {
    expect(() => parseLog('{bad')).toThrow('Invalid JSON'); expect(() => parseLog(JSON.stringify([{ seq: 1 }]))).toThrow('invalid envelope');
    expect(() => parseLog(JSON.stringify([{ ...event('future'), t: null }]))).toThrow('invalid envelope');
  });
  it('replay never fabricates a costing interaction', async () => {
    const source = new ReplaySource(fixtures[0].events); await expect(source.answer()).rejects.toThrow('read-only'); await expect(source.cue()).rejects.toThrow('read-only'); await expect(source.skip()).rejects.toThrow('read-only');
  });
  it('validates the date in a parsed filename', () => {
    expect(parseFilename('IMG_20260115_143012_00_204.jpg')).toEqual({ date: '2026-01-15', time: '14:30:12', shot: 204 }); expect(parseFilename('IMG_20260231_143012_00_204.jpg')).toEqual({});
  });
  it('keeps score estimates separate from unknown uncertainty and category', () => {
    expect(score(null, 'urban', 1).expected).toBeNull(); expect(score(5, 'urban', 1).expected).toBeCloseTo(MAX_SCORE); expect(score(25, 'urban', 0.95).expected).toBeCloseTo(MAX_SCORE * 0.8 * 0.95);
    const split = score(1500, 'unknown', 0.76).split!; expect(split.nonUrban).toBeGreaterThan(split.urban); expect(coordinates(41.14081, -8.61315)).toBe('41.14081, −8.61315');
  });
  it('all twelve motion beats are driven by logged events in the rich fixture', () => {
    const beats = new Set(fixtures[1].events.flatMap(beatsFor)); expect([...beats].sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  });
  it('the real sample covers failed optional stages, a skip, an answer, a cue and distinct output snapshots', () => {
    const sample = reduce(fixtures[0].events); expect(sample.stages.some(s => s.status === 'failed' && s.optional)).toBe(true); expect(sample.questions.map(q => q.status)).toEqual(['skipped', 'answered']); expect(sample.penalty.multiplier).toBe(0.76); expect(sample.outputs.map(o => o.multiplier)).toEqual([1, 0.76]);
  });
  it('the rural fixture stays free after a skip', () => {
    const state = reduce(fixtures[2].events); expect(state.penalty.multiplier).toBe(1); expect(state.language).toBeNull(); expect(state.questions[0].after).toEqual(state.questions[0].before); expect(record(state.events[0].payload.versions).fixture).toContain('Invented');
  });
});
describe('sparse proposed payloads', () => {
  it('explains a disconnected backend even when the local proxy returns an HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('proxy unavailable', { status: 503 })));
    try { await expect(new LiveSource().status()).rejects.toThrow('No agent connected'); } finally { vi.unstubAllGlobals(); }
  });
  it('keeps local raster template placeholders and refuses malformed or external asset URLs', () => {
    vi.stubGlobal('location', { origin: 'http://127.0.0.1:5178' });
    try { expect(localAsset('/tiles/{z}/{x}/{y}.png')).toBe('http://127.0.0.1:5178/tiles/{z}/{x}/{y}.png'); expect(localAsset('https://example.com/photo.jpg')).toBeUndefined(); expect(localAsset('http://[')).toBeUndefined(); } finally { vi.unstubAllGlobals(); }
  });
  it('keeps sparse region and unknown share classes in the log without drawing fabricated bars', () => {
    const state = reduce([event('evidence.added', { evidence_id: 'regions', kind: 'region', regions: [{ name: 'Unmeasured' }, { name: 'Known', v: 0.3 }] }), event('evidence.added', { evidence_id: 'language', kind: 'language', votes: { pt: 0.6, future: 0.4 } }, 2)]);
    expect(state.regions).toEqual([{ name: 'Known', v: 0.3 }]); expect(state.language).toEqual([{ id: 'pt', v: 0.6 }]); expect(state.events[0].payload.regions).toHaveLength(2);
  });
  it('does not invent counts when point or name arrays are missing', () => {
    for (const kind of ['geo_sample', 'name_match']) expect(captionFor(event('evidence.added', { kind })).caption).not.toMatch(/\b0 (places|logged)/);
  });
  it('preserves a logged zero radius as distinct from a null radius', () => {
    const state = reduce([event('output.produced', { output_id: 'o', coordinates: [{ lat: 41, lng: -8 }], position_uncertainty_m: 0, category: { value: 'urban' }, penalty: { answered_questions: 0, cues: 0, conversions: 0, multiplier: 1 } })]);
    expect(state.answer?.r).toBe(0); expect(state.answer?.expected).toBe(2000);
  });
});
