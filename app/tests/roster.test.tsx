import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it, vi } from 'vitest';
vi.mock('pannellum', () => ({}));
import { LoggedRoster } from '../src/ui';
import type { WorkerStatus } from '../src/data';

const status = (plugin: string): WorkerStatus => ({
  worker: 'live', gpu: { used_gb: 10.7, total_gb: 15.92 }, tile_source: null,
  models: [
    { id: 'ocr', name: 'PP-OCRv6 medium', role: 'Reads signs on the CPU', state: 'resident', gb: 0, cpu: true },
    { id: 'vlm-plugin', name: 'hosted-model-9 (API)', role: 'Answers the scene checklist', state: plugin, gb: 0, cpu: true },
    { id: 'qwen', name: 'Qwen3.5-9B (Ollama)', role: 'Answers the scene checklist', state: 'resident', gb: 5.4 },
  ],
});

it('names the VLM rows by where they run, never by the model the server reports', () => {
  const html = renderToStaticMarkup(<LoggedRoster status={status('resident')} models={[]} />);
  expect(html).toContain('VLM (API)');
  expect(html).toContain('VLM (Local)');
  expect(html).not.toContain('hosted-model-9');
  expect(html).toContain('open weights + hosted VLM');
  expect(html).not.toContain('Local model roles');
});
it('keeps the local wording when no hosted VLM is loaded', () => {
  const html = renderToStaticMarkup(<LoggedRoster status={status('disabled')} models={[]} />);
  expect(html).toContain('VLM (Local)');
  expect(html).toContain('all open weights');
  expect(html).toContain('Local model roles');
});
