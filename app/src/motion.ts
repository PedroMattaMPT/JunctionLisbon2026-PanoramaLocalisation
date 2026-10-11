import { useLayoutEffect, useRef, type RefObject } from 'react';
import { finite, str, type CaseRecord, type RunEvent } from './model';

export const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
export function motionDuration(name: string) {
  const token = getComputedStyle(document.documentElement).getPropertyValue(`--dur-${name}`).trim(), value = parseFloat(token);
  if (!Number.isFinite(value)) return 0;
  return token.endsWith('ms') ? value : token.endsWith('s') ? value * 1000 : value;
}
export function beatsFor(e: RunEvent): number[] {
  if (e.type === 'run.started') return [1];
  if (e.type === 'stage.finished' && e.stage === 'views') return [2];
  if (e.type === 'candidates.updated') return [8, 9];
  if (e.type.startsWith('question.')) return [10];
  if (e.type === 'stage.started' && e.stage === 'spot') return [11];
  if (e.type === 'output.produced') return [12];
  if (e.type !== 'evidence.added') return [];
  const kind = str(e.payload.kind);
  if (kind === 'object') return [3];
  if (['text', 'postcode', 'phone', 'road_number', 'language'].includes(kind)) return [4];
  if (['checklist', 'vlm_checklist', 'vlm_summary', 'landmark_hypothesis'].includes(kind)) return [5];
  if (['scene_shares', 'sun'].includes(kind)) return [6];
  if (['neighbour', 'landmark_photo', 'region', 'geo_sample', 'name_match', 'knn', 'region_head', 'geoclip', 'name_lookups', 'landmark_gallery'].includes(kind)) return [7];
  if (['contradiction', 'fusion'].includes(kind)) return [8];
  if (kind === 'match') return [11];
  return [];
}
export function useEventMotion(root: RefObject<HTMLElement>, c: CaseRecord, enabled: boolean) {
  const previous = useRef<CaseRecord>();
  const pending = useRef(new Set<() => void>());
  useLayoutEffect(() => () => { pending.current.forEach(cleanup => cleanup()); }, []);
  useLayoutEffect(() => {
    const old = previous.current; previous.current = c;
    if (!enabled || old && old.id !== c.id) pending.current.forEach(cleanup => cleanup());
    const el = root.current; if (!el || !enabled || !old || old.id && c.id !== old.id) return;
    const newEvents = c.events.filter(e => !old.events.some(p => p.seq === e.seq));
    if (!newEvents.length) return;
    const css = getComputedStyle(el), space = (n: string) => parseFloat(css.getPropertyValue(`--space-${n}`));
    const animations: Animation[] = [], frames: number[] = [], counts: { target: Element; original: string | null }[] = [], strokes: { target: SVGElement; dash: string; offset: string }[] = [];
    const ease = (name: string) => css.getPropertyValue(`--ease-${name}`).trim();
    const animate = (target: Element, keyframes: Keyframe[], duration: string, delay = 0, easing = 'enter') => {
      if (typeof target.animate !== 'function') return;
      const reduced = reducedMotion();
      animations.push(target.animate(reduced ? [{ opacity: 0 }, { opacity: 1 }] : keyframes, { duration: motionDuration(reduced ? 'quick' : duration), delay: reduced ? 0 : Math.min(delay, motionDuration('stagger-cap')), easing: reduced ? ease('move') : ease(easing), fill: 'backwards' }));
    };
    const all = (selector: string, keyframes: Keyframe[], duration = 'standard', stagger = false, easing = 'enter') => el.querySelectorAll(selector).forEach((target, i) => animate(target, keyframes, duration, stagger ? i * motionDuration('stagger') : 0, easing));
    const draw = (selector: string, duration = 'quick') => el.querySelectorAll<SVGGeometryElement>(selector).forEach((target, i) => {
      if (reducedMotion() || typeof target.getTotalLength !== 'function') return;
      const length = target.getTotalLength(); if (!Number.isFinite(length) || length <= 0) return;
      const original = { target, dash: target.style.strokeDasharray, offset: target.style.strokeDashoffset }; strokes.push(original);
      target.style.strokeDasharray = String(length);
      const animation = target.animate([{ strokeDashoffset: String(length) }, { strokeDashoffset: '0' }], { duration: motionDuration(duration), delay: Math.min(i * motionDuration('stagger'), motionDuration('stagger-cap')), easing: ease('enter') });
      animation.onfinish = () => { target.style.strokeDasharray = original.dash; target.style.strokeDashoffset = original.offset; }; animations.push(animation);
    });
    const fade = [{ opacity: 0 }, { opacity: 1 }];
    const rise = [{ opacity: 0, transform: `translateY(${space('2')}px)` }, { opacity: 1, transform: 'none' }];
    for (const event of newEvents) {
      const kind = str(event.payload.kind), id = str(event.payload.evidence_id), escaped = typeof CSS !== 'undefined' ? CSS.escape(id) : id.replace(/[^\w-]/g, '');
      const row = escaped ? `[data-motion-id="${escaped}"]` : '.app-no-target';
      for (const beat of beatsFor(event)) {
        if (beat === 1) all('[data-motion-target="intake"],.aq-fn-parts', rise);
        if (beat === 2) { all('.aq-ov-sector,.aq-ov-mask,.aq-ov-maskline', fade, 'quick', true); draw('.aq-ov-sector'); }
        if (beat === 3) {
          if (event.payload.kept === false) all(row, [{ opacity: 1 }, { opacity: parseFloat(css.getPropertyValue('--opacity-ghost')) }], 'standard', false, 'exit');
          else { all(row, [{ opacity: 0, transform: 'scale(0.92)' }, { opacity: 1, transform: 'scale(1)' }], 'deliberate', true); draw(`${row} rect:not(.aq-ov-halo),${row} path:not(.aq-ov-halo)`, 'cinematic'); }
        }
        if (beat === 4) { all(row, rise); draw(`${row} rect`); all('[data-motion-target="read"]', [{ opacity: 0, transform: 'scale(0.92)' }, { opacity: 1, transform: 'scale(1)' }]); if (kind === 'language') all('.aq-stack-seg', [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], 'deliberate', false, 'move'); }
        if (beat === 5) { all(row, rise, 'standard', true); all(`${row} [data-feature]`, rise, 'deliberate', true); }
        if (beat === 6) { if (kind === 'scene_shares') all('[data-motion-target="measure"]', [{ transform: 'scaleX(0)', opacity: 0 }, { transform: 'scaleX(1)', opacity: 1 }], 'cinematic', false, 'move'); else all('.aq-compass,.aq-ruler', fade, 'deliberate', false, 'move'); }
        if (beat === 7) {
          all('[data-motion-target="geo"]', fade); all(row, rise);
          const card = el.querySelector(`.aq-ev[data-link="${escaped}"]`), pin = el.querySelector(`.aq-map-ref[data-link="${escaped}"]`);
          if (card && pin && !reducedMotion()) { const from = card.getBoundingClientRect(), to = pin.getBoundingClientRect(); animate(pin, [{ transform: `translate(${from.left - to.left}px,${from.top - to.top}px)`, opacity: 0 }, { transform: 'none', opacity: 1 }], 'cinematic'); }
        }
        if (beat === 8) {
          if (kind === 'contradiction') {
            for (const linked of Array.isArray(event.payload.between) ? event.payload.between : []) {
              if (typeof linked !== 'string') continue;
              const target = el.querySelector(`.aq-ev[data-link="${CSS.escape(linked)}"]`);
              if (target) animate(target, [{ opacity: 1 }, { opacity: parseFloat(css.getPropertyValue('--opacity-dim')) }, { opacity: 1 }, { opacity: parseFloat(css.getPropertyValue('--opacity-dim')) }, { opacity: 1 }], 'deliberate');
            }
          } else {
            el.querySelectorAll('.aq-cand,.focus-candidate').forEach(target => { const candidate = c.candidates.find(v => v.id === target.getAttribute('data-link')), before = old.candidates.find(v => v.id === candidate?.id); const bar = target.querySelector('.aq-cand-bar b,.focus-support b'); if (bar && candidate?.v != null && candidate.v > 0) animate(bar, [{ transform: `scaleX(${before?.v != null ? before.v / candidate.v : 0})` }, { transform: 'scaleX(1)' }], 'deliberate', 0, 'move'); });
            all('.aq-pol,.aq-ruled', fade, 'quick', true); if (c.groups.length > old.groups.length) all('.aq-corr', rise);
          }
        }
        // Beat 9 is handled by the map adapter, using the same logged view and motion tokens.
        if (beat === 10) {
          if (event.type === 'question.asked') { all('.aq-q,.focus-question', rise); all('.aq-zone-line', fade, 'standard', true); draw('.aq-zone-line', 'standard'); all('.aq-gain-fill', [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], 'deliberate', false, 'move'); }
          else if (event.type === 'question.answered') all('.aq-mult,.aq-receipt', fade, 'deliberate', false, 'move');
          else all('.aq-receipt.is-skipped', fade); // no candidate, zone or multiplier motion on a skip
        }
        if (beat === 11) { all('.aq-match', [{ transform: `translateX(${space('3')}px)`, opacity: 0 }, { transform: 'none', opacity: 1 }]); all('.aq-match-in,.aq-match-out', fade, 'quick', true); draw('.aq-match-in'); const inliers = finite(event.payload.inliers); if (inliers !== null) count('[data-inlier-count]', inliers, 'deliberate', value => String(Math.round(value))); }
        if (beat === 12) {
          all('.aq-mark,[data-motion-target="final-mark"]', [{ transform: `translateY(-${space('3')}px)`, opacity: 0 }, { transform: 'none', opacity: 1 }], 'deliberate', false, 'spring');
          all('.aq-ring,.aq-coord-r', fade, 'deliberate', false, 'move'); all('.aq-slots-wi i', [{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], 'deliberate', true, 'move');
          const expected = c.answer?.expected; if (expected != null) count('.app-final .aq-score-v > span:first-child', expected * (c.special ? 3 : 1), 'cinematic', value => `≈ ${Math.round(value).toLocaleString('en-US')}`);
        }
      }
    }
    function count(selector: string, value: number, duration: string, format: (value: number) => string) {
      if (reducedMotion()) return; const target = el!.querySelector(selector); if (!target) return;
      const begin = performance.now(), ms = motionDuration(duration), original = target.textContent;
      counts.push({ target, original });
      const tick = (now: number) => { const elapsed = Math.min(1, (now - begin) / ms); target.textContent = format(value * elapsed); if (elapsed < 1) frames.push(requestAnimationFrame(tick)); else target.textContent = original; };
      frames.push(requestAnimationFrame(tick));
    }
    // Progress messages can arrive immediately after observations. Keep their entrances running across
    // those renders, and cancel only when seeking, changing cases, unmounting or completing the motion.
    const cleanup = () => { clearTimeout(timer); animations.forEach(animation => animation.cancel()); frames.forEach(cancelAnimationFrame); counts.forEach(({ target, original }) => { if (target.isConnected) target.textContent = original; }); strokes.forEach(({ target, dash, offset }) => { target.style.strokeDasharray = dash; target.style.strokeDashoffset = offset; }); pending.current.delete(cleanup); };
    const timer = setTimeout(cleanup, Math.max(motionDuration('cinematic'), motionDuration('deliberate')) + motionDuration('stagger-cap') + 100);
    pending.current.add(cleanup);
  }, [c.events.at(-1)?.seq, c.id, enabled]);
}
