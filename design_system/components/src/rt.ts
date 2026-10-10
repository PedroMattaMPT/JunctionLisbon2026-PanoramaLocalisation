// Runtime: React from the page (window.React), density context, type-class helper, formatters.
const R: any = (window as any).React;
export const h = R.createElement;
export const Fragment = R.Fragment;
export const { useState, useEffect, useRef, useMemo, useContext, createContext, useCallback, useId } = R;

export type Density = 'console' | 'stage';
export const DensityContext = createContext('console');
export function useDensity(): Density { return useContext(DensityContext); }

/** Map a role to the generated type-style class for the current density (classes come from tokens.css). */
const TYPE: Record<Density, Record<string, string>> = {
  console: { title: 'console-title', heading: 'console-heading', body: 'console-body', label: 'console-label', micro: 'console-micro', data: 'console-data', dataSm: 'console-data-sm', readout: 'console-readout', inference: 'inference', stamp: 'stamp', caption: 'console-heading', headline: 'narrative-title', score: 'console-readout', display: 'narrative-title' },
  stage: { title: 'stage-title', heading: 'stage-body aq-strong', body: 'stage-body', label: 'stage-label', micro: 'stage-label', data: 'stage-data', dataSm: 'stage-label aq-mono', readout: 'stage-readout', inference: 'stage-inference', stamp: 'stage-stamp', caption: 'stage-caption', headline: 'narrative-headline', score: 'stage-score', display: 'narrative-display' },
};
export function useT() { return TYPE[useDensity()]; }

export const cx = (...a: any[]) => a.filter(Boolean).join(' ');

// ---------- formatters (true minus, tabular-friendly) ----------
export const MINUS = '−';
export const num = (x: number, d = 2) => (x < 0 ? MINUS : '') + Math.abs(x).toFixed(d);
export const fmtCoord = (lat: number, lng: number) => `${num(lat, 5)}, ${num(lng, 5)}`;
export const fmtEst = (x: number | null | undefined) => (x == null ? 'unknown' : x.toFixed(2));
export const fmtMult = (m: number) => '×' + m.toFixed(m === 0.8 || m === 0.5 ? 1 : 2);
export function fmtDist(m: number | null | undefined) {
  if (m == null) return 'unknown';
  if (m < 1000) return `${Math.round(m)} m`;
  if (m < 10000) return `${(m / 1000).toFixed(1)} km`;
  return `${Math.round(m / 1000)} km`;
}
export function fmtTime(s: number) { const neg = s < 0; s = Math.abs(Math.round(s)); const m = Math.floor(s / 60), r = s % 60; return (neg ? MINUS : '') + String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0'); }
export const fmtInt = (n: number) => Math.round(n).toLocaleString('en-US');
export const fmtPct = (x: number, d = 0) => (x * 100).toFixed(d) + '%';
export const fmtSigned = (x: number, d = 2) => (x > 0 ? '+' : x < 0 ? MINUS : '±') + Math.abs(x).toFixed(d);

// ---------- scoring (rules) ----------
export const RANK_W = Array.from({ length: 10 }, (_, i) => Math.pow(0.95, i));
export const theta = (dMeters: number, urban: boolean) => { const d = dMeters < 10 ? 0 : dMeters; return urban ? 2 / (1 + d / 100) : 2 / (1 + d / 10000); };
export const MAX_SCORE = 1000 * 2 * RANK_W.reduce((a, b) => a + b, 0); // 16,050.52
