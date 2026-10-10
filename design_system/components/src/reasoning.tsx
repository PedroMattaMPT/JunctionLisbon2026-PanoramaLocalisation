import { h, Fragment, cx, useT, useDensity, fmtEst, fmtTime } from './rt';
import { Icon } from './icons';
import { Badge, Stamp } from './base';
import { ModelChip } from './shell';
import { ConfidenceMeter } from './charts';

// ---------------------------------------------------------------------------
const STATUS_WORD: Record<string, string> = { queued: 'Queued', running: 'Running', done: 'Done', skipped: 'Skipped', failed: 'Failed', timed_out: 'Timed out' };
const STATUS_ICON: Record<string, string> = { queued: 'queued', running: 'running', done: 'done', skipped: 'skipped', failed: 'failed', timed_out: 'timeout' };
export interface StageRowProps { stage: any; compact?: boolean; pass?: number }
/** One pipeline stage: status (icon + word), its models, real duration, memory. Running shows real elapsed against the stage deadline. */
export function StageRow({ stage: s, compact, pass }: StageRowProps) {
  const T = useT();
  const st = s.status as string;
  return h('li', { className: cx('aq-stage', 'is-' + st, compact && 'is-compact') },
    h('span', { className: 'aq-stage-i', title: STATUS_WORD[st] }, h(Icon, { name: STATUS_ICON[st] })),
    h('span', { className: 'aq-stage-n' },
      h('span', { className: T.heading }, s.name), s.optional ? h('span', { className: cx(T.micro, 'aq-ink3') }, ' optional') : null, pass ? h('span', { className: cx(T.micro, 'aq-ink3') }, ` · pass ${pass}`) : null,
      compact ? null : h('span', { className: cx('aq-stage-m', T.micro) }, (s.models || []).join(' · '))),
    h('span', { className: cx('aq-stage-w', T.micro) }, STATUS_WORD[st]),
    h('span', { className: cx('aq-stage-d', T.dataSm) }, s.dur != null ? (s.dur >= 60 ? fmtTime(s.dur) : s.dur.toFixed(1) + ' s') : '—'),
    compact ? null : h('span', { className: cx('aq-stage-g', T.dataSm) }, s.cpu ? 'CPU' : s.gb ? s.gb.toFixed(1) + ' GB' : ''),
    st === 'running' && s.deadline ? h('span', { className: 'aq-stage-dl', 'aria-label': `${s.dur} s of ${s.deadline} s deadline` }, h('span', { className: 'aq-stage-dl-t' }, h('b', { style: { width: `${Math.min(1, s.dur / s.deadline) * 100}%` } })), h('span', { className: cx(T.micro, 'aq-ink3') }, `${s.dur.toFixed(0)} s of ${s.deadline} s deadline, then fallback`)) : null,
    s.note || s.fallback ? h('span', { className: cx('aq-stage-note', T.micro) }, s.fallback ? h(Fragment, null, h(Icon, { name: 'warning' }), ` ${s.note || ''} Fallback ran: ${s.fallback}`) : s.note) : null);
}

export interface StageTimelineProps { stages: any[]; compact?: boolean; title?: string; loopFrom?: string; loopTo?: string }
/** The stage list, data-driven: any number of stages, any model names. A bracket marks stages that ran again after an answer. */
export function StageTimeline({ stages, compact, title = 'Stages', loopFrom, loopTo }: StageTimelineProps) {
  const T = useT();
  const done = stages.filter(s => s.status === 'done').length;
  const i0 = loopFrom ? stages.findIndex(s => s.id === loopFrom) : -1, i1 = loopTo ? stages.findIndex(s => s.id === loopTo) : -1;
  return h('section', { className: cx('aq-timeline', compact && 'is-compact') },
    h('div', { className: 'aq-timeline-h' }, h('span', { className: T.title }, title), h('span', { className: cx(T.micro, 'aq-ink3') }, `${done} of ${stages.length} done · real durations`)),
    h('ol', { className: 'aq-timeline-l', style: i0 >= 0 ? ({ '--loop-a': i0, '--loop-b': i1 } as any) : undefined },
      stages.map((s, i) => h(StageRow, { key: s.id, stage: s, compact, pass: i0 >= 0 && i >= i0 && i <= i1 ? 2 : undefined }))),
    i0 >= 0 ? h('div', { className: cx(T.micro, 'aq-ink3', 'aq-timeline-loop') }, h(Icon, { name: 'replay' }), ` ${stages[i0].name} to ${stages[i1].name} ran again after the answer`) : null);
}

// ---------------------------------------------------------------------------
const KIND: Record<string, [string, string]> = {
  text: ['text', 'Text read'], object: ['object', 'Objects found'], checklist: ['checklist', 'Checklist answer'], measure: ['measure', 'Scene measure'],
  sun: ['sun', 'Sun and compass'], language: ['language', 'Language vote'], neighbour: ['neighbour', 'Reference-photo neighbours'], region: ['region', 'Region estimate'],
  name: ['name', 'Name match'], contradiction: ['contradiction', 'Contradiction'],
};
export interface PolarityChipProps { name: string; pol: number }
/** Evidence → candidate: ▲ supports, ▼ contradicts, ● neutral. Glyph and word, never colour alone. */
export function PolarityChip({ name, pol }: PolarityChipProps) {
  const T = useT();
  const k = pol > 0 ? 'support' : pol < 0 ? 'contra' : 'neutral';
  return h('span', { className: cx('aq-pol', 'is-' + k, T.label), title: `${k === 'support' ? 'Supports' : k === 'contra' ? 'Contradicts' : 'Neutral on'} ${name}` }, h(Icon, { name: k }), name);
}

export interface EvidenceCardProps { e: any; names?: Record<string, string>; selected?: boolean; compact?: boolean; isNew?: boolean; crop?: any; showActor?: boolean }
/**
 * One piece of evidence, in three registers kept apart:
 * observation (bracketed, mono, what a model saw) → inference (italic serif, what follows) → estimate (≈ mono with range, what the solver takes from it).
 */
export function EvidenceCard({ e, names = {}, selected, compact, isNew, crop, showActor = true }: EvidenceCardProps) {
  const T = useT();
  const [icon, label] = KIND[e.kind] || ['info', e.kind];
  const pols = Object.entries(e.pol || {});
  const isContra = e.kind === 'contradiction';
  return h('article', { className: cx('aq-ev', 'is-' + e.kind, selected && 'is-sel', e.notVisible && 'is-nv', e.empty && 'is-empty', isNew && 'is-new', compact && 'is-compact'), 'data-link': e.id, tabIndex: 0, 'aria-label': `${label}: ${e.obs}` },
    h('header', { className: 'aq-ev-h' }, h(Icon, { name: icon }), h('span', { className: T.label }, label),
      h('span', { className: cx(T.micro, 'aq-ink3') }, e.stage), isNew ? h('span', { className: cx('aq-ev-new', T.micro) }, 'new') : null,
      h('span', { className: cx(T.dataSm, 'aq-ev-t') }, fmtTime(e.t || 0))),
    h('div', { className: 'aq-ev-obs' },
      crop || null,
      h('div', { className: 'aq-ev-obs-b' },
        h('span', { className: cx('aq-ev-reg', T.micro) }, isContra ? 'In conflict' : e.notVisible ? "Can't tell" : 'Observed'),
        h('span', { className: cx(T.data, 'aq-ev-obs-t') }, e.obs),
        e.conf != null ? h(ConfidenceMeter, { value: e.conf }) : null)),
    e.inference ? h('div', { className: 'aq-ev-inf' }, h(Icon, { name: 'infer' }), h('span', { className: T.inference }, e.inference)) : null,
    e.estimate && !compact ? h('div', { className: 'aq-ev-est' }, h(Icon, { name: 'estimate' }), h('span', { className: T.data }, `${e.estimate.label} ${fmtEst(e.estimate.v)}`), h('span', { className: cx(T.micro, 'aq-ink3') }, 'estimate, not a calibrated probability')) : null,
    pols.length && !compact ? h('div', { className: 'aq-ev-pol' }, pols.map(([k, v]) => h(PolarityChip, { key: k, name: names[k] || k, pol: v as number }))) : null,
    showActor && !compact ? h('footer', { className: 'aq-ev-f' }, h(ModelChip, { name: e.model, actor: e.actor, size: 'sm' }), e.actor === 'model' ? h('span', { className: cx(T.micro, 'aq-ink3') }, e.sub || 'local · open weights') : h('span', { className: cx(T.micro, 'aq-ink3') }, 'code, not a model')) : null);
}

// ---------------------------------------------------------------------------
export interface CorrelationBracketProps { label: string; cap?: number; note?: string; children?: any }
/** Groups evidence that shares one image encoder: drawn as one voice, with its capped combined weight. */
export function CorrelationBracket({ label, cap, note, children }: CorrelationBracketProps) {
  const T = useT();
  return h('section', { className: 'aq-corr', 'aria-label': label },
    h('div', { className: 'aq-corr-h' }, h(Icon, { name: 'bracket' }), h('span', { className: T.label }, label), cap != null ? h(Badge, { tone: 'solver' }, `weight capped at ${cap.toFixed(2)}`) : null),
    note ? h('div', { className: cx(T.micro, 'aq-ink3') }, note) : null,
    h('div', { className: 'aq-corr-b' }, children));
}

// ---------------------------------------------------------------------------
export interface CaptionBarProps { headline: string; caption: string; actor?: 'model' | 'solver' | 'team'; source?: string; t?: number; speed?: number }
/** Plain-language caption built from a template per event type, e.g. "Reading signs: a postcode in a format only Portugal uses". */
export function CaptionBar({ headline, caption, actor = 'model', source, t, speed }: CaptionBarProps) {
  const T = useT();
  return h('div', { className: 'aq-caption', role: 'status', 'aria-live': 'polite' },
    h('div', { className: 'aq-caption-l' }, h('div', { className: cx(T.headline, 'aq-caption-h') }, headline), h('div', { className: cx(T.caption, 'aq-caption-c') }, caption)),
    h('div', { className: 'aq-caption-r' }, source ? h(ModelChip, { name: source, actor, size: 'sm' }) : null,
      t != null ? h('span', { className: cx(T.data, 'aq-ink3') }, `log ${fmtTime(t)}`) : null,
      speed ? h('span', { className: cx('aq-sys is-replay', T.label) }, h(Icon, { name: 'replay' }), `${speed}×`) : null));
}
