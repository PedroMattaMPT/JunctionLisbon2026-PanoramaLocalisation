// Placeholder imagery: two tiny 3D scenes (urban riverfront, rural montado) that can be drawn as an
// equirectangular strip or as a rectilinear view from any camera. Stand-in for the real 6080×3040 JPG.
// Image yaw: 0° at the strip's left edge, clockwise. Direction(yaw) = (sin, cos). Camera eye height 1.7 m.

export type Pt3 = [number, number, number];
export interface Poly { pts: Pt3[]; fill: string; stroke?: string; sw?: number; cls?: string; seg?: string; depth: number; kind?: string }
export interface Disc { c: Pt3; r: number; ry?: number; fill: string; seg?: string; depth: number; kind?: string }
export interface Scene { polys: Poly[]; discs: Disc[]; sky: string; ground: string; horizon?: (yaw: number) => number; horizonFill?: string; sun?: { yaw: number; el: number }; groundSeg: string; keypoints?: Pt3[] }

const D2R = Math.PI / 180, R2D = 180 / Math.PI;
export const dir = (yaw: number) => [Math.sin(yaw * D2R), Math.cos(yaw * D2R)];
const EYE = 1.7;

// ----- palettes (illustration only: a muted photo stand-in, not UI colours) -----
const P = {
  sky: '#b9c9d3', skyR: '#c6d4dc', ground: '#8d8a84', pave: '#9b978f', quay: '#7c7a75', water: '#4d6670', water2: '#5b7580',
  granite: '#8e8c87', granite2: '#a19d95', plaster: '#d8cfbd', ochre: '#c9a35a', white: '#e6e2d8', azulejo: '#5f7fa8', azulejo2: '#dfe5ec',
  window: '#3b4247', window2: '#4a5257', door: '#2f3437', roof: '#9a5a43', far: '#9aa4a6', far2: '#8b979b', hill: '#7f8f86', sign: '#2c3236', signText: '#efe9dc',
  field: '#b8a46a', field2: '#a8955c', soil: '#9a6448', soil2: '#8a573e', grass: '#8d9a5c', trunk: '#8b4a32', trunkOld: '#5f564b', canopy: '#55663f', canopy2: '#4a5a37', farm: '#efece4', trim: '#3f6aa0', hills: '#8a9a8a', hills2: '#99a796',
};

function facade(polys: Poly[], kp: Pt3[], o: { a: number; b: number; d: number; h: number; color: string; floors?: number; bay?: number; shop?: boolean; azulejo?: boolean; balcony?: boolean; seg?: string }) {
  const m = (o.a + o.b) / 2;
  const end = (yaw: number) => { const k = o.d / Math.cos((yaw - m) * D2R); const [s, c] = dir(yaw); return [s * k, c * k]; };
  const A = end(o.a), B = end(o.b);
  const L = Math.hypot(B[0] - A[0], B[1] - A[1]);
  const at = (u: number, z: number): Pt3 => [A[0] + (B[0] - A[0]) * (u / L), A[1] + (B[1] - A[1]) * (u / L), z];
  const depth = o.d;
  polys.push({ pts: [at(0, 0), at(L, 0), at(L, o.h), at(0, o.h)], fill: o.color, depth, seg: 'building', kind: 'wall' });
  polys.push({ pts: [at(0, o.h), at(L, o.h), at(L, o.h + 0.6), at(0, o.h + 0.6)], fill: P.roof, depth: depth - 0.01, seg: 'building' });
  if (o.azulejo) polys.push({ pts: [at(L * 0.08, 3.2), at(L * 0.92, 3.2), at(L * 0.92, o.h - 0.4), at(L * 0.08, o.h - 0.4)], fill: P.azulejo, depth: depth - 0.02, seg: 'building', kind: 'azulejo' });
  const bay = o.bay || 3.2, n = Math.max(1, Math.floor(L / bay));
  const floors = o.floors || Math.max(1, Math.floor((o.h - 3.4) / 3.1));
  for (let i = 0; i < n; i++) {
    const u0 = (i + 0.3) * (L / n), u1 = (i + 0.7) * (L / n);
    for (let f = 0; f < floors; f++) {
      const z0 = 3.8 + f * 3.1, z1 = z0 + 1.8;
      if (z1 > o.h - 0.3) break;
      polys.push({ pts: [at(u0, z0), at(u1, z0), at(u1, z1), at(u0, z1)], fill: (i + f) % 3 ? P.window : P.window2, depth: depth - 0.03, seg: 'building', kind: 'window' });
      kp.push(at(u0, z0), at(u1, z1), at(u0, z1), at(u1, z0));
      if (o.balcony && f < 2) polys.push({ pts: [at(u0 - 0.25, z0 - 0.1), at(u1 + 0.25, z0 - 0.1), at(u1 + 0.25, z0 + 0.7), at(u0 - 0.25, z0 + 0.7)], fill: 'none', stroke: '#2a2f33', sw: 1.2, depth: depth - 0.04, seg: 'building' });
    }
    if (o.shop !== false) polys.push({ pts: [at(u0 - 0.2, 0), at(u1 + 0.2, 0), at(u1 + 0.2, 2.6), at(u0 - 0.2, 2.6)], fill: P.door, depth: depth - 0.03, seg: 'building', kind: 'door' });
  }
}

let URBAN: Scene | null = null;
export function urbanScene(): Scene {
  if (URBAN) return URBAN;
  const polys: Poly[] = [], discs: Disc[] = [], kp: Pt3[] = [];
  // far bank (Gaia) across the river: low buildings at ~220 m, plus a hill
  for (let y = 104; y < 172; y += 5.5) facade(polys, [], { a: y, b: y + 5, d: 210 + (y % 3) * 15, h: 10 + ((y * 7) % 9), color: (y % 2) ? P.far : P.far2, bay: 6, floors: 2, shop: false });
  polys.push(...groundStrip(102, 174, 240, 260, P.hill, 'building', 34));
  // quay and water (ground plane)
  polys.push(groundPoly(arcPts(100, 176, 9, 200, 20), P.water, 'water', 150));
  polys.push(groundPoly(arcPts(100, 176, 7.5, 9, 20), P.quay, 'road', 8));
  // facades round the square
  facade(polys, kp, { a: 18, b: 74, d: 17, h: 14.5, color: P.plaster, floors: 3, balcony: true });
  facade(polys, kp, { a: 74, b: 104, d: 28, h: 17, color: P.ochre, floors: 4 });
  facade(polys, kp, { a: 172, b: 236, d: 14, h: 13, color: P.granite2, floors: 3 });
  facade(polys, kp, { a: 236, b: 281, d: 10, h: 11.5, color: P.white, floors: 2, balcony: true });
  facade(polys, kp, { a: 281, b: 321, d: 12, h: 15, color: P.granite, floors: 3, balcony: true });
  facade(polys, kp, { a: 321, b: 360, d: 16, h: 16, color: P.azulejo2, azulejo: true, floors: 3 });
  facade(polys, kp, { a: 0, b: 18, d: 16, h: 16, color: P.azulejo2, azulejo: true, floors: 3 });
  // shop signs as dark plaques (the OCR targets)
  sign(polys, 38, 6.5, 17, 7, 2.6); sign(polys, 212.5, -3.1, 14, 4.2, 1.6); sign(polys, 289, 2, 12, 5, 1.4);
  // bollards and a lamp
  for (const y of [246, 252, 258]) post(polys, y, 5.2, 0.9, 0.16, '#3a3f42');
  post(polys, 96, 9, 5.5, 0.12, '#2f3437');
  URBAN = { polys, discs, sky: P.sky, ground: P.pave, groundSeg: 'road', sun: { yaw: 141, el: 22 }, keypoints: kp };
  return URBAN;
}

let RURAL: Scene | null = null;
export function ruralScene(): Scene {
  if (RURAL) return RURAL;
  const polys: Poly[] = [], discs: Disc[] = [];
  // far field bands
  polys.push(groundPoly(arcPts(0, 360, 60, 900, 72), P.field, 'grass', 600));
  polys.push(groundPoly(arcPts(0, 360, 18, 60, 72), P.field2, 'grass', 40));
  polys.push(groundPoly(blob(40, 9, 5, 3), P.grass, 'grass', 9)); polys.push(groundPoly(blob(250, 11, 6, 4), P.grass, 'grass', 11));
  // soil patches and the track toward yaw ~200
  polys.push(groundPoly(blob(150, 26, 9, 5), P.soil, 'ground', 26));
  polys.push(groundPoly(blob(300, 40, 14, 6), P.soil2, 'ground', 40));
  const track: Pt3[] = []; const tr: Pt3[] = [];
  for (let t = 0; t <= 1.001; t += 0.05) { const dd = 2 + t * 160, yaw = 200 + Math.sin(t * 3) * 14; const [s, c] = dir(yaw); const [ps, pc] = dir(yaw + 90); const w = 1.6 + t * 0.4; track.push([s * dd + ps * w, c * dd + pc * w, 0]); tr.unshift([s * dd - ps * w, c * dd - pc * w, 0]); }
  polys.push({ pts: [...track, ...tr], fill: P.soil, depth: 20, seg: 'ground', kind: 'track' });
  // farmhouse (whitewash, blue trim) at yaw 70, ~420 m
  { const [s, c] = dir(70), [ps, pc] = dir(160); const d = 420, w = 9; const a: Pt3 = [s * d - ps * w, c * d - pc * w, 0], b: Pt3 = [s * d + ps * w, c * d + pc * w, 0];
    polys.push({ pts: [a, b, [b[0], b[1], 5], [a[0], a[1], 5]], fill: P.farm, depth: d, seg: 'building', kind: 'farm' });
    polys.push({ pts: [a, b, [b[0], b[1], 0.9], [a[0], a[1], 0.9]], fill: P.trim, depth: d - 0.1, seg: 'building' });
    polys.push({ pts: [[a[0], a[1], 5], [b[0], b[1], 5], [b[0], b[1], 5.4], [a[0], a[1], 5.4]], fill: P.trim, depth: d - 0.1, seg: 'building' }); }
  // cork and holm oaks
  const trees = [[12, 16, 1], [30, 70, 0], [48, 120, 0], [88, 24, 1], [104, 260, 0], [118, 60, 0], [140, 180, 0], [150, 34, 1], [168, 95, 0], [184, 130, 0], [228, 19, 1], [246, 140, 0], [262, 48, 0], [282, 230, 0], [300, 13, 1], [318, 85, 0], [334, 38, 1], [352, 110, 0], [60, 160, 0], [210, 220, 0], [5, 300, 0], [74, 340, 0], [196, 310, 0], [330, 260, 0]];
  for (const [yaw, d, cork] of trees) tree(polys, discs, yaw, d, !!cork);
  const horizon = (y: number) => 0.9 + 0.55 * Math.sin((y * 2 + 30) * D2R) + 0.35 * Math.sin((y * 5 + 10) * D2R) + 0.2 * Math.sin((y * 11) * D2R);
  RURAL = { polys, discs, sky: P.skyR, ground: '#b09a62', groundSeg: 'grass', horizon, horizonFill: P.hills, sun: { yaw: 178, el: 61 } };
  return RURAL;
}

function sign(polys: Poly[], yaw: number, pitch: number, d: number, w: number, hh: number) {
  // angular w×h at yaw/pitch, placed on a plane at distance d
  const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
  const r = d, z = EYE + r * Math.tan(pitch * D2R), hw = Math.tan((w / 2) * D2R) * r, hh2 = Math.tan((hh / 2) * D2R) * r;
  const cx = s * (r - 0.3), cy = c * (r - 0.3);
  polys.push({ pts: [[cx - ps * hw, cy - pc * hw, z - hh2], [cx + ps * hw, cy + pc * hw, z - hh2], [cx + ps * hw, cy + pc * hw, z + hh2], [cx - ps * hw, cy - pc * hw, z + hh2]], fill: P.sign, depth: r - 0.3, seg: 'building', kind: 'sign' });
}
function post(polys: Poly[], yaw: number, d: number, hgt: number, w: number, fill: string) {
  const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
  const x = s * d, y = c * d;
  polys.push({ pts: [[x - ps * w, y - pc * w, 0], [x + ps * w, y + pc * w, 0], [x + ps * w, y + pc * w, hgt], [x - ps * w, y - pc * w, hgt]], fill, depth: d, seg: 'building' });
}
function tree(polys: Poly[], discs: Disc[], yaw: number, d: number, cork: boolean) {
  const [s, c] = dir(yaw), [ps, pc] = dir(yaw + 90);
  const x = s * d, y = c * d, tw = 0.35, th = 2.2;
  polys.push({ pts: [[x - ps * tw, y - pc * tw, 0], [x + ps * tw, y + pc * tw, 0], [x + ps * tw, y + pc * tw, th + 0.6], [x - ps * tw, y - pc * tw, th + 0.6]], fill: cork ? P.trunk : P.trunkOld, depth: d, seg: 'tree', kind: cork ? 'cork' : 'holm' });
  discs.push({ c: [x, y, th + 2.4], r: 4.2, ry: 2.4, fill: cork ? P.canopy : P.canopy2, depth: d - 0.5, seg: 'tree' });
}
export function arcPts(a: number, b: number, r0: number, r1: number, n: number): Pt3[] {
  const out: Pt3[] = [];
  for (let i = 0; i <= n; i++) { const y = a + (b - a) * i / n; const [s, c] = dir(y); out.push([s * r1, c * r1, 0]); }
  for (let i = n; i >= 0; i--) { const y = a + (b - a) * i / n; const [s, c] = dir(y); out.push([s * r0, c * r0, 0]); }
  return out;
}
function blob(yaw: number, d: number, rx: number, ry: number): Pt3[] {
  const [s, c] = dir(yaw); const out: Pt3[] = [];
  for (let i = 0; i < 18; i++) { const t = i / 18 * Math.PI * 2; out.push([s * d + Math.cos(t) * rx, c * d + Math.sin(t) * ry, 0]); }
  return out;
}
function groundPoly(pts: Pt3[], fill: string, seg: string, depth: number): Poly { return { pts, fill, seg, depth }; }
function groundStrip(a: number, b: number, d: number, h: number, fill: string, seg: string, n: number): Poly[] {
  // a hill profile behind the far bank
  const pts: Pt3[] = [];
  for (let i = 0; i <= n; i++) { const y = a + (b - a) * i / n; const [s, c] = dir(y); const z = 18 + 22 * Math.sin((i / n) * Math.PI) + 6 * Math.sin(i * 1.7); pts.push([s * (d + 40), c * (d + 40), z]); }
  for (let i = n; i >= 0; i--) { const y = a + (b - a) * i / n; const [s, c] = dir(y); pts.push([s * (d + 40), c * (d + 40), 0]); }
  return [{ pts, fill, seg, depth: d + 40 }];
}

// ---------- projections ----------
/** World point → (yaw°, pitch°) from a camera at (cx, cy, EYE). */
export function toYawPitch(p: Pt3, cam: Pt3 = [0, 0, EYE]): [number, number] {
  const dx = p[0] - cam[0], dy = p[1] - cam[1], dz = p[2] - cam[2];
  let yaw = Math.atan2(dx, dy) * R2D; if (yaw < 0) yaw += 360;
  return [yaw, Math.atan2(dz, Math.hypot(dx, dy)) * R2D];
}
/** Subdivide polygon edges so long ground edges curve correctly in the strip. */
function densify(pts: Pt3[], maxLen: number): Pt3[] {
  const out: Pt3[] = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); const n = Math.max(1, Math.ceil(L / maxLen));
    for (let k = 0; k < n; k++) out.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, a[2] + (b[2] - a[2]) * k / n]);
  }
  return out;
}
/** Equirect polygon points (in strip px). Handles the 0/360 seam by unwrapping relative to the first point. */
export function equiPts(pts: Pt3[], W: number, H: number): [number, number][][] {
  const dense = densify(pts, 1.5);
  let prev: number | null = null; const raw: [number, number][] = [];
  for (const p of dense) {
    let [yaw, pitch] = toYawPitch(p);
    if (prev != null) { while (yaw - prev > 180) yaw -= 360; while (yaw - prev < -180) yaw += 360; }
    prev = yaw; raw.push([yaw / 360 * W, (90 - pitch) / 180 * H]);
  }
  const xs = raw.map(r => r[0]); const min = Math.min(...xs), max = Math.max(...xs);
  const copies: [number, number][][] = [raw];
  if (min < 0) copies.push(raw.map(r => [r[0] + W, r[1]] as [number, number]));
  if (max > W) copies.push(raw.map(r => [r[0] - W, r[1]] as [number, number]));
  return copies;
}

export interface Cam { pos: Pt3; yaw: number; pitch?: number; fov: number; w: number; h: number }
/** Rectilinear projection with near-plane clipping. Returns screen points or null when fully behind. */
export function persp(pts: Pt3[], cam: Cam): [number, number][] | null {
  const f = (cam.w / 2) / Math.tan((cam.fov / 2) * D2R);
  const [s, c] = dir(cam.yaw); const pr = (cam.pitch || 0) * D2R, cp = Math.cos(pr), sp = Math.sin(pr);
  const rel = densify(pts, 2).map(p => {
    const dx = p[0] - cam.pos[0], dy = p[1] - cam.pos[1], dz = p[2] - cam.pos[2];
    const fwd0 = dx * s + dy * c, right = dx * c - dy * s;
    const fwd = fwd0 * cp + dz * sp, up = -fwd0 * sp + dz * cp;
    return [right, up, fwd];
  });
  const near = 0.3; const clipped: number[][] = [];
  for (let i = 0; i < rel.length; i++) {
    const a = rel[i], b = rel[(i + 1) % rel.length];
    const ain = a[2] >= near, bin = b[2] >= near;
    if (ain) clipped.push(a);
    if (ain !== bin) { const t = (near - a[2]) / (b[2] - a[2]); clipped.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near]); }
  }
  if (clipped.length < 3) return null;
  return clipped.map(([x, y, z]) => [cam.w / 2 + (x / z) * f, cam.h / 2 - (y / z) * f]);
}
export function perspPoint(p: Pt3, cam: Cam): [number, number] | null { const r = persp([p, p, p], cam); return r ? r[0] : null; }
export const yawPitchToXY = (yaw: number, pitch: number, W: number, H: number): [number, number] => [((yaw % 360) + 360) % 360 / 360 * W, (90 - pitch) / 180 * H];
/** Skyline: the highest elevation angle of anything at each yaw (degrees), sampled every `step`°. */
export function skyline(sc: Scene, step = 2): [number, number][] {
  const out: [number, number][] = [];
  for (let y = 0; y <= 360; y += step) {
    let best = sc.horizon ? sc.horizon(y) : 0;
    for (const p of sc.polys) {
      if (p.seg !== 'building' && p.seg !== 'tree') continue;
      if (p.kind && p.kind !== 'wall' && p.kind !== 'farm' && p.kind !== 'cork' && p.kind !== 'holm') continue;
      const yp = p.pts.map(q => toYawPitch(q));
      const ys = yp.map(q => q[0]); let lo = Math.min(...ys), hi = Math.max(...ys);
      if (hi - lo > 180) continue;
      if (y >= lo && y <= hi) best = Math.max(best, ...yp.map(q => q[1]));
    }
    for (const d of sc.discs) { const [dy, dp] = toYawPitch(d.c); const ar = Math.atan2(d.r, Math.hypot(d.c[0], d.c[1])) * R2D; if (Math.abs(((y - dy + 540) % 360) - 180) < ar) best = Math.max(best, dp + Math.atan2(d.ry || d.r, Math.hypot(d.c[0], d.c[1])) * R2D * 0.9); }
    out.push([y, best]);
  }
  return out;
}
