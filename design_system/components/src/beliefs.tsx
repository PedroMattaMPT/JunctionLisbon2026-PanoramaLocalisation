import { h, Fragment, cx, useT, useDensity, fmtEst, fmtSigned } from './rt';
import { Icon } from './icons';
import { Badge, Stamp } from './base';
import { PolarityChip } from './reasoning';

// ---------------------------------------------------------------------------
export interface CandidateRowProps { c: any; selected?: boolean; max?: number; showDelta?: boolean; ghost?: boolean }
/** A candidate: rank, name, level, estimate bar with its range, change since the last update, and support/contradict counts. */
export function CandidateRow({ c, selected, max = 1, showDelta = true, ghost }: CandidateRowProps) {
  const T = useT();
  const pct = (x: number) => `${Math.min(100, (x / max) * 100)}%`;
  const d = c.delta || 0;
  return h('div', { className: cx('aq-cand', selected && 'is-sel', c.other && 'is-other', ghost && 'is-ghost'), 'data-link': c.id, tabIndex: c.other ? -1 : 0, role: 'row' },
    h('span', { className: cx('aq-cand-rank', T.data) }, c.other ? '' : c.rank),
    h('span', { className: 'aq-cand-n' }, h('span', { className: T.heading }, c.name), c.other ? null : h('span', { className: cx(T.micro, 'aq-cand-lvl') }, c.level),
      c.contradictedBy ? h('span', { className: cx(T.micro, 'aq-c-contra', 'aq-cand-x') }, h(Icon, { name: 'contra' }), ` contradicted by ${c.contradictedBy}`) : null,
      c.keptNote ? h('span', { className: cx(T.micro, 'aq-ink3', 'aq-cand-x') }, c.keptNote) : null,
      c.lookalike ? h('span', { className: cx(T.micro, 'aq-ink2', 'aq-cand-x') }, h(Icon, { name: 'neighbour' }), ' look-alike of the Alentejo montado') : null),
    h('span', { className: 'aq-cand-bar', role: 'img', 'aria-label': `estimate ${fmtEst(c.v)}${c.lo != null ? `, range ${fmtEst(c.lo)} to ${fmtEst(c.hi)}` : ''}` },
      h('b', { style: { width: pct(c.v) } }), c.lo != null ? h('em', { style: { left: pct(c.lo), width: `calc(${pct(c.hi)} - ${pct(c.lo)})` } }) : null),
    h('span', { className: cx('aq-cand-v', T.data) }, fmtEst(c.v), c.lo != null ? h('span', { className: cx(T.micro, 'aq-ink3') }, ` ${fmtEst(c.lo)}–${fmtEst(c.hi)}`) : null),
    h('span', { className: 'aq-cand-meta' },
      showDelta ? h('span', { className: cx('aq-cand-d', T.dataSm, d > 0.005 ? 'is-up' : d < -0.005 ? 'is-down' : ''), title: 'change since the last update' }, d > 0.005 ? h(Icon, { name: 'support' }) : d < -0.005 ? h(Icon, { name: 'contra' }) : null, Math.abs(d) < 0.005 ? '±0.00' : fmtSigned(d)) : null,
      c.other ? null : h('span', { className: cx('aq-cand-c', T.dataSm), title: `${c.sup} supporting, ${c.con} contradicting` }, h('span', { className: 'aq-c-support' }, h(Icon, { name: 'support' }), c.sup), h('span', { className: 'aq-c-contra' }, h(Icon, { name: 'contra' }), c.con))));
}

export interface CandidateListProps { candidates: any[]; selected?: string; title?: string; ruledOut?: any[]; showDelta?: boolean; caption?: string }
/** The ranked candidate list with "other" and the ruled-out rows underneath. Estimates, not calibrated probabilities. */
export function CandidateList({ candidates, selected, title = 'Candidates', ruledOut = [], showDelta = true, caption = 'Estimates from the solver · bar = estimate, band = range' }: CandidateListProps) {
  const T = useT();
  const max = Math.max(...candidates.map(c => c.hi || c.v));
  return h('section', { className: 'aq-cands', role: 'table', 'aria-label': title },
    h('div', { className: 'aq-cands-h' }, h('span', { className: T.title }, title), h('span', { className: cx(T.micro, 'aq-ink3') }, caption)),
    candidates.map(c => h(CandidateRow, { key: c.id, c, selected: selected === c.id, max, showDelta })),
    ruledOut.map((r, i) => h(RuledOutRow, { key: i, r })));
}

export interface RuledOutRowProps { r: { name: string; level?: string; reason: string; by?: string[] }; byLabels?: Record<string, string>; stamp?: boolean }
/** A ruled-out place stays visible: struck through, with the reason and the evidence that decided it. */
export function RuledOutRow({ r, byLabels, stamp }: RuledOutRowProps) {
  const T = useT();
  return h('div', { className: 'aq-ruled', role: 'row' },
    h(Icon, { name: 'failed', className: 'aq-c-contra' }),
    h('span', { className: 'aq-ruled-b' }, h('s', { className: T.heading }, r.name), r.level ? h('span', { className: cx(T.micro, 'aq-ink3') }, ' ' + r.level) : null,
      h('span', { className: cx(T.body, 'aq-ruled-why') }, 'Ruled out because ', h('span', { className: 'aq-ink1' }, r.reason)),
      r.by && byLabels ? h('span', { className: 'aq-ruled-by' }, r.by.map(b => h(Badge, { key: b, tone: 'contra', icon: 'contra' }, byLabels[b] || b))) : null),
    stamp ? h(Stamp, { kind: 'ruled-out' }) : null);
}

// ---------------------------------------------------------------------------
export interface FunnelProps { levels: { level: string; name: string; v: number }[]; current?: number }
/** Country → region → town → spot, each with its estimate; the map never zooms tighter than the level the evidence supports. */
export function Funnel({ levels, current }: FunnelProps) {
  const T = useT();
  const cur = current ?? levels.length - 1;
  return h('ol', { className: 'aq-funnel', 'aria-label': 'Narrowing from country to spot' }, levels.map((l, i) => h('li', { key: i, className: cx('aq-funnel-r', i === cur && 'is-cur', i > cur && 'is-later'), style: { '--w': `${100 - i * 14}%` } as any },
    h('span', { className: cx(T.micro, 'aq-funnel-lvl') }, l.level), h('span', { className: cx(T.heading, 'aq-funnel-n') }, l.name), h('span', { className: cx(T.data, 'aq-funnel-v') }, fmtEst(l.v)))));
}

// ---------------------------------------------------------------------------
export interface EvidenceMatrixProps { evidence: any[]; candidates: string[]; names: Record<string, string>; groups?: any[]; selected?: string; dense?: boolean }
/** Evidence × candidate: what supports and what contradicts each place. Correlated rows share a bracket. */
export function EvidenceMatrix({ evidence, candidates, names, groups = [], selected, dense }: EvidenceMatrixProps) {
  const T = useT();
  const inGroup = (id: string) => groups.find(g => g.members.includes(id));
  const rows = evidence.filter(e => Object.keys(e.pol || {}).length);
  const col = (k: string) => rows.reduce((a, e) => { const p = (e.pol || {})[k]; return [a[0] + (p > 0 ? 1 : 0), a[1] + (p < 0 ? 1 : 0)]; }, [0, 0]);
  return h('div', { className: cx('aq-matrix', dense && 'is-dense'), role: 'table', 'aria-label': 'Evidence by candidate' },
    h('div', { className: 'aq-mx-row aq-mx-head', role: 'row', style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
      h('span', { className: cx(T.micro, 'aq-ink3'), role: 'columnheader' }, 'Evidence'), candidates.map(k => h('span', { key: k, role: 'columnheader', className: cx(T.label, 'aq-mx-ch') }, names[k] || k))),
    rows.map((e, i) => {
      const g = inGroup(e.id); const first = g && g.members[0] === e.id;
      return h('div', { key: e.id, role: 'row', className: cx('aq-mx-row', g && 'is-grouped', first && 'is-gfirst', selected === e.id && 'is-sel'), 'data-link': e.id, style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
        h('span', { className: 'aq-mx-rh', role: 'rowheader' }, h(Icon, { name: e.kind === 'contradiction' ? 'contradiction' : ({ text: 'text', language: 'language', checklist: 'checklist', measure: 'measure', sun: 'sun', neighbour: 'neighbour', region: 'region', name: 'name', object: 'object' } as any)[e.kind] }),
          h('span', { className: cx(T.dataSm, 'aq-mx-obs') }, e.obs), g && first ? h('span', { className: cx(T.micro, 'aq-mx-g') }, g.label) : null),
        candidates.map(k => { const p = (e.pol || {})[k]; const kind = p > 0 ? 'support' : p < 0 ? 'contra' : p === 0 ? 'neutral' : 'none';
          return h('span', { key: k, role: 'cell', className: cx('aq-mx-c', 'is-' + kind), title: kind === 'none' ? 'not applicable' : `${kind} · ${names[k]}` }, kind === 'none' ? h('span', { className: 'aq-mx-dot' }) : h(Icon, { name: kind })); }));
    }),
    h('div', { className: 'aq-mx-row aq-mx-foot', role: 'row', style: { gridTemplateColumns: `minmax(0, 1fr) repeat(${candidates.length}, var(--mx-col))` } },
      h('span', { className: cx(T.micro, 'aq-ink3') }, 'Totals (correlated rows count once)'),
      candidates.map(k => { const [s, c] = col(k); return h('span', { key: k, className: cx(T.dataSm, 'aq-mx-tot') }, h('span', { className: 'aq-c-support' }, s), ' / ', h('span', { className: 'aq-c-contra' }, c)); })));
}
