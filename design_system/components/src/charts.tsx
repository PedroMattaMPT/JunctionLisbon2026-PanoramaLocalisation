import { h, Fragment, cx, useT, useDensity, fmtEst, fmtPct, fmtSigned } from './rt';
import { Icon } from './icons';

// ---------------------------------------------------------------------------
export interface ConfidenceMeterProps { value?: number | null; level?: 'high' | 'med' | 'low' | 'unknown'; showValue?: boolean }
/** Three cells + a word. Unknown is dashed and says "unknown" — never drawn as low. */
export function ConfidenceMeter({ value, level, showValue = true }: ConfidenceMeterProps) {
  const T = useT();
  const lv = level || (value == null ? 'unknown' : value >= 0.8 ? 'high' : value >= 0.5 ? 'med' : 'low');
  const n = { high: 3, med: 2, low: 1, unknown: 0 }[lv];
  const word = { high: 'high', med: 'medium', low: 'low', unknown: 'unknown' }[lv];
  return h('span', { className: cx('aq-conf', 'is-' + lv), title: `Confidence ${word}${value != null ? ' · ' + fmtEst(value) : ''}` },
    h('span', { className: 'aq-conf-cells', 'aria-hidden': true }, [0, 1, 2].map(i => h('i', { key: i, className: i < n ? 'is-on' : '' }))),
    showValue && value != null ? h('span', { className: T.dataSm }, fmtEst(value)) : null,
    h('span', { className: cx(T.micro, 'aq-conf-w') }, word));
}

// ---------------------------------------------------------------------------
export interface StackedBarProps { parts: { id: string; label?: string; v: number; color?: string; hatch?: boolean }[]; caption?: string; height?: number; labelMin?: number; title?: string }
/** One 100% bar, 2px gaps between segments, every segment labelled (inline when it fits, else in the legend). */
export function StackedBar({ parts, caption, height, labelMin = 0.09, title }: StackedBarProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const total = parts.reduce((a, p) => a + p.v, 0) || 1;
  const hh = height || (stage ? 36 : 18);
  return h('figure', { className: 'aq-stack' },
    title ? h('figcaption', { className: cx(T.label, 'aq-stack-t') }, title) : null,
    h('div', { className: 'aq-stack-bar', style: { height: hh }, role: 'img', 'aria-label': parts.map(p => `${p.label || p.id} ${fmtPct(p.v / total)}`).join(', ') },
      parts.filter(p => p.v > 0).map(p => h('span', { key: p.id, className: cx('aq-stack-seg', p.hatch && 'is-hatch'), style: { flexGrow: p.v / total, background: p.color } },
        p.v / total >= labelMin ? h('b', { className: T.dataSm }, `${p.label || p.id} ${Math.round((p.v / total) * 100)}`) : null))),
    h('ul', { className: cx('aq-stack-legend', T.micro) }, parts.map(p => h('li', { key: p.id, className: p.v === 0 ? 'is-zero' : '' }, h('i', { style: { background: p.color }, className: p.hatch ? 'is-hatch' : '' }), h('span', null, p.label || p.id), h('span', { className: 'aq-num' }, p.v.toFixed(2))))),
    caption ? h('div', { className: cx(T.micro, 'aq-ink3') }, caption) : null);
}

export interface LanguageVoteProps { votes: { id: string; v: number }[]; voters?: number }
/** The language vote: one stacked bar across pt / gl / es / ca / eu / fr. Identity by label; the model hue alternates in two steps. */
export function LanguageVote({ votes, voters = 3 }: LanguageVoteProps) {
  const parts = votes.map((x, i) => ({ id: x.id, v: x.v, color: i % 2 ? 'var(--model-soft)' : 'var(--model)' }));
  return h(StackedBar, { parts, title: `Language vote · ${voters} voters`, caption: 'Share of votes, not a probability of country' });
}

const SEG_COL: Record<string, string> = { sky: 'var(--seg-sky)', building: 'var(--seg-building)', grass: 'var(--seg-grass)', tree: 'var(--seg-tree)', road: 'var(--seg-road)', water: 'var(--seg-water)', ground: 'var(--seg-ground)', masked: 'var(--seg-masked)' };
const SEG_ORDER = ['sky', 'building', 'grass', 'tree', 'road', 'water', 'ground', 'masked'];
export interface SceneSharesProps { shares: { id: string; v: number }[]; masked?: number }
/** Scene shares from segmentation: visible share of the image, not land cover. */
export function SceneShares({ shares, masked = 0 }: SceneSharesProps) {
  const map: any = Object.fromEntries(shares.map(s => [s.id, s.v]));
  if (masked) map.masked = masked;
  const parts = SEG_ORDER.filter(k => map[k] != null).map(k => ({ id: k, label: k, v: map[k], color: SEG_COL[k], hatch: k === 'masked' }));
  return h(StackedBar, { parts, title: 'Scene shares (EoMT-L)', caption: 'visible share, not land cover', labelMin: 0.12 });
}

// ---------------------------------------------------------------------------
export interface CompassDialProps { yawToBearing: number | null; err?: number; sun?: { azimuth: number; elevation: number }; water?: number; size?: number; viewYaw?: number }
/** Image yaw 0, true north, the sun's azimuth and elevation, and the error of the fix. North unknown draws no N. */
export function CompassDial({ yawToBearing, err = 0, sun, water, size, viewYaw }: CompassDialProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const S = size || (stage ? 300 : 168); const c = S / 2, R = S / 2 - (stage ? 34 : 20);
  const pt = (bearing: number, r: number) => [c + Math.sin(bearing * Math.PI / 180) * r, c - Math.cos(bearing * Math.PI / 180) * r];
  const known = yawToBearing != null;
  const els: any[] = [h('circle', { key: 'ring', cx: c, cy: c, r: R, className: 'aq-dial-ring' })];
  for (let b = 0; b < 360; b += 15) { const [x1, y1] = pt(b, R); const [x2, y2] = pt(b, R - (b % 90 === 0 ? 10 : 5)); els.push(h('line', { key: 't' + b, x1, y1, x2, y2, className: b % 90 === 0 ? 'aq-dial-major' : 'aq-dial-minor' })); }
  if (known) {
    ['N', 'E', 'S', 'W'].forEach((l, i) => { const [x, y] = pt(i * 90, R + (stage ? 18 : 11)); els.push(h('text', { key: l, x, y: y + (stage ? 7 : 4), textAnchor: 'middle', className: cx('aq-dial-card', l === 'N' && 'is-n') }, l)); });
    // error wedge around the image's yaw-0 direction
    const y0 = yawToBearing!; const a1 = y0 - err, a2 = y0 + err; const [x1, y1] = pt(a1, R - 12), [x2, y2] = pt(a2, R - 12);
    els.push(h('path', { key: 'err', d: `M${c} ${c}L${x1} ${y1}A${R - 12} ${R - 12} 0 0 1 ${x2} ${y2}Z`, className: 'aq-dial-err' }));
    const [ax, ay] = pt(y0, R - 14); els.push(h('line', { key: 'yaw0', x1: c, y1: c, x2: ax, y2: ay, className: 'aq-dial-yaw' }));
    els.push(h('text', { key: 'yaw0t', x: ax, y: ay - 4, textAnchor: 'middle', className: 'aq-dial-lab' }, 'yaw 0'));
    if (sun) { const [sx, sy] = pt(sun.azimuth, R - 12 - (R - 24) * (sun.elevation / 90)); els.push(h('g', { key: 'sun', className: 'aq-dial-sun' }, h('circle', { cx: sx, cy: sy, r: stage ? 9 : 5 }), h('line', { x1: c, y1: c, x2: sx, y2: sy }))); }
    if (water != null) { const [wx, wy] = pt(water, R - 4); els.push(h('g', { key: 'w', className: 'aq-dial-water' }, h('circle', { cx: wx, cy: wy, r: stage ? 6 : 3.5 }))); }
    if (viewYaw != null) { const [vx, vy] = pt(viewYaw + y0, R - 4); els.push(h('line', { key: 'v', x1: c, y1: c, x2: vx, y2: vy, className: 'aq-dial-view' })); }
  } else {
    els.push(h('text', { key: 'q', x: c, y: c + 4, textAnchor: 'middle', className: 'aq-dial-lab' }, 'north unknown'));
    const [ax, ay] = pt(0, R - 14); els.push(h('line', { key: 'yaw0', x1: c, y1: c, x2: ax, y2: ay, className: 'aq-dial-yaw is-unknown' }));
  }
  els.push(h('circle', { key: 'c', cx: c, cy: c, r: 2.5, className: 'aq-dial-c' }));
  return h('figure', { className: 'aq-dial' },
    h('svg', { viewBox: `0 0 ${S} ${S}`, width: S, height: S, role: 'img', 'aria-label': known ? `Image yaw 0 points to bearing ${yawToBearing}° ± ${err}°` : 'North unknown' }, els),
    h('figcaption', { className: cx('aq-dial-cap') },
      known ? h(Fragment, null, h('div', { className: T.data }, `yaw 0 at ${yawToBearing}° ± ${err}°`),
        sun ? h('div', { className: cx(T.micro, 'aq-ink2') }, h(Icon, { name: 'sun' }), ` sun az ${sun.azimuth}° · el ${sun.elevation}°`) : null,
        water != null ? h('div', { className: cx(T.micro, 'aq-ink2') }, h(Icon, { name: 'water' }), ` water ~${water}°`) : null)
        : h('div', { className: cx(T.micro, 'aq-ink3') }, 'No sun found; bearings stay as camera yaw')));
}

// ---------------------------------------------------------------------------
export interface EstimateBarsProps { rows: { name: string; v: number; lo?: number; hi?: number; other?: boolean; before?: number; note?: string }[]; tone?: 'model' | 'solver'; max?: number; title?: string; caption?: string; mode?: 'single' | 'beforeAfter' }
/** Horizontal estimate bars, top 5 plus "other", with ranges where known. Before/after mode for answers. */
export function EstimateBars({ rows, tone = 'solver', max, title, caption, mode = 'single' }: EstimateBarsProps) {
  const T = useT();
  const M = max || Math.max(...rows.map(r => Math.max(r.hi || r.v, r.before || 0)), 0.01);
  const pct = (x: number) => `${Math.min(100, (x / M) * 100)}%`;
  return h('figure', { className: cx('aq-ebars', 'aq-tone-' + tone) },
    title ? h('figcaption', { className: cx(T.label, 'aq-ebars-t') }, title) : null,
    h('div', { className: 'aq-ebars-rows' }, rows.map((r, i) => h('div', { key: i, className: cx('aq-ebar', r.other && 'is-other') },
      h('span', { className: cx(T.body, 'aq-ebar-n') }, r.name),
      h('span', { className: 'aq-ebar-track' },
        mode === 'beforeAfter' && r.before != null ? h('i', { className: 'aq-ebar-before', style: { width: pct(r.before) } }) : null,
        h('b', { className: 'aq-ebar-fill', style: { width: pct(r.v) } }),
        r.lo != null && r.hi != null ? h('em', { className: 'aq-ebar-range', style: { left: pct(r.lo), width: `calc(${pct(r.hi)} - ${pct(r.lo)})` } }) : null),
      h('span', { className: cx(T.data, 'aq-ebar-v') }, mode === 'beforeAfter' && r.before != null ? `${fmtEst(r.before)} › ${fmtEst(r.v)}` : fmtEst(r.v)),
      r.note ? h('span', { className: cx(T.micro, 'aq-ebar-note') }, r.note) : null))),
    caption ? h('div', { className: cx(T.micro, 'aq-ink3') }, caption) : null);
}

// ---------------------------------------------------------------------------
export interface GainMeterProps { gain: number; breakEven?: number; cueLine?: boolean; max?: number }
/** Expected gain of asking against the break-even line (5.26% for ×0.95; 25% for a ×0.8 cue). */
export function GainMeter({ gain, breakEven = 1 / 0.95 - 1, cueLine, max = 0.3 }: GainMeterProps) {
  const T = useT();
  const pct = (x: number) => `${Math.min(100, Math.max(0, x / max * 100))}%`;
  const worth = gain > breakEven;
  return h('figure', { className: cx('aq-gain', worth ? 'is-worth' : 'is-not') },
    h('div', { className: 'aq-gain-head' }, h('span', { className: T.label }, 'Expected gain'), h('span', { className: T.readout }, fmtSigned(gain * 100, 0) + '%'),
      h('span', { className: cx(T.micro, 'aq-ink3') }, worth ? `above the ${fmtPct(breakEven, 2)} break-even` : `below the ${fmtPct(breakEven, 2)} break-even — not worth asking`)),
    h('div', { className: 'aq-gain-track', role: 'img', 'aria-label': `Expected gain ${fmtPct(gain)} against break-even ${fmtPct(breakEven, 2)}` },
      h('b', { style: { width: pct(gain) } }),
      h('i', { className: 'aq-gain-line', style: { left: pct(breakEven) } }, h('span', { className: T.micro }, `${fmtPct(breakEven, 2)} · ×0.95`)),
      cueLine ? h('i', { className: 'aq-gain-line is-cue', style: { left: pct(0.25) } }, h('span', { className: T.micro }, '25% · cue ×0.8')) : null),
    h('div', { className: cx('aq-gain-axis', T.micro) }, h('span', null, '0%'), h('span', null, fmtPct(max))));
}
