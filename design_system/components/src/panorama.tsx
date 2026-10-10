import { h, Fragment, cx, useT, useDensity, useState, useId } from './rt';
import { Icon } from './icons';
import { Toggle } from './base';
import { urbanScene, ruralScene, equiPts, toYawPitch, persp, perspPoint, skyline, yawPitchToXY, dir, Scene, Cam, Pt3 } from './scene';

const D2R = Math.PI / 180;
export const sceneFor = (c: any): Scene => (c.scene === 'rural' ? ruralScene() : urbanScene());
const SEG_VAR: Record<string, string> = { sky: 'var(--seg-sky)', building: 'var(--seg-building)', tree: 'var(--seg-tree)', grass: 'var(--seg-grass)', water: 'var(--seg-water)', road: 'var(--seg-road)', ground: 'var(--seg-ground)' };
const pts2 = (a: [number, number][]) => a.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');

// ---------------------------------------------------------------------------
/** Draws the scene as an equirectangular image into an SVG group. seg=true draws segmentation classes instead of colours. */
function EquiScene({ sc, W, H, seg }: { sc: Scene; W: number; H: number; seg?: boolean }) {
  const els: any[] = [];
  els.push(h('rect', { key: 'sky', x: 0, y: 0, width: W, height: H / 2 + 1, fill: seg ? SEG_VAR.sky : sc.sky }));
  els.push(h('rect', { key: 'gr', x: 0, y: H / 2, width: W, height: H / 2, fill: seg ? SEG_VAR[sc.groundSeg] : sc.ground }));
  if (!seg) for (const dd of (sc.horizon ? [4, 9, 20] : [2.2, 3.2, 4.6, 6.5, 9.5])) { const y = (90 + Math.atan2(1.7, dd) / D2R) / 180 * H; els.push(h('line', { key: 'pv' + dd, x1: 0, x2: W, y1: y, y2: y, stroke: '#00000014', strokeWidth: 1 })); }
  if (sc.horizon) {
    const top: [number, number][] = []; for (let y = 0; y <= 360; y += 2) top.push(yawPitchToXY(y === 360 ? 359.999 : y, sc.horizon(y), W, H));
    els.push(h('polygon', { key: 'hz', points: pts2([...top, [W, H / 2 + 1], [0, H / 2 + 1]]), fill: seg ? SEG_VAR.tree : sc.horizonFill }));
  }
  if (sc.sun && !seg) { const [x, y] = yawPitchToXY(sc.sun.yaw, sc.sun.el, W, H); els.push(h('circle', { key: 'sun', cx: x, cy: y, r: Math.max(2.5, W / 360 * 1.4), fill: '#f7f3e6' })); }
  const polys = [...sc.polys].sort((a, b) => b.depth - a.depth);
  polys.forEach((p, i) => {
    if (seg && (p.kind === 'window' || p.kind === 'door' || p.kind === 'sign' || p.fill === 'none')) return;
    for (const cp of equiPts(p.pts, W, H)) els.push(h('polygon', { key: 'p' + i + '_' + cp[0][0].toFixed(0), points: pts2(cp), fill: seg ? SEG_VAR[p.seg || 'building'] : p.fill, stroke: seg ? 'none' : p.stroke, strokeWidth: p.sw }));
  });
  sc.discs.forEach((d, i) => {
    const [yaw, pitch] = toYawPitch(d.c); const dist = Math.hypot(d.c[0], d.c[1]);
    const rx = Math.atan2(d.r, dist) / D2R / 360 * W, ry = Math.atan2(d.ry || d.r, dist) / D2R / 180 * H;
    const [x, y] = yawPitchToXY(yaw, pitch, W, H);
    for (const dx of [0, W, -W]) els.push(h('ellipse', { key: 'd' + i + dx, cx: x + dx, cy: y, rx, ry, fill: seg ? SEG_VAR.tree : d.fill }));
  });
  return h('g', { className: seg ? 'aq-seg-layer' : undefined }, els);
}

// ---------------------------------------------------------------------------
export interface BearingRulerProps { width: number; mode?: 'yaw' | 'bearing'; offset?: number; err?: number; marks?: { yaw: number; label?: string; tone?: string }[]; fov?: { yaw: number; fov: number } }
/** 0–360° ruler under the panorama. Camera yaw until the sun fixes north; then true bearings with the fix's ± error. */
export function BearingRuler({ width, mode = 'yaw', offset = 0, err, marks = [], fov }: BearingRulerProps) {
  const stage = useDensity() === 'stage';
  const H = stage ? 48 : 28; const W = width;
  const ticks: any[] = [];
  const x = (yaw: number) => (((yaw % 360) + 360) % 360) / 360 * W;
  for (let b = 0; b < 360; b += 5) {
    const yaw = mode === 'bearing' ? b - offset : b; const X = x(yaw);
    const major = b % 45 === 0, mid = b % 15 === 0;
    ticks.push(h('line', { key: 't' + b, x1: X, x2: X, y1: 0, y2: major ? H * 0.42 : mid ? H * 0.28 : H * 0.16, className: major ? 'aq-ruler-major' : 'aq-ruler-minor' }));
    if (major) {
      const card = mode === 'bearing' ? ({ 0: 'N', 90: 'E', 180: 'S', 270: 'W' } as any)[b] : null;
      ticks.push(h('text', { key: 'l' + b, x: X, y: H - (stage ? 8 : 5), textAnchor: X < 12 ? 'start' : X > W - 12 ? 'end' : 'middle', className: cx('aq-ruler-txt', card && 'is-card') }, card ? `${card} ${b}°` : `${b}°`));
    }
  }
  let errBand = null;
  if (mode === 'bearing' && err) { const X = x(-offset); const half = err / 360 * W; errBand = h('rect', { x: X - half, y: 0, width: half * 2, height: H * 0.42, className: 'aq-ruler-err' }); }
  return h('div', { className: cx('aq-ruler', 'is-' + mode) },
    h('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, preserveAspectRatio: 'none', 'aria-hidden': true },
      h('rect', { x: 0, y: 0, width: W, height: H, className: 'aq-ruler-bg' }), errBand,
      fov ? h('rect', { x: x(fov.yaw - fov.fov / 2), y: 0, width: fov.fov / 360 * W, height: 3, className: 'aq-ruler-fov' }) : null,
      ticks,
      marks.map((m, i) => h('path', { key: 'm' + i, d: `M${x(m.yaw)} 0 l5 7 h-10z`, className: cx('aq-ruler-mark', m.tone && 'is-' + m.tone) }))),
    h('div', { className: cx('aq-ruler-cap', useT().micro) }, mode === 'bearing' ? `True bearing · sun fix ± ${err}°` : 'Camera yaw · north unknown'));
}

// ---------------------------------------------------------------------------
export interface PanoramaStripProps {
  c: any; width?: number; layers?: Record<string, boolean>; selected?: string; ruler?: 'yaw' | 'bearing' | false; fov?: { yaw: number; fov: number };
  showRejected?: boolean; crop?: [number, number]; visibleBoxes?: string[]; fadedBoxes?: string[]; label?: boolean; labelMode?: 'all' | 'selected' | 'text';
}
/** The flat equirectangular panorama with overlay layers and the bearing ruler. Built from the case's evidence. */
export function PanoramaStrip({ c, width = 640, layers = {}, selected, ruler = 'yaw', fov, showRejected = true, crop, visibleBoxes, fadedBoxes, label = true, labelMode = 'all' }: PanoramaStripProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const uid = useId().replace(/:/g, '');
  const W = width, H = width / 2;
  const sc = sceneFor(c);
  const L = { sectors: false, mask: true, boxes: true, text: true, seg: false, sun: false, water: false, skyline: false, ...layers };
  const [y0, y1] = crop ? [(90 - crop[0]) / 180 * H, (90 - crop[1]) / 180 * H] : [0, H];
  const xy = (yaw: number, pitch: number) => yawPitchToXY(yaw, pitch, W, H);
  const lw = stage ? 2.5 : 1.5;
  const overlays: any[] = [];
  // view sectors
  if (L.sectors) {
    for (let i = 0; i < 8; i++) { const X = i * W / 8; overlays.push(h('line', { key: 's' + i, x1: X, x2: X, y1: H * 0.25, y2: H * 0.82, className: 'aq-ov-sector' })); overlays.push(h('text', { key: 'st' + i, x: X + W / 16, y: H * 0.25 + (stage ? 26 : 14), textAnchor: 'middle', className: 'aq-ov-lab' }, `V${i + 1}`)); }
    overlays.push(h('line', { key: 'sky', x1: 0, x2: W, y1: H * 0.25, y2: H * 0.25, className: 'aq-ov-sector' }));
    overlays.push(h('text', { key: 'skyt', x: 6, y: H * 0.25 - 6, className: 'aq-ov-lab' }, 'sky view above 45°'));
  }
  // photographer mask (bottom 18%)
  if (L.mask) {
    const my = H * 0.82; const maskLabel = label && labelMode === 'all';
    overlays.push(h('rect', { key: 'mask', x: 0, y: my, width: W, height: H - my, fill: `url(#hatch${uid})`, className: 'aq-ov-mask' }));
    overlays.push(h('line', { key: 'maskl', x1: 0, x2: W, y1: my, y2: my, className: 'aq-ov-maskline' }));
    if (maskLabel) overlays.push(h('text', { key: 'maskt', x: 6, y: my + (stage ? 26 : 14), className: 'aq-ov-lab' }, 'photographer mask · bottom 18% · excluded'));
  }
  // skyline trace
  if (L.skyline) { const sl = skyline(sc, 2).map(([y, p]) => xy(y === 360 ? 359.99 : y, p)); overlays.push(h('polyline', { key: 'sl', points: pts2(sl), className: 'aq-ov-skyline' })); }
  // detection boxes (object frames: corner brackets)
  const boxIds = (id: string) => !visibleBoxes || visibleBoxes.includes(id);
  if (L.boxes && c.detections) c.detections.forEach((b: any) => {
    if (!boxIds(b.id)) return;
    if (!b.kept && !showRejected) return;
    const [x0, yy0] = xy(b.yaw - b.w / 2, b.pitch + b.h / 2), [x1, yy1] = xy(b.yaw + b.w / 2, b.pitch - b.h / 2);
    const w = x1 - x0, hh = yy1 - yy0, k = Math.min(w, hh) * 0.3;
    const sel = selected === b.id; const faded = fadedBoxes && fadedBoxes.includes(b.id);
    const d = `M${x0} ${yy0 + k}V${yy0}H${x0 + k}M${x1 - k} ${yy0}H${x1}V${yy0 + k}M${x1} ${yy1 - k}V${yy1}H${x1 - k}M${x0 + k} ${yy1}H${x0}V${yy1 - k}`;
    overlays.push(h('g', { key: b.id, className: cx('aq-ov-box', !b.kept && 'is-rejected', sel && 'is-sel', faded && 'is-faded'), 'data-link': b.id },
      h('path', { d, className: 'aq-ov-halo', strokeWidth: lw + 2.5 }), h('path', { d, strokeWidth: sel ? lw + 1 : lw }),
      !b.kept ? h('line', { x1: x0, y1: yy1, x2: x1, y2: yy0, strokeWidth: lw }) : null,
      label && (labelMode === 'all' || sel) ? h(OnPhotoLabel, { x: x0, y: yy0 - 3, text: b.kept ? `${b.label} ${b.score.toFixed(2)}` : `${b.label} · rejected`, strike: !b.kept }) : null));
  });
  // text boxes with readings
  if (L.text && c.texts) c.texts.forEach((t: any) => {
    const [x0, yy0] = xy(t.yaw - t.w / 2, t.pitch + t.h / 2), [x1, yy1] = xy(t.yaw + t.w / 2, t.pitch - t.h / 2);
    const sel = selected === t.id;
    overlays.push(h('g', { key: t.id, className: cx('aq-ov-text', sel && 'is-sel'), 'data-link': t.id },
      h('rect', { x: x0, y: yy0, width: x1 - x0, height: yy1 - yy0, className: 'aq-ov-halo', strokeWidth: lw + 2.5 }),
      h('rect', { x: x0, y: yy0, width: x1 - x0, height: yy1 - yy0, strokeWidth: sel ? lw + 1 : lw }),
      label && (labelMode !== 'selected' || sel) ? h(OnPhotoLabel, { x: Math.min(x0, W - (t.text.length + 8) * (stage ? 12.4 : 6.8) - 8), y: yy1 + (stage ? 30 : 15), text: `“${t.text}” ${t.conf.toFixed(2)}`, mono: true }) : null));
  });
  // sun marker
  if (L.sun && c.sun) {
    const [x, y] = xy(c.sun.yaw, c.sun.elevation); const r = stage ? 16 : 9;
    overlays.push(h('g', { key: 'sun', className: 'aq-ov-sun' }, h('circle', { cx: x, cy: y, r: r + 2, className: 'aq-ov-halo', strokeWidth: lw + 2.5 }), h('circle', { cx: x, cy: y, r: r, strokeWidth: lw }),
      h('path', { d: `M${x - r * 1.8} ${y}h${r * 0.8}M${x + r} ${y}h${r * 0.8}M${x} ${y - r * 1.8}v${r * 0.8}M${x} ${y + r}v${r * 0.8}`, strokeWidth: lw }),
      label ? h(OnPhotoLabel, { x: x + r * 2, y: y + 4, text: `sun · yaw ${c.sun.yaw}° · elevation ${c.sun.elevation}°` }) : null));
  }
  // water direction
  if (L.water && c.water) {
    const wy = c.water.bearing - c.yawToBearing; const [x, y] = xy(wy, -1.5); const s = stage ? 1.8 : 1;
    overlays.push(h('g', { key: 'water', className: 'aq-ov-water' }, h('path', { d: `M${x} ${y - 30 * s}v${26 * s}m-${6 * s} -${7 * s}l${6 * s} ${7 * s} ${6 * s} -${7 * s}`, className: 'aq-ov-halo', strokeWidth: lw + 2.5, fill: 'none' }),
      h('path', { d: `M${x} ${y - 30 * s}v${26 * s}m-${6 * s} -${7 * s}l${6 * s} ${7 * s} ${6 * s} -${7 * s}`, strokeWidth: lw, fill: 'none' }),
      label ? h(OnPhotoLabel, { x: x + 8, y: y - 22 * s, text: `water · bearing ~${c.water.bearing}°` }) : null));
  }
  // 360 viewer field of view (kept in sync on yaw)
  if (fov) {
    const vf = fov.fov * 0.62; const [x0, yy0] = xy(fov.yaw - fov.fov / 2, vf / 2), [x1, yy1] = xy(fov.yaw + fov.fov / 2, -vf / 2); const k = 10;
    const d = `M${x0} ${yy0 + k}V${yy0}H${x0 + k}M${x1 - k} ${yy0}H${x1}V${yy0 + k}M${x1} ${yy1 - k}V${yy1}H${x1 - k}M${x0 + k} ${yy1}H${x0}V${yy1 - k}`;
    overlays.push(h('g', { key: 'fov', className: 'aq-ov-fov' }, h('path', { d, className: 'aq-ov-halo', strokeWidth: lw + 3 }), h('path', { d, strokeWidth: lw + 0.5 }), label ? h(OnPhotoLabel, { x: x0 + 4, y: yy1 - 6, text: `360° view · yaw ${fov.yaw}°` }) : null));
  }
  const vb = `0 ${y0} ${W} ${y1 - y0}`;
  const marks = [] as any[];
  const selObj = (c.texts || []).concat(c.detections || []).find((o: any) => o.id === selected);
  if (selObj) marks.push({ yaw: selObj.yaw, tone: 'select' });
  return h('figure', { className: 'aq-pano', style: { width: W } },
    h('svg', { className: 'aq-pano-svg', viewBox: vb, width: W, height: y1 - y0, role: 'img', 'aria-label': `Panorama ${c.file}, ${c.size?.[0]}×${c.size?.[1]}` },
      h('defs', null, h('pattern', { id: 'hatch' + uid, width: 8, height: 8, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, h('line', { x1: 0, y1: 0, x2: 0, y2: 8, className: 'aq-hatch-line' }))),
      h(EquiScene, { sc, W, H }),
      L.seg ? h('g', { opacity: 0.62 }, h(EquiScene, { sc, W, H, seg: true })) : null,
      overlays),
    ruler ? h(BearingRuler, { width: W, mode: ruler, offset: c.yawToBearing, err: c.yawToBearingErr, marks, fov }) : null);
}

function OnPhotoLabel({ x, y, text, mono, strike }: { x: number; y: number; text: string; mono?: boolean; strike?: boolean }) {
  const stage = useDensity() === 'stage';
  const fs = stage ? 20 : 11, pad = stage ? 6 : 3, cw = fs * (mono ? 0.62 : 0.56);
  const w = text.length * cw + pad * 2, hh = fs + pad * 2 - 2;
  return h('g', { className: 'aq-ov-label' }, h('rect', { x, y: y - hh, width: w, height: hh, rx: 2, className: 'aq-ov-plate' }),
    h('text', { x: x + pad, y: y - pad - 1, className: cx('aq-ov-ltxt', mono && 'is-mono'), style: { fontSize: fs } }, text),
    strike ? h('line', { x1: x + pad, x2: x + w - pad, y1: y - hh / 2, y2: y - hh / 2, className: 'aq-ov-strike' }) : null);
}

// ---------------------------------------------------------------------------
/** Rectilinear render of the scene for a camera (used by the 360° viewer, zoom crops and exact-spot views). */
export function PerspScene({ sc, cam, seg }: { sc: Scene; cam: Cam; seg?: boolean }) {
  const els: any[] = [];
  // sky/ground split at the horizon line (pitch 0)
  const hz = perspPoint([cam.pos[0] + dir(cam.yaw)[0] * 1e5, cam.pos[1] + dir(cam.yaw)[1] * 1e5, cam.pos[2]], cam);
  const hy = Math.max(0, Math.min(cam.h, hz ? hz[1] : cam.h / 2));
  els.push(h('rect', { key: 'sky', x: 0, y: 0, width: cam.w, height: hy + 1, fill: sc.sky }), h('rect', { key: 'gr', x: 0, y: hy, width: cam.w, height: Math.max(0, cam.h - hy), fill: sc.ground }));
  if (sc.horizon) {
    const top: [number, number][] = []; for (let a = -cam.fov; a <= cam.fov; a += 2) { const y = cam.yaw + a; const e = sc.horizon(((y % 360) + 360) % 360); const dd = 1e5; const [s, c] = dir(y); const p = perspPoint([cam.pos[0] + s * dd, cam.pos[1] + c * dd, cam.pos[2] + Math.tan(e * D2R) * dd], cam); if (p) top.push(p); }
    if (top.length) els.push(h('polygon', { key: 'hz', points: pts2([...top, [top[top.length - 1][0], hy + 2], [top[0][0], hy + 2]]), fill: sc.horizonFill }));
  }
  if (sc.sun) { const dd = 1e5; const [s, c] = dir(sc.sun.yaw); const p = perspPoint([cam.pos[0] + s * dd * Math.cos(sc.sun.el * D2R), cam.pos[1] + c * dd * Math.cos(sc.sun.el * D2R), cam.pos[2] + dd * Math.sin(sc.sun.el * D2R)], cam); if (p && p[0] > -40 && p[0] < cam.w + 40) els.push(h('circle', { key: 'sun', cx: p[0], cy: p[1], r: cam.w / cam.fov * 1.2, fill: '#f7f3e6' })); }
  const dist = (p: Pt3[]) => { const m = p.reduce((a, q) => [a[0] + q[0], a[1] + q[1]], [0, 0]); return Math.hypot(m[0] / p.length - cam.pos[0], m[1] / p.length - cam.pos[1]); };
  const items = [...sc.polys.map(p => ({ t: 'p', p, d: dist(p.pts) - (p.kind === 'window' || p.kind === 'door' || p.kind === 'sign' || p.kind === 'azulejo' ? 0.05 : 0) })), ...sc.discs.map(d => ({ t: 'd', p: d, d: Math.hypot(d.c[0] - cam.pos[0], d.c[1] - cam.pos[1]) - 0.5 }))];
  // ground polygons (z=0 everywhere) always behind standing things
  items.sort((a: any, b: any) => { const ga = a.t === 'p' && a.p.pts.every((q: Pt3) => q[2] === 0), gb = b.t === 'p' && b.p.pts.every((q: Pt3) => q[2] === 0); if (ga !== gb) return ga ? -1 : 1; return b.d - a.d; });
  items.forEach((it: any, i: number) => {
    if (it.t === 'p') { const sp = persp(it.p.pts, cam); if (sp) els.push(h('polygon', { key: i, points: pts2(sp), fill: seg ? SEG_VAR[it.p.seg] : it.p.fill, stroke: it.p.stroke, strokeWidth: it.p.sw })); }
    else { const d = it.p; const cpt = perspPoint(d.c, cam); if (!cpt) return; const e = perspPoint([d.c[0], d.c[1], d.c[2] + (d.ry || d.r)], cam); const ry = e ? Math.abs(cpt[1] - e[1]) : 4; els.push(h('ellipse', { key: i, cx: cpt[0], cy: cpt[1], rx: ry * (d.r / (d.ry || d.r)), ry, fill: d.fill })); }
  });
  return h('g', null, els);
}
const dirPoint = (yaw: number, pitch: number, cam: Cam): [number, number] | null => { const dd = 100; const [s, c] = dir(yaw); return perspPoint([cam.pos[0] + s * dd * Math.cos(pitch * D2R), cam.pos[1] + c * dd * Math.cos(pitch * D2R), cam.pos[2] + dd * Math.sin(pitch * D2R)], cam); };

// ---------------------------------------------------------------------------
export interface Viewer360Props { c: any; yaw?: number; pitch?: number; fov?: number; width?: number; height?: number; selected?: string; synced?: boolean; showBoxes?: boolean }
/** The interactive 360° viewer frame (Pannellum in the app), kept in sync with the strip on yaw. */
export function Viewer360({ c, yaw = 212, pitch = 0, fov = 90, width = 560, height = 320, selected, synced = true, showBoxes = true }: Viewer360Props) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const sc = sceneFor(c);
  const cam: Cam = { pos: [0, 0, 1.7], yaw, pitch, fov, w: width, h: height };
  const bearing = c.yawToBearing != null ? Math.round(((yaw + c.yawToBearing) % 360 + 360) % 360) : null;
  const lw = stage ? 3 : 1.75;
  const boxes: any[] = [];
  if (showBoxes) for (const t of [...(c.texts || []), ...(c.detections || []).filter((d: any) => d.kept)]) {
    const a = dirPoint(t.yaw - t.w / 2, t.pitch + t.h / 2, cam), b = dirPoint(t.yaw + t.w / 2, t.pitch - t.h / 2, cam);
    if (!a || !b || a[0] < 0 || b[0] > width) continue;
    const isText = !!t.text; const sel = selected === t.id;
    boxes.push(h('g', { key: t.id, className: cx(isText ? 'aq-ov-text' : 'aq-ov-box', sel && 'is-sel'), 'data-link': t.id },
      h('rect', { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1], className: 'aq-ov-halo', strokeWidth: lw + 2.5, fill: 'none' }),
      h('rect', { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1], strokeWidth: sel ? lw + 1 : lw, fill: 'none' }),
      h(OnPhotoLabel, { x: a[0], y: isText ? b[1] + (stage ? 30 : 16) : a[1] - 3, text: isText ? `“${t.text}” ${t.conf.toFixed(2)}` : `${t.label} ${t.score.toFixed(2)}`, mono: isText })));
  }
  return h('figure', { className: 'aq-v360', style: { width } },
    h('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': `360° view at yaw ${yaw}°` }, h(PerspScene, { sc, cam }), boxes,
      h('path', { d: `M${width / 2 - 8} ${height / 2}h16M${width / 2} ${height / 2 - 8}v16`, className: 'aq-v360-cross' })),
    h('figcaption', { className: 'aq-v360-bar' },
      h('span', { className: T.label }, h(Icon, { name: 'camera' }), ' 360° view'),
      h('span', { className: cx(T.data, 'aq-ink2') }, `yaw ${yaw}°`), bearing != null ? h('span', { className: cx(T.data, 'aq-ink2') }, `bearing ${bearing}° ± ${c.yawToBearingErr}°`) : null,
      h('span', { className: cx(T.data, 'aq-ink3') }, `fov ${fov}°`),
      h('span', { className: cx('aq-v360-sync', T.micro, synced ? 'is-on' : 'is-off') }, h(Icon, { name: synced ? 'done' : 'warning' }), synced ? 'synced with strip' : 'not synced — click to re-sync')));
}

// ---------------------------------------------------------------------------
export interface ZoomCropProps { c: any; target: string; width?: number; height?: number; fov?: number; note?: string }
/** A full-resolution crop around one box, with its reading. Opens from a box or an evidence card. */
export function ZoomCrop({ c, target, width = 280, height = 160, fov = 14, note }: ZoomCropProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const t = [...(c.texts || []), ...(c.detections || [])].find((o: any) => o.id === target);
  if (!t) return null;
  const sc = sceneFor(c);
  const fv = Math.max(fov, t.w * 1.7, t.h * 1.7 * width / height);
  const cam: Cam = { pos: [0, 0, 1.7], yaw: t.yaw, pitch: t.pitch, fov: fv, w: width, h: height };
  const a = dirPoint(t.yaw - t.w / 2, t.pitch + t.h / 2, cam), b = dirPoint(t.yaw + t.w / 2, t.pitch - t.h / 2, cam);
  const isText = !!t.text;
  const px = Math.round(t.w / 360 * (c.size?.[0] || 6080)), py = Math.round(t.h / 180 * (c.size?.[1] || 3040));
  return h('figure', { className: 'aq-crop', 'data-link': t.id, style: { width } },
    h('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': `Crop of ${isText ? t.text : t.label}` },
      h(PerspScene, { sc, cam }),
      a && b ? h('rect', { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]), height: Math.abs(b[1] - a[1]), className: isText ? 'aq-crop-box is-text' : 'aq-crop-box', strokeWidth: stage ? 3 : 1.5, fill: 'none' }) : null,
      isText && a && b ? h('text', { x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2 + (stage ? 8 : 4), textAnchor: 'middle', className: 'aq-crop-sign', style: { fontSize: Math.min((b[1] - a[1]) * 0.62, ((b[0] - a[0]) / Math.max(4, t.text.length)) * 1.5) } }, t.text) : null),
    h('figcaption', { className: 'aq-crop-cap' },
      h('span', { className: isText ? T.data : T.label }, isText ? `“${t.text}”` : t.label), h('span', { className: cx(T.data, 'aq-ink2') }, (isText ? t.conf : t.score).toFixed(2)),
      h('span', { className: cx(T.micro, 'aq-ink3') }, note || `full resolution · ${px}×${py} px of ${c.size?.[0]}×${c.size?.[1]} · yaw ${t.yaw}°`)));
}

// ---------------------------------------------------------------------------
export interface LayerTogglesProps { layers: Record<string, boolean>; counts?: Record<string, string>; onChange?: (k: string, v: boolean) => void; columns?: number }
const LAYER_META: Record<string, [string, string, string?]> = {
  sectors: ['View sectors', 'sector'], mask: ['Photographer mask', 'mask'], boxes: ['Detection boxes', 'object', 'var(--model)'], text: ['Text and readings', 'text', 'var(--model)'],
  seg: ['Segmentation tint', 'measure'], sun: ['Sun marker', 'sun'], water: ['Water direction', 'water'], skyline: ['Skyline trace', 'skyline'],
};
/** Overlay switches for the panorama, with counts; every layer comes from evidence in the log. */
export function LayerToggles({ layers, counts = {}, onChange, columns = 2 }: LayerTogglesProps) {
  const T = useT();
  return h('fieldset', { className: 'aq-layers', style: { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } },
    h('legend', { className: cx(T.label, 'aq-ink3') }, h(Icon, { name: 'layers' }), ' Layers'),
    Object.keys(LAYER_META).map(k => h(Toggle, { key: k, label: LAYER_META[k][0], icon: LAYER_META[k][1], on: !!layers[k], hint: counts[k], onChange: onChange ? (v: boolean) => onChange(k, v) : undefined })));
}
