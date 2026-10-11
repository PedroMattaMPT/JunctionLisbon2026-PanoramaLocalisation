import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it, vi } from 'vitest';
vi.mock('pannellum', () => ({}));
import { reduce } from '../src/reducer';
import { FocusQuestion } from '../src/focus';
import { QuestionView } from '../src/human';
import type { RunEvent } from '../src/model';

const event = (type: string, payload: Record<string, unknown>, seq: number): RunEvent => ({ run_id: 'review', panorama: 'invented.jpg', seq, t: seq, ts: '', type, stage: 'review', actor: 'agent', model: null, payload });
const asked = event('question.asked', { question_id: 'q1', text: 'Which place fits?', agent_probabilities: { a: .65, b: .25, c: .1 }, options: [{ id: 'a', label: 'Invented A', support: .2 }, { id: 'b', label: 'Invented B', support: .6 }, { id: 'c', label: 'None of these', complement: true, support: .2 }] }, 3);
it('reopens a finished run while preserving its answer and receipts', () => {
  const events = [event('output.produced', { output_id: 'o1', coordinates: [{ lat: 38.7, lng: -9.1 }], penalty: { answered_questions: 1, multiplier: .95 } }, 1), event('run.finished', {}, 2)];
  const before = reduce(events), after = reduce([...events, event('run.reopened', { output_id: 'o1' }, 3)]);
  expect(before.finished).toBe(true); expect(after.finished).toBe(false);
  expect(after.answer).toEqual(before.answer); expect(after.penalty).toEqual(before.penalty);
});
it('shows model option probabilities in both Focus and Full questions, including none of these', () => {
  const c = reduce([asked]);
  expect(c.question!.options.map(o => o.probability)).toEqual([.65, .25, .1]);
  const focus = renderToStaticMarkup(<FocusQuestion c={c} disabled={false} readOnly={false} onAnswer={() => {}} onSkip={() => {}} onHighlight={() => {}} onError={() => {}} onDetails={() => {}} />);
  const full = renderToStaticMarkup(<QuestionView q={c.question!} evidence={[]} disabled={false} onAnswer={() => {}} onSkip={() => {}} onError={() => {}} />);
  for (const html of [focus, full]) for (const percentage of [65, 25, 10]) expect(html).toContain(`Agent probability: ${percentage}%`);
});
it('uses logged support for older questions and keeps missing or invalid probabilities absent', () => {
  const c = reduce([{ ...asked, payload: { question_id: 'q1', options: [{ id: 'a', label: 'A', support: 0 }, { id: 'b', label: 'B', support: .9 }, { id: 'c', label: 'C', probability: 2 }, { id: 'd', label: 'D' }] } }]);
  expect(c.question!.options.map(o => o.probability)).toEqual([0, .9, undefined, undefined]);
});
