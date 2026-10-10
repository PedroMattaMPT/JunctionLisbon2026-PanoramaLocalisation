import { h, Fragment, cx, useT, useDensity, useState, fmtCoord, fmtDist, fmtMult, fmtTime, fmtInt, RANK_W, theta, MAX_SCORE } from './rt';
import { Icon } from './icons';
import { Button, Badge, Tabs, Dialog } from './base';
import { ModelChip } from './shell';

// ---------------------------------------------------------------------------
export interface CoordinateBlockProps { a: any; showCopy?: boolean; size?: 'md' | 'lg' }
/** The coordinate, once, in mono with a true minus — always with its order, uncertainty, role, method and the multiplier when produced. */
export function CoordinateBlock({ a, showCopy = true, size = 'md' }: CoordinateBlockProps) {
  const T = useT();
  return h('div', { className: cx('aq-coord', size === 'lg' && 'is-lg') },
    h('div', { className: cx(T.micro, 'aq-ink3') }, 'Latitude, longitude · WGS84'),
    h('div', { className: 'aq-coord-v' }, h('span', { className: size === 'lg' ? T.readout : T.data }, fmtCoord(a.lat, a.lng)), h('span', { className: cx(T.data, 'aq-coord-r') }, a.r == null ? '± unknown' : `± ${fmtDist(a.r)}`)),
    h('dl', { className: cx('aq-coord-meta', T.micro) },
      h('dt', null, 'source role'), h('dd', { className: 'aq-num' }, a.role), h('dt', null, 'method'), h('dd', { className: 'aq-num' }, a.method),
      h('dt', null, 'radius from'), h('dd', null, a.r == null ? 'no bound yet' : a.rSource), h('dt', null, 'multiplier when produced'), h('dd', { className: cx('aq-num', a.multiplier < 1 && 'aq-c-cost') }, fmtMult(a.multiplier))),
    showCopy ? h('div', { className: 'aq-coord-a' }, h(Button, { icon: 'copy' }, 'Copy lat, lng'), h(Button, { variant: 'quiet', icon: 'copy' }, 'Copy as JSON')) : null);
}

// ---------------------------------------------------------------------------
export interface AnswerSlotsProps { a: any; expanded?: boolean; special?: boolean; producedAt?: number }
/** Ten slots, normally one coordinate ten times: shown once with ×10 and the rank weights, expandable to the full list. */
export function AnswerSlots({ a, expanded: ex, special, producedAt = 340 }: AnswerSlotsProps) {
  const T = useT();
  const [open, setOpen] = useState(!!ex);
  return h('section', { className: cx('aq-slots', open && 'is-open') },
    h('header', { className: 'aq-slots-h' }, h('span', { className: T.heading }, 'Answer slots'), h('span', { className: cx(T.micro, 'aq-ink3') }, 'Same coordinate in all 10 — our default: the one with the highest expected score')),
    h('div', { className: 'aq-slots-once' },
      h('span', { className: cx(T.data, 'aq-slots-coord') }, fmtCoord(a.lat, a.lng)), h('span', { className: cx('aq-slots-x', T.readout) }, '×10'),
      h('span', { className: cx(T.micro, 'aq-ink2') }, `each at ${fmtMult(a.multiplier)} · ${a.method}`)),
    h('div', { className: 'aq-slots-w', role: 'img', 'aria-label': 'Rank weights 1.00 to 0.63' }, RANK_W.map((w, i) => h('span', { key: i, className: 'aq-slots-wi' }, h('i', { style: { height: `${w * 100}%` } }), h('b', { className: T.dataSm }, w.toFixed(2))))),
    h('button', { type: 'button', className: cx('aq-slots-toggle', T.label), 'aria-expanded': open, onClick: () => setOpen(!open) }, h(Icon, { name: open ? 'chevronDown' : 'chevronRight' }), open ? 'Hide the 10 rows' : 'Show all 10 rows'),
    open ? h('table', { className: cx('aq-slots-table', T.dataSm) },
      h('thead', null, h('tr', null, ['Slot', 'Latitude, longitude', 'Rank weight', 'Penalty snapshot', 'Produced'].map(x => h('th', { key: x, className: T.micro }, x)))),
      h('tbody', null, RANK_W.map((w, i) => h('tr', { key: i }, h('td', null, i + 1), h('td', null, fmtCoord(a.lat, a.lng)), h('td', null, w.toFixed(2)), h('td', { className: a.multiplier < 1 ? 'aq-c-cost' : '' }, fmtMult(a.multiplier)), h('td', { className: 'aq-ink3' }, fmtTime(producedAt)))))) : null);
}

// ---------------------------------------------------------------------------
export interface ChoiceNoteProps { a: any; mostLikelyName?: string; mostLikelyExpected?: number }
/** Says why the chosen coordinate differs from the most likely candidate — or that it doesn't. */
export function ChoiceNote({ a, mostLikelyName, mostLikelyExpected }: ChoiceNoteProps) {
  const T = useT();
  return h('div', { className: cx('aq-choice', a.mostLikely ? 'is-same' : 'is-diff') },
    h(Icon, { name: a.mostLikely ? 'done' : 'info' }),
    a.mostLikely ? h('div', { className: T.body }, `Chosen coordinate is the most likely candidate${mostLikelyName ? ' (' + mostLikelyName + ')' : ''}.`)
      : h('div', { className: 'aq-choice-b' }, h('div', { className: T.heading }, 'Why not the most likely spot'), h('div', { className: cx(T.body, 'aq-ink2') }, a.why),
        mostLikelyExpected ? h('div', { className: cx('aq-choice-cmp', T.data) }, h('span', null, `${mostLikelyName}: ≈ ${fmtInt(mostLikelyExpected)}`), h('span', { className: 'aq-c-solver' }, `chosen: ≈ ${fmtInt(a.expected)}`)) : null));
}

// ---------------------------------------------------------------------------
export interface ScoreCurveProps { urban?: 'urban' | 'non-urban' | 'unknown'; band?: [number, number]; expected?: number | { urban: number; nonUrban: number }; width?: number; height?: number; multiplier?: number }
/** θ against distance on a log axis (10 m – 100 km), both curves, marks at 25 m, 100 m, 1 km, 5 km, 10 km, and the current uncertainty band. */
export function ScoreCurve({ urban = 'urban', band, expected, width, height, multiplier = 1 }: ScoreCurveProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const W = width || (stage ? 900 : 420), H = height || (stage ? 380 : 200);
  const m = { l: stage ? 70 : 40, r: 14, t: 14, b: stage ? 52 : 30 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const lx = (d: number) => m.l + (Math.log10(d) - 1) / 4 * iw; // 10 m .. 100 km
  const ly = (k: number) => m.t + (1 - k) * ih; // share kept 0..1
  const curve = (u: boolean) => { const pts: string[] = []; for (let e = 1; e <= 5.0001; e += 0.02) { const d = Math.pow(10, e); pts.push(`${lx(d).toFixed(1)},${ly(theta(d, u) / 2).toFixed(1)}`); } return pts.join(' '); };
  const marks = [25, 100, 1000, 5000, 10000];
  const showU = true, showN = true;
  const els: any[] = [];
  [0, 0.25, 0.5, 0.75, 1].forEach(k => { els.push(h('line', { key: 'g' + k, x1: m.l, x2: W - m.r, y1: ly(k), y2: ly(k), className: 'aq-sc-grid' })); els.push(h('text', { key: 'gt' + k, x: m.l - 6, y: ly(k) + 4, textAnchor: 'end', className: 'aq-sc-tick' }, `${k * 100}%`)); });
  [10, 100, 1000, 10000, 100000].forEach(d => els.push(h('text', { key: 'x' + d, x: lx(d), y: H - m.b + (stage ? 26 : 16), textAnchor: 'middle', className: 'aq-sc-tick' }, fmtDist(d))));
  marks.forEach(d => els.push(h('line', { key: 'm' + d, x1: lx(d), x2: lx(d), y1: m.t, y2: H - m.b, className: 'aq-sc-mark' })));
  if (band) els.push(h('rect', { key: 'band', x: lx(Math.max(10, band[0])), y: m.t, width: Math.max(3, lx(Math.max(10.5, band[1])) - lx(Math.max(10, band[0]))), height: ih, className: 'aq-sc-band' }));
  if (showN) els.push(h('polyline', { key: 'n', points: curve(false), className: cx('aq-sc-line is-n', urban === 'urban' && 'is-faint') }));
  if (showU) els.push(h('polyline', { key: 'u', points: curve(true), className: cx('aq-sc-line is-u', urban === 'non-urban' && 'is-faint') }));
  if (showU) els.push(h('text', { key: 'ul', x: lx(300) + 6, y: ly(theta(300, true) / 2) - 6, className: 'aq-sc-lab' }, 'Urban'));
  if (showN) els.push(h('text', { key: 'nl', x: lx(30000) + 6, y: ly(theta(30000, false) / 2) - 6, className: 'aq-sc-lab' }, 'non-Urban'));
  els.push(h('line', { key: 'ax', x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, className: 'aq-sc-axis' }));
  const exp = expected == null ? null : typeof expected === 'number' ? h('div', { className: 'aq-sc-exp' }, h('span', { className: cx(T.micro, 'aq-ink3') }, 'Expected score · estimate'), h('span', { className: cx(T.readout, 'aq-c-solver') }, `≈ ${fmtInt(expected)}`), h('span', { className: cx(T.data, 'aq-ink3') }, `of ${fmtInt(Math.floor(MAX_SCORE))}`), multiplier < 1 ? h('span', { className: cx(T.dataSm, 'aq-c-cost') }, `includes ${fmtMult(multiplier)}`) : null)
    : h('div', { className: 'aq-sc-exp' }, h('span', { className: cx(T.micro, 'aq-ink3') }, 'Urban label unknown · both scenarios'), h('span', { className: cx(T.readout, 'aq-c-solver') }, `≈ ${fmtInt(expected.urban)}`), h('span', { className: cx(T.micro, 'aq-ink2') }, 'if Urban'), h('span', { className: cx(T.readout, 'aq-c-solver') }, `≈ ${fmtInt(expected.nonUrban)}`), h('span', { className: cx(T.micro, 'aq-ink2') }, 'if non-Urban'));
  return h('figure', { className: 'aq-sc' },
    h('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': 'Share of the slot score kept against distance error' }, els),
    h('figcaption', { className: 'aq-sc-cap' }, exp, h('span', { className: cx(T.micro, 'aq-ink3') }, `Share of 1000 × θ kept per slot · band = current uncertainty${band ? ` (${fmtDist(band[0])}–${fmtDist(band[1])})` : ''} · under 10 m counts as 0`)));
}

// ---------------------------------------------------------------------------
const TYPE_ICON: Record<string, string> = { 'run.started': 'play', 'run.finished': 'done', 'stage.started': 'running', 'stage.finished': 'done', 'stage.skipped': 'skipped', 'stage.failed': 'failed', 'stage.timed_out': 'timeout', 'evidence.added': 'plus', 'candidates.updated': 'solver', 'question.asked': 'question', 'question.answered': 'team', 'question.skipped': 'skip', 'cue.sent': 'cue', 'output.produced': 'pin' };
export interface EventLogProps { events: any[]; filter?: string; json?: number; height?: number; current?: number }
/** The JSON event log as a readable list; everything on screen derives from it. One row can expand to its raw JSON. */
export function EventLog({ events, filter = 'all', json, height, current }: EventLogProps) {
  const T = useT();
  const shown = events.filter(e => filter === 'all' || e.actor === filter);
  return h('section', { className: 'aq-log' },
    h(Tabs, { tabs: [{ id: 'all', label: 'All', count: events.length }, { id: 'model', label: 'Models', icon: 'model' }, { id: 'solver', label: 'Solver', icon: 'solver' }, { id: 'team', label: 'Team', icon: 'team' }], value: filter, label: 'Filter by actor' }),
    h('ol', { className: 'aq-log-l', style: height ? { maxHeight: height } : undefined }, shown.map((e, i) => h('li', { key: i, className: cx('aq-log-r', 'aq-actor-' + e.actor, current != null && e.t > current && 'is-future', current != null && Math.abs(e.t - current) < 0.01 && 'is-now') },
      h('span', { className: cx(T.dataSm, 'aq-ink3') }, fmtTime(e.t)), h(Icon, { name: TYPE_ICON[e.type] || 'info', className: 'aq-log-i' }),
      h('span', { className: cx(T.dataSm, 'aq-log-type') }, e.type), h('span', { className: cx(T.body, 'aq-log-text') }, e.text),
      json === i ? h('pre', { className: cx('aq-log-json', T.dataSm) }, JSON.stringify({ run_id: 'r-07', t: e.t, type: e.type, stage: e.stage, actor: e.actor, model: e.model, payload: { text: e.text } }, null, 1)) : null))));
}

// ---------------------------------------------------------------------------
export interface ReplayScrubberProps { events: any[]; t: number; duration: number; speed?: 1 | 2 | 5; playing?: boolean }
/** Scrubber over the event log. Ticks are real events (shape = actor); the speed badge is always visible; timestamps stay real. */
export function ReplayScrubber({ events, t, duration, speed = 1, playing = false }: ReplayScrubberProps) {
  const T = useT();
  const x = (s: number) => `${(s / duration) * 100}%`;
  return h('div', { className: 'aq-scrub' },
    h('div', { className: 'aq-scrub-ctl' },
      h(Button, { variant: 'quiet', icon: 'back', title: 'Previous event' }, ''), h(Button, { variant: 'secondary', icon: playing ? 'pause' : 'play', shortcut: 'Space' }, playing ? 'Pause' : 'Play'), h(Button, { variant: 'quiet', icon: 'forward', title: 'Next event' }, ''),
      h('div', { className: 'aq-seg', role: 'radiogroup', 'aria-label': 'Replay speed' }, [1, 2, 5].map(s => h('button', { key: s, type: 'button', role: 'radio', 'aria-checked': s === speed, className: cx('aq-seg-o', T.label, s === speed && 'is-on') }, `${s}×`))),
      h('span', { className: cx('aq-sys is-replay', T.label) }, h(Icon, { name: 'replay' }), `Replay ${speed}×`),
      h('span', { className: cx(T.data, 'aq-scrub-time') }, fmtTime(t), h('span', { className: 'aq-ink3' }, ` / ${fmtTime(duration)} · real timestamps`))),
    h('div', { className: 'aq-scrub-track', role: 'slider', 'aria-valuemin': 0, 'aria-valuemax': duration, 'aria-valuenow': t, tabIndex: 0 },
      h('b', { style: { width: x(t) } }),
      events.map((e, i) => h('i', { key: i, className: cx('aq-scrub-tick', 'is-' + e.actor), style: { left: x(e.t) }, title: `${fmtTime(e.t)} ${e.type}` })),
      h('span', { className: 'aq-scrub-head', style: { left: x(t) } })),
    h('div', { className: cx('aq-scrub-legend', T.micro) }, h('span', null, h('i', { className: 'aq-scrub-tick is-model' }), 'model'), h('span', null, h('i', { className: 'aq-scrub-tick is-solver' }), 'solver'), h('span', null, h('i', { className: 'aq-scrub-tick is-team' }), 'team')));
}

// ---------------------------------------------------------------------------
export interface ExportBarProps { confirm?: boolean; submitted?: boolean; a?: any }
/** Copy, export and submit. Submit asks once more and restates what will be sent. */
export function ExportBar({ confirm, submitted, a }: ExportBarProps) {
  const T = useT();
  return h('div', { className: 'aq-export' },
    h('div', { className: 'aq-export-row' }, h(Button, { icon: 'copy' }, 'Copy lat, lng'), h(Button, { icon: 'download' }, 'Export JSON log'),
      submitted ? h(Badge, { tone: 'team', icon: 'submit', solid: true }, 'Submitted 05:52') : h(Button, { variant: 'primary', icon: 'submit', shortcut: '⇧⏎' }, 'Submit answer')),
    confirm && a ? h(Dialog, { title: 'Submit this answer?', inline: true, actions: h(Fragment, null, h(Button, { variant: 'quiet' }, 'Go back'), h(Button, { variant: 'primary', icon: 'submit' }, 'Submit')) },
      h('div', { className: T.body }, 'Sends 10 slots of ', h('span', { className: cx(T.data, 'aq-ink1') }, fmtCoord(a.lat, a.lng)), ` (lat, lng), produced at ${fmtMult(a.multiplier)}.`),
      h('div', { className: T.body }, 'After submitting, this case is locked; the log is exported with it.')) : null);
}
