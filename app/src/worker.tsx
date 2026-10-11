import React from 'react';
import { Badge, Button } from '@ds/base';
import type { RunSummary, WorkerStatus } from './data';
import { time } from './format';

/** What the one live worker is doing, across every tab: the run it holds, the question that run waits on,
 * and the uploads queued behind it (T50). The skip is free and neutral, so any console may unblock the worker. */
export function WorkerBanner({ status, runs, ownRunId, onOpen, onSkipRemaining, pending = false }: {
  status?: WorkerStatus; runs: RunSummary[]; ownRunId?: string; onOpen?(runId: string): void;
  onSkipRemaining(runId: string): void; pending?: boolean;
}) {
  if (!status || status.mock || status.worker === 'replay') return null;
  const queue = status.queue ?? [], q = status.current_question ?? null, currentId = status.current ?? null;
  if (!currentId && !queue.length && status.worker === 'online') return null;
  const current = runs.find(r => r.run_id === currentId);
  const name = (id: string) => runs.find(r => r.run_id === id)?.panorama ?? id;
  const skipping = current?.skip_remaining === true;
  const position = ownRunId ? queue.indexOf(ownRunId) : -1;
  return <section className={`app-worker ${q ? 'is-blocked' : ''}`} aria-live="polite" aria-label="Live worker">
    <div className="aq-row">
      <Badge tone={q ? 'contra' : 'neutral'} icon={q ? 'clock' : 'online'}>{status.worker !== 'online' ? `Worker ${status.worker}` : q ? 'Worker waits on a question' : currentId ? 'Worker solving' : 'Worker idle'}</Badge>
      {currentId && <span className="console-data-sm aq-ink2">{name(currentId)} · {currentId}{currentId === ownRunId ? ' · this case' : ''}</span>}
    </div>
    {status.worker !== 'online' && <p className="console-body aq-ink2 app-worker-q">Models are warming up; uploads wait in the queue until the worker is online.</p>}
    {q && <p className="console-body app-worker-q">Question <span className="console-data">{q.question_id}</span>{q.text ? <> · “{q.text}”</> : null} has waited <span className="console-data">{time(q.waiting_s)}</span>{q.timeout_in_s !== null ? <> · auto-skip in <span className="console-data">{time(q.timeout_in_s)}</span></> : null}. {queue.length ? 'Queued uploads start once it is answered or skipped.' : 'Answer it or skip it to let the run finish.'}</p>}
    {currentId && <div className="app-skip-rest">
      {onOpen && currentId !== ownRunId && <Button variant="quiet" icon="forward" onClick={() => onOpen(currentId)}>Open this run</Button>}
      <Button variant="quiet" icon="skip" disabled={pending || skipping} onClick={() => onSkipRemaining(currentId)}>{skipping ? 'Skipping its remaining questions' : 'Skip remaining questions'}</Button>
      <span className="console-micro aq-ink3">Free and neutral: the run finishes with its current output.</span>
    </div>}
    {queue.length > 0 && <p className="console-micro aq-ink2 app-worker-q">{queue.length} upload{queue.length === 1 ? '' : 's'} waiting: {queue.map((id, i) => `${i + 1}. ${name(id)}${id === ownRunId ? ' (this case)' : ''}`).join(' · ')}{position >= 0 ? `. This case starts after ${position === 0 ? 'the current run' : `${position} more`}.` : ''}</p>}
  </section>;
}
