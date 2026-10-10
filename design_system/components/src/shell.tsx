import { h, Fragment, cx, useT, useDensity, useState, fmtTime, fmtMult, fmtInt, MAX_SCORE } from './rt';
import { Icon } from './icons';
import { Badge, KeyCap, CostTag } from './base';
import { WORDMARK } from './wordmark-data';

// ---------------------------------------------------------------------------
export interface WordmarkProps { size?: number; mark?: boolean; title?: string }
/** "aqui" — Newsreader letters; the tittle is a point inside a broken uncertainty ring (here, ± how sure). mark=true draws only the i. */
export function Wordmark({ size = 24, mark, title = 'Aqui' }: WordmarkProps) {
  const W = WORDMARK;
  const ring = h('circle', { cx: W.cx, cy: W.cy, r: W.ring, fill: 'none', stroke: 'currentColor', strokeWidth: 52, strokeDasharray: '360 190', strokeDashoffset: 120, className: 'aq-wm-ring' });
  const dot = h('circle', { cx: W.cx, cy: W.cy, r: W.dot, className: 'aq-wm-dot' });
  if (mark) {
    return h('svg', { className: 'aq-wordmark is-mark', viewBox: '16 4 32 52', height: size, width: Math.round(size * 32 / 52), role: 'img', 'aria-label': title },
      h('rect', { x: 26.5, y: 31, width: 11, height: 24, fill: 'currentColor' }),
      h('circle', { cx: 32, cy: 17.5, r: 10, fill: 'none', strokeWidth: 4, strokeDasharray: '14 7', strokeDashoffset: 4, className: 'aq-wm-ring' }), h('circle', { cx: 32, cy: 17.5, r: 4.5, className: 'aq-wm-dot' }));
  }
  return h('svg', { className: 'aq-wordmark', viewBox: W.vb, height: size, width: Math.round(size * 4060 / 2010), role: 'img', 'aria-label': title }, h('path', { d: W.d, fill: 'currentColor' }), ring, dot);
}

// ---------------------------------------------------------------------------
export interface TimerProps { label: string; used: number; budget: number; warnAt?: number; compact?: boolean }
/** Time used against a budget. Ink until 80%, then cost colour; over budget shows how far over. */
export function Timer({ label, used, budget, warnAt = 0.8, compact }: TimerProps) {
  const T = useT();
  const frac = used / budget;
  const state = frac > 1 ? 'over' : frac >= warnAt ? 'warn' : 'ok';
  return h('div', { className: cx('aq-timer', 'is-' + state, compact && 'is-compact'), role: 'timer', 'aria-label': `${label}: ${fmtTime(used)} of ${fmtTime(budget)}` },
    h('div', { className: cx('aq-timer-l', T.micro) }, h(Icon, { name: 'clock' }), label),
    h('div', { className: 'aq-timer-v' },
      h('span', { className: T.readout }, fmtTime(used)), h('span', { className: cx(T.data, 'aq-ink3') }, ' / ' + fmtTime(budget)),
      state === 'over' ? h('span', { className: cx('aq-over', T.label) }, '+' + fmtTime(used - budget) + ' over') : null),
    h('div', { className: 'aq-timer-bar', 'aria-hidden': true }, h('span', { style: { width: `${Math.min(1, frac) * 100}%` } }), h('i', { style: { left: `${warnAt * 100}%` } })));
}

// ---------------------------------------------------------------------------
export interface MultiplierChipProps { value: number; history?: { t: number; m: number; what: string }[]; open?: boolean }
/** The running multiplier for this panorama, always on screen. Opens to its history; every step is a log event. */
export function MultiplierChip({ value, history = [], open }: MultiplierChipProps) {
  const T = useT();
  const [o, setO] = useState(!!open);
  const spent = value < 1;
  return h('div', { className: 'aq-mult-wrap' },
    h('button', { type: 'button', className: cx('aq-mult', spent && 'is-spent'), 'aria-expanded': o, onClick: () => setO(!o), title: 'Multiplier applied to every guess produced from now on' },
      h('span', { className: cx(T.micro, 'aq-mult-l') }, 'Multiplier'), h('span', { className: T.readout }, fmtMult(value)), h(Icon, { name: 'chevronDown' })),
    o ? h('div', { className: 'aq-mult-pop', role: 'dialog', 'aria-label': 'Multiplier history' },
      h('div', { className: cx(T.label, 'aq-ink2') }, 'Applies to every guess produced after it, for this panorama only'),
      h('ol', { className: 'aq-mult-list' }, history.map((e, i) => h('li', { key: i, className: T.body },
        h('span', { className: cx(T.data, 'aq-ink3') }, fmtTime(e.t)), h('span', null, e.what), h('span', { className: cx(T.data, e.m < (history[i - 1]?.m ?? 1) ? 'aq-c-cost' : 'aq-ink2') }, fmtMult(e.m)))))) : null);
}

// ---------------------------------------------------------------------------
export interface ScoreReadoutProps { expected: number; range?: [number, number]; max?: number; special?: boolean; urbanUnknown?: { urban: number; nonUrban: number }; size?: 'md' | 'xl' }
/** Expected score under current beliefs — always labelled an estimate, never a result. */
export function ScoreReadout({ expected, range, max = MAX_SCORE, special, urbanUnknown, size = 'md' }: ScoreReadoutProps) {
  const T = useT();
  const k = special ? 3 : 1;
  if (urbanUnknown) {
    return h('div', { className: 'aq-score is-split' },
      h('div', { className: cx(T.micro, 'aq-score-l') }, 'Expected score · label unknown'),
      h('div', { className: 'aq-score-two' },
        h('span', null, h('span', { className: cx(T.label, 'aq-ink3') }, 'if Urban '), h('span', { className: T.readout }, '≈ ' + fmtInt(urbanUnknown.urban * k))),
        h('span', null, h('span', { className: cx(T.label, 'aq-ink3') }, 'if non-Urban '), h('span', { className: T.readout }, '≈ ' + fmtInt(urbanUnknown.nonUrban * k)))));
  }
  return h('div', { className: cx('aq-score', size === 'xl' && 'is-xl') },
    h('div', { className: cx(T.micro, 'aq-score-l') }, special ? 'Expected score · estimate · ×3 Special One' : 'Expected score · estimate'),
    h('div', { className: 'aq-score-v' }, h('span', { className: size === 'xl' ? T.score : T.readout }, '≈\u2009' + fmtInt(expected * k)),
      h('span', { className: cx(T.data, 'aq-ink3') }, ' of ' + fmtInt(Math.floor(max * k)))),
    range ? h('div', { className: cx(T.micro, 'aq-ink3') }, `range ${fmtInt(range[0] * k)}–${fmtInt(range[1] * k)}`) : null);
}

// ---------------------------------------------------------------------------
export interface GpuMeterProps { used: number; total?: number; models?: { name: string; gb: number }[]; compact?: boolean }
/** GPU memory in GB with the resident models as segments. Warns above 14 GB of 16. */
export function GpuMeter({ used, total = 16, models, compact }: GpuMeterProps) {
  const T = useT();
  const warn = used > total * 0.875;
  return h('div', { className: cx('aq-gpu', warn && 'is-warn', compact && 'is-compact') },
    h('div', { className: cx(T.micro, 'aq-gpu-l') }, h(Icon, { name: 'gpu' }), 'GPU memory'),
    h('div', { className: 'aq-gpu-v' }, h('span', { className: T.data }, used.toFixed(1)), h('span', { className: cx(T.data, 'aq-ink3') }, ` / ${total} GB`)),
    h('div', { className: 'aq-gpu-bar', role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': total, 'aria-valuenow': used },
      models && models.length ? models.map((m, i) => h('span', { key: i, title: `${m.name} ${m.gb} GB`, style: { width: `${(m.gb / total) * 100}%` } })) : h('span', { style: { width: `${(used / total) * 100}%` } })));
}

// ---------------------------------------------------------------------------
export interface SystemBadgeProps { kind: 'worker-online' | 'worker-offline' | 'tiles-offline' | 'clean' | 'replay'; speed?: number }
/** System status in words: worker online/offline, map tiles offline, clean state verified, replay speed. */
export function SystemBadge({ kind, speed }: SystemBadgeProps) {
  const T = useT();
  const map: any = {
    'worker-online': ['online', 'GPU worker online', 'ok'], 'worker-offline': ['offline', 'GPU worker offline — answer kept', 'bad'],
    'tiles-offline': ['offline', 'Map tiles offline · outlines', 'warn'], clean: ['clean', 'Clean state verified', 'ok'],
    replay: ['replay', `Replay ${speed || 1}× · real timestamps`, 'replay'],
  };
  const [icon, text, tone] = map[kind];
  return h('span', { className: cx('aq-sys', 'is-' + tone, T.label) }, h(Icon, { name: icon }), text);
}

// ---------------------------------------------------------------------------
export interface ModelChipProps { name: string; role?: string; actor?: 'model' | 'solver' | 'team'; local?: boolean; size?: 'sm' | 'md' }
/** Who produced something. Models say "local · open weights"; the solver says "code, not a model". */
export function ModelChip({ name, role, actor = 'model', local = true, size = 'md' }: ModelChipProps) {
  const T = useT();
  const sub = actor === 'solver' ? 'code, not a model' : actor === 'team' ? 'human' : local ? 'local · open weights' : null;
  return h('span', { className: cx('aq-mchip', 'aq-actor-' + actor, 'is-' + size) },
    h(Icon, { name: actor }), h('span', { className: cx(T.label, 'aq-mchip-n') }, name),
    size === 'md' && (role || sub) ? h('span', { className: cx(T.micro, 'aq-mchip-r') }, [role, sub].filter(Boolean).join(' · ')) : null);
}

// ---------------------------------------------------------------------------
export interface ModelRosterProps { models: any[]; compact?: boolean; title?: string }
/** Every local model with its role and memory. State in words: resident, running, idle, standby (fallback). */
export function ModelRoster({ models, compact, title = 'Local models' }: ModelRosterProps) {
  const T = useT();
  const total = models.filter(m => m.state === 'resident' || m.state === 'running').reduce((a, m) => a + (m.gb || 0), 0);
  return h('div', { className: cx('aq-roster', compact && 'is-compact') },
    h('div', { className: 'aq-roster-h' }, h('span', { className: T.heading }, title), h('span', { className: cx(T.micro, 'aq-ink3') }, `all open weights · ${total.toFixed(1)} GB resident`)),
    h('ul', null, models.map(m => h('li', { key: m.id, className: cx('aq-roster-row', 'is-' + m.state) },
      h(Icon, { name: m.state === 'running' ? 'running' : m.state === 'standby' ? 'queued' : 'model', className: 'aq-roster-i' }),
      h('span', { className: 'aq-roster-n' }, h('span', { className: T.label }, m.name), compact ? null : h('span', { className: cx(T.micro, 'aq-ink3') }, m.role)),
      h('span', { className: cx(T.micro, 'aq-roster-s') }, m.state === 'standby' ? 'fallback · standby' : m.state),
      h('span', { className: cx(T.dataSm, 'aq-roster-g') }, m.cpu ? 'CPU' : m.gb ? `${m.gb.toFixed(1)} GB` : '—')))));
}

// ---------------------------------------------------------------------------
export interface CaseCardProps { label: string; status: 'waiting' | 'processing' | 'needs-answer' | 'done' | 'submitted'; special?: boolean; multiplier?: number; expected?: number; used?: number; stage?: string; elapsed?: number; current?: boolean; gain?: number }
/** A sealed case in the queue. Only status crosses between cases: no image, no date, no content. */
export function CaseCard(p: CaseCardProps) {
  const T = useT();
  const words: any = { waiting: 'Waiting', processing: 'Processing', 'needs-answer': 'Question waiting', done: 'Answer ready', submitted: 'Submitted' };
  const icon: any = { waiting: 'queued', processing: 'running', 'needs-answer': 'question', done: 'done', submitted: 'submit' };
  return h('div', { className: cx('aq-case', 'is-' + p.status, p.special && 'is-special', p.current && 'is-current'), tabIndex: 0, role: 'button', 'aria-label': `${p.label}, ${words[p.status]}` },
    h('div', { className: 'aq-case-h' }, h(Icon, { name: 'lock', className: 'aq-ink3' }), h('span', { className: T.heading }, p.label), p.special ? h(Badge, { tone: 'outline', icon: 'special' }, '×3 Special One') : null),
    h('div', { className: cx('aq-case-s', T.label) }, h(Icon, { name: icon[p.status] }), words[p.status]),
    h('div', { className: cx('aq-case-m', T.data) },
      p.status === 'processing' ? h('span', { className: 'aq-ink2' }, `${p.stage} · ${fmtTime(p.elapsed || 0)}`) : null,
      p.status === 'needs-answer' ? h('span', { className: 'aq-ink2' }, `gain +${Math.round((p.gain || 0) * 100)}% vs 5.26%`) : null,
      (p.status === 'done' || p.status === 'submitted' || p.status === 'needs-answer') && p.expected ? h('span', null, '≈ ' + fmtInt(p.expected * (p.special ? 3 : 1))) : null,
      p.multiplier != null && p.status !== 'waiting' ? h('span', { className: p.multiplier < 1 ? 'aq-c-cost' : 'aq-ink3' }, fmtMult(p.multiplier)) : null,
      p.used != null ? h('span', { className: 'aq-ink3' }, fmtTime(p.used)) : null,
      p.status === 'waiting' ? h('span', { className: 'aq-ink3' }, 'sealed until it runs') : null));
}

// ---------------------------------------------------------------------------
export interface ShortcutBarProps { keys: { k: string; label: string }[] }
/** Shortcut hints for the current mode, along the bottom of the console. */
export function ShortcutBar({ keys }: ShortcutBarProps) {
  const T = useT();
  return h('div', { className: 'aq-keys', role: 'note', 'aria-label': 'Keyboard shortcuts' }, keys.map((k, i) => h('span', { key: i, className: cx('aq-keys-i', T.micro) }, h(KeyCap, null, k.k), k.label)));
}

// ---------------------------------------------------------------------------
export interface CleanStateCheckProps { items?: { label: string; ok: boolean }[]; caseLabel?: string }
/** Shown when a case starts: proof it is sealed — new conversation, empty evidence, nothing carried over. */
export function CleanStateCheck({ items, caseLabel = 'this case' }: CleanStateCheckProps) {
  const T = useT();
  const list = items || [{ label: 'New model conversation', ok: true }, { label: 'Evidence file empty', ok: true }, { label: 'Nothing carried over from other cases', ok: true }];
  return h('div', { className: 'aq-clean', role: 'status' },
    h('div', { className: 'aq-clean-h' }, h(Icon, { name: 'clean' }), h('span', { className: T.heading }, `Clean state for ${caseLabel}`)),
    h('ul', null, list.map((it, i) => h('li', { key: i, className: cx(T.body, it.ok ? '' : 'is-bad') }, h(Icon, { name: it.ok ? 'done' : 'failed' }), it.label))));
}

// ---------------------------------------------------------------------------
export interface RunBarProps { c: any; special?: boolean; online?: boolean; tilesOffline?: boolean; replay?: number; showWordmark?: boolean }
/** The always-visible run bar: case, timers, multiplier, expected score, GPU, worker status. Built from the case's run record. */
export function RunBar({ c, special, online = true, tilesOffline, replay, showWordmark = true }: RunBarProps) {
  const T = useT();
  const r = c.run;
  const unknown = c.urban === 'unknown';
  return h('header', { className: 'aq-runbar', role: 'banner' },
    showWordmark ? h('div', { className: 'aq-runbar-wm' }, h(Wordmark, { size: useDensity() === 'stage' ? 36 : 22 })) : null,
    h('div', { className: 'aq-runbar-case' }, h('span', { className: T.heading }, c.label), special || c.special ? h(Badge, { tone: 'outline', icon: 'special' }, '×3 Special One') : null,
      h('span', { className: cx(T.micro, 'aq-ink3') }, `${c.urban === 'urban' ? 'Urban' : c.urban === 'non-urban' ? 'Non-urban' : 'Urban label unknown'} · ${c.urbanSource}`)),
    h(Timer, { label: 'This panorama', used: r.used, budget: r.budget }),
    h(Timer, { label: 'Session', used: r.session, budget: r.sessionBudget, compact: true }),
    h(MultiplierChip, { value: r.multiplier, history: c.multiplierHistory }),
    unknown ? h(ScoreReadout, { expected: r.expected, urbanUnknown: r.split }) : h(ScoreReadout, { expected: r.expected, special: special || c.special }),
    h(GpuMeter, { used: r.gpu, total: r.gpuMax, compact: true }),
    h('div', { className: 'aq-runbar-sys' }, replay ? h(SystemBadge, { kind: 'replay', speed: replay }) : h(SystemBadge, { kind: online ? 'worker-online' : 'worker-offline' }), tilesOffline ? h(SystemBadge, { kind: 'tiles-offline' }) : null));
}
