import { h, Fragment, cx, useT, useDensity, DensityContext, useState, fmtMult, fmtTime } from './rt';
import { Icon } from './icons';

// ---------------------------------------------------------------------------
// Density — sets console or stage density (and optionally a theme) for a subtree.
export interface DensityProps { value?: 'console' | 'stage'; theme?: 'dark' | 'light' | 'stage'; className?: string; style?: any; children?: any }
export function Density({ value = 'console', theme, className, style, children }: DensityProps) {
  return h(DensityContext.Provider, { value }, h('div', { 'data-density': value, 'data-theme': theme, className: cx('aq-root', className), style }, children));
}

// ---------------------------------------------------------------------------
export interface CostTagProps { multiplier: number; label?: string }
/** The cost tag: the multiplier an action will apply, shown before the click. */
export function CostTag({ multiplier, label }: CostTagProps) {
  const T = useT();
  return h('span', { className: cx('aq-costtag', T.data), title: `Costs ${fmtMult(multiplier)} on every guess after this` },
    h(Icon, { name: 'cost' }), h('span', null, fmtMult(multiplier)), label ? h('span', { className: 'aq-costtag-l' }, label) : null);
}

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'quiet' | 'skip';
  icon?: string; cost?: number; shortcut?: string; busy?: string; disabled?: boolean;
  pressed?: boolean; forceState?: 'hover' | 'focus' | 'active'; onClick?: () => void; children?: any; title?: string; className?: string;
}
/** The one button. Primary at most once per view; any action that costs points carries its cost tag. */
export function Button({ variant = 'secondary', icon, cost, shortcut, busy, disabled, pressed, forceState, onClick, children, title, className }: ButtonProps) {
  const T = useT();
  return h('button', {
    type: 'button', className: cx('aq-btn', 'aq-btn-' + variant, T.label, forceState && 'is-' + forceState, busy && 'is-busy', className),
    disabled: disabled || !!busy, 'aria-pressed': pressed, onClick, title, 'aria-busy': busy ? true : undefined,
  },
    icon ? h(Icon, { name: icon }) : null,
    h('span', { className: 'aq-btn-l' }, busy || children),
    variant === 'skip' ? h('span', { className: 'aq-free' }, 'free') : null,
    cost != null ? h(CostTag, { multiplier: cost }) : null,
    shortcut ? h(KeyCap, null, shortcut) : null);
}

export interface KeyCapProps { children?: any }
/** A keyboard key. Shown next to every action that has a shortcut. */
export function KeyCap({ children }: KeyCapProps) {
  const T = useT();
  return h('kbd', { className: cx('aq-key', T.dataSm) }, children);
}

export interface BadgeProps { tone?: 'neutral' | 'model' | 'solver' | 'team' | 'cost' | 'support' | 'contra' | 'outline'; icon?: string; solid?: boolean; children?: any; title?: string }
/** A short label. Tone means something: actors, cost, polarity. Neutral by default. */
export function Badge({ tone = 'neutral', icon, solid, children, title }: BadgeProps) {
  const T = useT();
  return h('span', { className: cx('aq-badge', 'aq-tone-' + tone, solid && 'is-solid', T.label), title }, icon ? h(Icon, { name: icon }) : null, children);
}

export interface StampProps { kind?: 'ruled-out' | 'confirmed' | 'submitted' | 'estimate'; children?: any }
/** A verdict stamp. At most one in view. Words, never colour alone. */
export function Stamp({ kind = 'ruled-out', children }: StampProps) {
  const T = useT();
  const text = children || { 'ruled-out': 'RULED OUT', confirmed: 'CONFIRMED BY MATCH', submitted: 'SUBMITTED', estimate: 'ESTIMATE' }[kind];
  return h('span', { className: cx('aq-stamp', 'aq-stamp-' + kind, T.stamp) }, text);
}

export interface TabsProps { tabs: { id: string; label: string; count?: number; icon?: string }[]; value: string; onChange?: (id: string) => void; label?: string }
/** Tabs: arrow keys move, Enter selects. Counts in mono. */
export function Tabs({ tabs, value, onChange, label }: TabsProps) {
  const T = useT();
  const [cur, setCur] = useState(value);
  const sel = onChange ? value : cur;
  return h('div', { className: 'aq-tabs', role: 'tablist', 'aria-label': label },
    tabs.map(t => h('button', {
      key: t.id, role: 'tab', type: 'button', 'aria-selected': sel === t.id, tabIndex: sel === t.id ? 0 : -1,
      className: cx('aq-tab', T.label, sel === t.id && 'is-on'), onClick: () => (onChange ? onChange(t.id) : setCur(t.id)),
    }, t.icon ? h(Icon, { name: t.icon }) : null, t.label, t.count != null ? h('span', { className: cx('aq-tab-n', T.dataSm) }, t.count) : null)));
}

export interface ToggleProps { label: string; on?: boolean; swatch?: string; icon?: string; disabled?: boolean; onChange?: (on: boolean) => void; hint?: string }
/** A switch. With a swatch it is a map/panorama layer toggle. */
export function Toggle({ label, on = false, swatch, icon, disabled, onChange, hint }: ToggleProps) {
  const T = useT();
  const [s, setS] = useState(on);
  const val = onChange ? on : s;
  return h('label', { className: cx('aq-toggle', T.label, val && 'is-on', disabled && 'is-disabled') },
    h('input', { type: 'checkbox', role: 'switch', checked: val, disabled, onChange: (e: any) => (onChange ? onChange(e.target.checked) : setS(e.target.checked)) }),
    h('span', { className: 'aq-toggle-track', 'aria-hidden': true }, h('span', { className: 'aq-toggle-knob' })),
    swatch ? h('span', { className: 'aq-swatch', style: { background: swatch } }) : null,
    icon ? h(Icon, { name: icon }) : null,
    h('span', { className: 'aq-toggle-l' }, label),
    hint ? h('span', { className: cx('aq-toggle-hint', T.micro) }, hint) : null);
}

export interface SegmentedProps { options: { id: string; label: string; icon?: string }[]; value: string; label?: string; onChange?: (id: string) => void }
/** A segmented choice (radio group), e.g. Urban / Non-urban / Unknown. */
export function Segmented({ options, value, label, onChange }: SegmentedProps) {
  const T = useT();
  const [cur, setCur] = useState(value);
  const sel = onChange ? value : cur;
  return h('div', { className: 'aq-seg', role: 'radiogroup', 'aria-label': label },
    options.map(o => h('button', { key: o.id, type: 'button', role: 'radio', 'aria-checked': sel === o.id, className: cx('aq-seg-o', T.label, sel === o.id && 'is-on'), onClick: () => (onChange ? onChange(o.id) : setCur(o.id)) },
      o.icon ? h(Icon, { name: o.icon }) : null, o.label)));
}

export interface TooltipProps { content: any; open?: boolean; children?: any; side?: 'top' | 'bottom' }
/** Hover or focus reveals a short explanation. Never holds the only copy of something important. */
export function Tooltip({ content, open, children, side = 'top' }: TooltipProps) {
  const T = useT();
  return h('span', { className: cx('aq-tip-wrap', open && 'is-open') }, children, h('span', { role: 'tooltip', className: cx('aq-tip', 'aq-tip-' + side, T.micro) }, content));
}

export interface ToastProps { tone?: 'neutral' | 'cost' | 'contra' | 'team'; icon?: string; title: string; body?: any; action?: string }
/** A transient report of something that happened (and is in the log). */
export function Toast({ tone = 'neutral', icon, title, body, action }: ToastProps) {
  const T = useT();
  return h('div', { className: cx('aq-toast', 'aq-tone-' + tone), role: 'status' },
    h(Icon, { name: icon || (tone === 'contra' ? 'warning' : tone === 'cost' ? 'cost' : 'info') }),
    h('div', { className: 'aq-toast-b' }, h('div', { className: T.heading }, title), body ? h('div', { className: cx(T.body, 'aq-ink2') }, body) : null),
    action ? h(Button, { variant: 'quiet' }, action) : null);
}

export interface DialogProps { title: string; children?: any; actions?: any; inline?: boolean; tone?: 'neutral' | 'cost' }
/** A modal decision. Used for Submit and for sending a cue: the cost is restated in the dialog. */
export function Dialog({ title, children, actions, inline, tone = 'neutral' }: DialogProps) {
  const T = useT();
  const box = h('div', { className: cx('aq-dialog', 'aq-tone-' + tone), role: 'dialog', 'aria-modal': true, 'aria-label': title },
    h('div', { className: cx('aq-dialog-t', T.title) }, title), h('div', { className: cx('aq-dialog-b', T.body) }, children), actions ? h('div', { className: 'aq-dialog-a' }, actions) : null);
  return h('div', { className: cx('aq-scrim', inline && 'is-inline') }, box);
}

export interface EmptyStateProps { icon?: string; title: string; body?: any; action?: any }
/** What to do when there is nothing here yet. Direction, not mood. */
export function EmptyState({ icon = 'info', title, body, action }: EmptyStateProps) {
  const T = useT();
  return h('div', { className: 'aq-empty' }, h(Icon, { name: icon }), h('div', { className: T.heading }, title), body ? h('div', { className: cx(T.body, 'aq-ink2') }, body) : null, action || null);
}

export interface WaitStateProps { what: string; who?: string; elapsed: number; deadline?: number; partial?: string; fallback?: string }
/** A real wait: names what is running, shows real elapsed time against its real deadline. No spinner, no fake percentage. */
export function WaitState({ what, who, elapsed, deadline, partial, fallback }: WaitStateProps) {
  const T = useT();
  const frac = deadline ? Math.min(1, elapsed / deadline) : 0;
  return h('div', { className: 'aq-wait', role: 'status', 'aria-live': 'polite' },
    h('div', { className: 'aq-wait-h' }, h(Icon, { name: 'running', className: 'aq-ink1' }), h('span', { className: T.heading }, what), who ? h('span', { className: cx('aq-ink3', T.label) }, who) : null),
    deadline ? h('div', { className: 'aq-deadline', 'aria-hidden': true }, h('span', { style: { width: `${frac * 100}%` } })) : null,
    h('div', { className: cx('aq-wait-m', T.data) }, h('span', null, fmtTime(elapsed)), deadline ? h('span', { className: 'aq-ink3' }, ` of ${fmtTime(deadline)} deadline`) : null),
    partial ? h('div', { className: cx(T.body, 'aq-ink2') }, partial) : null,
    fallback ? h('div', { className: cx(T.micro, 'aq-ink3') }, `If it runs out: ${fallback}`) : null);
}
