import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it, vi } from 'vitest';
// The panorama adapter needs a browser at import time; real viewer behavior is checked in Playwright.
vi.mock('pannellum', () => ({}));
import { emptyCase } from '../src/reducer';
import type { Option, Output, Question } from '../src/model';
import { FocusAnswer, FocusQuestion, FocusWorking } from '../src/focus';
import type { RunEvent } from '../src/model';
import { focusCaseStatus, focusOptions, initialFullConsole, optionSize, plainLabel, uncertaintySentence } from '../src/focus-model';

const option = (id: string, radius?: number): Option => ({ id, key: id.toUpperCase(), label: 'Serra (Tomar, Santarém)', reason: `Original wording ${id}: wikidata:Q123, radius ${radius}.`, chips: [], none: false, links: {}, radius });
const question: Question = { id: 'q1', text: 'Where was this panorama taken? Exactly as asked.', kind: 'place', options: [option('a', 4300), option('b', 1200)], scope: [], gain: 0.53, breakEven: 1 / 0.95 - 1, cost: 0.95, status: 'open', askedAt: 20, before: [], multiplierBefore: 1 };
const output: Output = { id: 'o1', t: 30, seq: 12, lat: 41.1407, lng: -8.613, role: 'area', method: 'coarse_candidate', r: null, rSource: 'source_estimate', multiplier: 0.95, penalty: { answered_questions: 1, cues: 0, conversions: 0, multiplier: 0.95 }, category: 'unknown', special: false, expected: null, max: 16050, why: '', sources: ['wikidata:Q123'], coordinates: [{ rank: 1, lat: 41.1407, lng: -8.613 }], raw: {} };

it('keeps question wording and the original option record while distinguishing equal labels by radius', () => {
  const before = JSON.stringify(question);
  const shown = focusOptions(question);
  expect(shown.map(o => o.label)).toEqual(['Serra (Tomar, Santarém) · within 4.3 km', 'Serra (Tomar, Santarém) · within 1.2 km']);
  const html = renderToStaticMarkup(<FocusQuestion c={{ ...emptyCase(), question, questions: [question] }} disabled readOnly onAnswer={() => { throw Error('No implicit answer'); }} onSkip={() => { throw Error('No implicit skip'); }} onHighlight={() => {}} onError={() => {}} onDetails={() => {}} />);
  expect(html).toContain(question.text);
  expect(html).toContain(question.options[0].reason);
  expect(html).toContain('An answer costs ×0.95. Skip changes nothing.');
  expect(html).not.toContain('aq-costtag');
  expect(JSON.stringify(question)).toBe(before);
});
it('uses zone dimensions as an area size, never as a circular place radius', () => {
  const zone = { ...option('a'), extent: { south: 40, north: 40.01, west: -8, east: -7.99 } };
  expect(optionSize(zone)).toMatch(/m × 1.1 km area$/);
  expect(optionSize({ ...zone, none: true })).toBe('');
  expect(optionSize(option('a'))).toBe('');
  expect(optionSize(option('a', 0))).toBe('within 0 m');
});
it('shows coordinates despite unknown uncertainty and omits technical sources from the answer', () => {
  const html = renderToStaticMarkup(<FocusAnswer a={output} onCopy={() => {}} onSubmit={() => {}} canSubmit={false} onDetails={() => {}} />);
  expect(html).toContain('41.14070, −8.61300');
  expect(html).toContain('Uncertainty unknown.');
  expect(html).toContain('×0.95 after 1 answer');
  expect(html).not.toMatch(/coarse_candidate|wikidata:|source_estimate|± unknown/);
  expect(uncertaintySentence({ ...output, role: 'camera', r: 0 })).toBe('A camera position, probably within 0 m.');
});
it('labels score scenarios as estimates and applies the Special One factor once', () => {
  const html = renderToStaticMarkup(<FocusAnswer a={{ ...output, r: 180, split: { urban: 1000, nonUrban: 2000 }, special: true }} onCopy={() => {}} onSubmit={() => {}} canSubmit onDetails={() => {}} />);
  expect(html).toContain('Score estimate');
  expect(html).toContain('3,000');
  expect(html).toContain('6,000');
});
it('keeps a case working after an intermediate output and gives an open question priority', () => {
  expect(focusCaseStatus(emptyCase(), true, 'waiting')).toBe('waiting');
  expect(focusCaseStatus(emptyCase(), true, 'processing')).toBe('working');
  const c = { ...emptyCase(), answer: output };
  expect(focusCaseStatus(c, true)).toBe('working');
  expect(focusCaseStatus(c, true, 'answer ready')).toBe('done');
  expect(focusCaseStatus({ ...c, finished: true }, true)).toBe('done');
  expect(focusCaseStatus({ ...c, question }, true)).toBe('question');
  expect(focusCaseStatus({ ...c, submitted: true }, true)).toBe('submitted');
});
it('keeps queue status current when polling arrives before the event stream', () => {
  expect(focusCaseStatus(emptyCase(), true, 'question waiting')).toBe('question');
  expect(focusCaseStatus(emptyCase(), true, 'finished')).toBe('done');
});
it('allows an explicit fallback even when localStorage fails, and respects a focus override', () => {
  const unavailable = { getItem() { throw Error('Storage unavailable'); } };
  expect(initialFullConsole('?view=full', unavailable)).toBe(true);
  expect(initialFullConsole('', unavailable)).toBe(false);
  expect(initialFullConsole('?view=focus', { getItem: () => 'full' })).toBe(false);
  expect(initialFullConsole('', { getItem: () => 'full' })).toBe(true);
});
it('removes technical identifiers from labels without rewriting human place names', () => {
  expect(plainLabel('GeoCLIP estimate in Cedofeita, Porto (PT)')).toBe('Cedofeita, Porto (PT)');
  expect(plainLabel('wikidata:Q31799706')).toBe('Area estimate');
  expect(plainLabel('geonames:123')).toBe('Area estimate');
  expect(plainLabel('GeoCLIP stock gallery point 4172')).toBe('Area estimate');
  expect(plainLabel('Ribeira, Porto (PT)')).toBe('Ribeira, Porto (PT)');
});
it('uses Thinking for activity without displaying a model name or invented detections', () => {
  const event = { type: 'stage.started', actor: 'model', model: 'qwen3.5:9b', stage: 'describe' } as RunEvent;
  const html = renderToStaticMarkup(<FocusWorking c={emptyCase()} event={event} onDetails={() => {}} onSelect={() => {}} />);
  expect(html).toContain('Thinking');
  expect(html).not.toMatch(/Qwen|qwen|is thinking|Found in the panorama/);
});
