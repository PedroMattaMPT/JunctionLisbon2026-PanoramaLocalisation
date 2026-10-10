import { h, Fragment, cx, useT, useDensity, useState, fmtMult, fmtCoord, fmtEst, fmtPct, fmtTime } from './rt';
import { Icon } from './icons';
import { Button, KeyCap, Badge, CostTag } from './base';
import { ModelChip } from './shell';
import { GainMeter, EstimateBars } from './charts';
import { PolarityChip } from './reasoning';

// ---------------------------------------------------------------------------
export interface QuestionOptionProps { o: any; state?: 'open' | 'chosen' | 'other' | 'skipped'; evidence?: any[]; cost?: number; hover?: boolean; showLinks?: boolean; brief?: boolean }
/** One option: key, label, one-line reason, evidence chips, representative point (never a camera position) and outbound links. */
export function QuestionOption({ o, state = 'open', evidence = [], cost = 0.95, hover, showLinks = true, brief }: QuestionOptionProps) {
  const T = useT();
  const k = o.key.toLowerCase();
  const chips = (o.chips || []).map((id: string) => evidence.find(e => e.id === id)).filter(Boolean);
  const pt = o.point;
  return h('div', { className: cx('aq-qopt', 'is-' + k, 'is-' + state, hover && 'is-hover'), role: 'radio', 'aria-checked': state === 'chosen', tabIndex: 0 },
    h('span', { className: cx('aq-qopt-key', T.data) }, o.key),
    h('div', { className: 'aq-qopt-b' },
      h('div', { className: cx(T.heading, 'aq-qopt-l') }, o.label, state === 'chosen' ? h(Badge, { tone: 'team', icon: 'team' }, 'Team answer') : null),
      h('div', { className: cx(T.body, 'aq-ink2') }, o.reason),
      chips.length ? h('div', { className: 'aq-qopt-chips' }, chips.map((e: any) => h('span', { key: e.id, className: cx('aq-qchip', T.micro) }, h(Icon, { name: 'support' }), h('span', { className: 'aq-num' }, e.obs.length > 28 ? e.obs.slice(0, 27) + '…' : e.obs)))) : null,
      brief ? null : pt ? h('div', { className: cx('aq-qopt-pt', T.micro) }, h(Icon, { name: 'crosshair' }), h('span', { className: cx(T.dataSm, 'aq-ink2') }, fmtCoord(pt[0], pt[1])), h('span', { className: 'aq-ink3' }, 'not a camera position'),
        showLinks ? h('span', { className: 'aq-qopt-links' }, ['OSM', 'Google Maps', 'Street View'].map(l => h('a', { key: l, href: '#', onClick: (e: any) => e.preventDefault() }, l, h(Icon, { name: 'link' })))) : null)
        : o.none ? h('div', { className: cx('aq-qopt-pt', T.micro, 'aq-ink3') }, 'Exists only because the agent made it an option.') : null),
    h('div', { className: 'aq-qopt-act' }, state === 'open' ? h(Fragment, null, h(KeyCap, null, String('ABCD'.indexOf(o.key) + 1)), h(CostTag, { multiplier: cost })) : null));
}

export interface QuestionCardProps { q: any; evidence?: any[]; state?: 'open' | 'answered' | 'skipped'; cueLine?: boolean; hoverKey?: string; number?: number; brief?: boolean }
/** The agent's question: up to four options, the expected gain against the break-even, the cost on every answer, and a free Skip that changes nothing. */
export function QuestionCard({ q, evidence = [], state = 'open', cueLine, hoverKey, number = 1, brief }: QuestionCardProps) {
  const T = useT();
  return h('section', { className: cx('aq-q', 'is-' + state), 'aria-label': `Question ${number}: ${q.text}` },
    h('header', { className: 'aq-q-h' },
      h('div', { className: 'aq-q-meta' }, h('span', { className: cx(T.label, 'aq-ink2') }, `Question ${number}`), h(ModelChip, { name: 'chosen by the solver', actor: 'solver', size: 'sm' }), h(ModelChip, { name: `worded by ${q.wordedBy}`, actor: 'model', size: 'sm' })),
      h('nav', { className: cx('aq-crumbs', T.micro), 'aria-label': 'Scope' }, h('span', { className: 'aq-ink3' }, 'Scope'), q.scope.map((s: string, i: number) => h(Fragment, { key: i }, i ? h(Icon, { name: 'chevronRight' }) : null, h('span', { className: i === q.scope.length - 1 ? 'aq-ink1' : 'aq-ink2' }, s)))),
      h('h3', { className: cx(T.title, 'aq-q-t') }, q.text)),
    state === 'open' ? h(GainMeter, { gain: q.gain, breakEven: q.breakEven, cueLine }) : null,
    h('div', { className: 'aq-q-opts', role: 'radiogroup', 'aria-label': 'Options' }, q.options.map((o: any) => h(QuestionOption, {
      key: o.key, o, evidence, cost: q.cost, hover: hoverKey === o.key,
      state: state === 'answered' ? (q.answer === o.key ? 'chosen' : 'other') : state === 'skipped' ? 'skipped' : 'open', showLinks: state === 'open' && !brief, brief,
    }))),
    state === 'open' ? h('footer', { className: 'aq-q-f' },
      h('div', { className: 'aq-q-cost' }, h(Icon, { name: 'cost' }), h('span', { className: T.body }, 'Any answer costs ', h('b', { className: 'aq-c-cost aq-num' }, fmtMult(q.cost)), ' on every guess after it, right or wrong.')),
      h('div', { className: 'aq-q-actions' },
        h(Button, { variant: 'skip', icon: 'skip', shortcut: 'S' }, 'Skip'),
        h('span', { className: cx(T.micro, 'aq-ink3', 'aq-q-skipnote') }, 'Changes nothing. Not read as “no” or “none of these”.'),
        brief ? null : h('span', { className: 'aq-q-share' }, h(Button, { variant: 'quiet', icon: 'copy' }, 'Copy all links'), h(Button, { variant: 'quiet', icon: 'qr' }, 'QR for a phone')))) : null);
}

// ---------------------------------------------------------------------------
export interface AnswerReceiptProps { kind: 'answered' | 'skipped'; q: any; before: any[]; after?: any[]; multiplierBefore: number; multiplierAfter?: number; t?: number }
/** What changed after the team's response. Answered: beliefs move and the multiplier ticks down. Skipped: nothing moves, and it says so. */
export function AnswerReceipt({ kind, q, before, after, multiplierBefore, multiplierAfter, t }: AnswerReceiptProps) {
  const T = useT();
  const opt = q.options.find((o: any) => o.key === q.answer);
  const rows = (after || before).map((r: any) => ({ name: r.name, v: r.v, before: (before.find((b: any) => b.id === r.id) || {}).v, other: r.other, note: r.keptNote }));
  return h('section', { className: cx('aq-receipt', 'is-' + kind), role: 'status' },
    h('header', { className: 'aq-receipt-h' },
      kind === 'answered' ? h(Fragment, null, h(ModelChip, { name: 'Team', actor: 'team', size: 'sm' }), h('span', { className: T.heading }, `Answered ${q.answer} · ${opt?.label}`))
        : h(Fragment, null, h(Icon, { name: 'skip' }), h('span', { className: T.heading }, 'Skipped · free')),
      t != null ? h('span', { className: cx(T.dataSm, 'aq-ink3', 'aq-receipt-t') }, fmtTime(t)) : null),
    kind === 'answered'
      ? h('div', { className: 'aq-receipt-m' }, h('span', { className: cx(T.label, 'aq-ink2') }, 'Multiplier'), h('span', { className: cx(T.readout, 'aq-ink3') }, fmtMult(multiplierBefore)), h(Icon, { name: 'chevronRight' }), h('span', { className: cx(T.readout, 'aq-c-cost') }, fmtMult(multiplierAfter!)), h('span', { className: cx(T.micro, 'aq-ink3') }, 'applies to every guess produced from now on'))
      : h('div', { className: 'aq-receipt-m' }, h('span', { className: cx(T.label, 'aq-ink2') }, 'Multiplier'), h('span', { className: T.readout }, fmtMult(multiplierBefore)), h('span', { className: cx(T.micro, 'aq-ink2') }, 'unchanged')),
    h(EstimateBars, { rows: kind === 'answered' ? rows : rows.map((r: any) => ({ ...r, before: r.v })), mode: 'beforeAfter', title: kind === 'answered' ? 'Estimates before (dashed) and after' : 'Estimates — exactly as before', tone: 'solver' }),
    kind === 'skipped' ? h('ul', { className: cx('aq-receipt-list', T.body) },
      h('li', null, h(Icon, { name: 'done' }), 'Beliefs unchanged; no candidate moved'), h('li', null, h(Icon, { name: 'done' }), 'Logged as “skipped” — not as “no” or “none of these”'), h('li', null, h(Icon, { name: 'done' }), 'No cost: multiplier stays ', h('span', { className: 'aq-num' }, fmtMult(multiplierBefore))))
      : h('div', { className: cx(T.micro, 'aq-ink3') }, 'Ruled-down candidates stay in the list with a small estimate, in case the answer was wrong.'));
}

// ---------------------------------------------------------------------------
const GAZ = ['porto', 'lisboa', 'lisbon', 'douro', 'gaia', 'ribeira', 'alentejo', 'évora', 'evora', 'nazaré', 'nazare', 'galicia', 'madrid', 'paris', 'extremadura', 'braga', 'sintra'];
const HINTS: [RegExp, string][] = [[/big[- ]wave surf/i, 'hints at Nazaré'], [/port wine|cellars/i, 'hints at Porto / Gaia'], [/tram 28/i, 'hints at Lisbon'], [/camino|pilgrim/i, 'hints at Santiago']];
const COORD = /-?\d{1,2}\.\d{2,}\s*,\s*-?\d{1,3}\.\d{2,}/;
export function checkCue(text: string) {
  const flags: { term: string; why: string }[] = [];
  for (const w of GAZ) { const m = new RegExp(`\\b${w}\\b`, 'i').exec(text); if (m) flags.push({ term: m[0], why: 'names a place' }); }
  for (const [re, why] of HINTS) { const m = re.exec(text); if (m) flags.push({ term: m[0], why }); }
  const c = COORD.exec(text); if (c) flags.push({ term: c[0], why: 'looks like coordinates' });
  return flags;
}
export interface CueComposerProps { text?: string; confirm?: boolean; max?: number; sent?: boolean }
/** Free-text cue to the agent: counter, ×0.8 cost before sending, a check that blocks place names, hints and coordinates, then a confirm step. */
export function CueComposer({ text: init = '', confirm, max = 1000, sent }: CueComposerProps) {
  const T = useT();
  const [text, setText] = useState(init);
  const flags = checkCue(text);
  const n = text.length;
  const state = sent ? 'sent' : flags.length ? 'flagged' : n === 0 ? 'empty' : confirm ? 'confirm' : 'ready';
  return h('section', { className: cx('aq-cue', 'is-' + state) },
    h('header', { className: 'aq-cue-h' }, h(Icon, { name: 'cue' }), h('span', { className: T.heading }, 'Cue to the agent'), h(CostTag, { multiplier: 0.8 }), h('span', { className: cx(T.micro, 'aq-ink3') }, 'pays off only above +25% expected gain')),
    h('div', { className: 'aq-cue-field' },
      h('textarea', { className: T.body, value: text, maxLength: max, rows: 3, 'aria-label': 'Cue text', placeholder: 'Describe what you see, without naming or hinting at a place. Example: “the wall tiles are glazed and mostly blue on white”.', onChange: (e: any) => setText(e.target.value) }),
      h('div', { className: cx('aq-cue-count', T.dataSm, n > max * 0.9 && 'is-near') }, `${n} / ${max}`)),
    flags.length ? h('ul', { className: cx('aq-cue-flags', T.body) }, flags.map((f, i) => h('li', { key: i }, h(Icon, { name: 'warning' }), h('b', { className: 'aq-num' }, `“${f.term}”`), ` ${f.why}. Cues must not name or hint at any place.`))) :
      n ? h('div', { className: cx('aq-cue-ok', T.micro) }, h(Icon, { name: 'done' }), 'No place names, hints or coordinates found') : null,
    state === 'confirm' ? h('div', { className: 'aq-cue-confirm', role: 'alertdialog' }, h('span', { className: T.body }, 'Send this cue? Every guess after it is multiplied by ', h('b', { className: 'aq-c-cost aq-num' }, '×0.8'), '.'), h(Button, { variant: 'quiet' }, 'Keep editing'), h(Button, { variant: 'primary', cost: 0.8 }, 'Send cue')) :
      sent ? h('div', { className: cx('aq-cue-ok', T.body) }, h(Icon, { name: 'done' }), 'Sent at 04:12 · logged · multiplier now ', h('b', { className: 'aq-c-cost aq-num' }, '×0.76')) :
      h('div', { className: 'aq-cue-a' }, h(Button, { variant: 'secondary', icon: 'cue', cost: 0.8, disabled: state !== 'ready' }, 'Review and send')));
}
