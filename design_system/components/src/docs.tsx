import { h, cx } from './rt';
import { Density } from './base';
/** Specimen helpers used only by previews: a labelled grid of states. */
export function Cell({ label, children, wide, pad = true }: any) {
  return h('div', { className: cx('aq-spec-cell', wide && 'is-wide', !pad && 'no-pad') }, label ? h('div', { className: 'aq-spec-l console-micro' }, label) : null, h('div', { className: 'aq-spec-b' }, children));
}
export function Grid({ cols = 3, children, gap }: any) { return h('div', { className: 'aq-spec-grid', style: { gridTemplateColumns: typeof cols === 'number' ? `repeat(${cols}, minmax(0, 1fr))` : cols, gap } }, children); }
export function Page({ children, theme, density = 'console', pad = true, style }: any) { return h(Density, { value: density, theme, className: cx('aq-spec-page', !pad && 'no-pad'), style }, children); }
